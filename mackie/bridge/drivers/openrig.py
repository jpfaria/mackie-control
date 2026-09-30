"""OpenRig, through its MCP server (`http://127.0.0.1:4123`).

A fader here is one strip of OpenRig's global mixer -- the level OpenRig sends
to an output (FRFR, SYN-5050, ...) or takes from an input. With the HD 8 mixer
in Bypass the HD 8's own aux buses ignore writes, so this is where those
levels are set (docs/openrig-bank/README.md).

Wire format, measured 2026-09-30 against OpenRig's rmcp 1.7.0 server:
streamable HTTP. A POST of `initialize` answers `text/event-stream` with a
`mcp-session-id` header; every later request carries that header, and a
request before `initialize` is refused with 422. Answers come as SSE `data:`
lines holding the JSON-RPC response.

The strips change with every project and chain opened, so the driver's banks
are live: `OpenRig OUT` and `OpenRig IN` take their faders from
`openrig://mixer` while the bridge runs, in the order OpenRig lists them, and
address each strip by its id. Nothing about them is written in a profile.

Targets name a strip the way `openrig://mixer` lists it: the full id
(`out:24,25@coreaudio:...`), the full name, or the start of the name
("FRFR" matches "FRFR (ADAT out 11/12)"). A name that matches more than one
strip is refused rather than guessed. `mute:FRFR` is that strip's mute: it
reads 1.0 / 0.0 and toggles, which is how the bridge asks for a mute lamp.

Transport: MCP, because it is what OpenRig serves today; its gRPC adapter
(`crates/adapter-server`) is still a placeholder (2026-09-30). Everything
wire-specific lives in `Http`, so a gRPC client replaces that class only.

Fader travel is linear in dB over OpenRig's own range, -60..+12 dB (the
bottom is silence, as in OpenRig); unity sits at 5/6 of the travel."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import Driver, Unsupported

URL = "http://127.0.0.1:4123"
MIN_DB, MAX_DB = -60.0, 12.0
TIMEOUT = 2.0


def to_db(value):
    v = max(0.0, min(1.0, value))
    return MIN_DB + v * (MAX_DB - MIN_DB)


def from_db(db):
    return max(0.0, min(1.0, (db - MIN_DB) / (MAX_DB - MIN_DB)))


class McpError(Exception):
    """The server answered, and said no."""


class Http:
    """A minimal MCP client over streamable HTTP, standard library only."""

    def __init__(self, url=URL, timeout=TIMEOUT):
        self.url, self.timeout = url, timeout
        self.session = None
        self._id = 0

    def _post(self, body):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["mcp-session-id"] = self.session
        req = urllib.request.Request(self.url, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            self.session = r.headers.get("mcp-session-id") or self.session
            return r.read().decode()

    def _rpc(self, method, params):
        self._id += 1
        text = self._post({"jsonrpc": "2.0", "id": self._id,
                           "method": method, "params": params})
        for line in text.splitlines():
            line = line.removeprefix("data:").strip() if line.startswith("data:") else line.strip()
            if not line.startswith("{"):
                continue
            msg = json.loads(line)
            if msg.get("id") != self._id:
                continue
            if "error" in msg:
                raise McpError(msg["error"].get("message", msg["error"]))
            return msg["result"]
        raise OSError(f"no answer to {method}")

    def connect(self):
        self.session = None
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "mackie-control", "version": "0"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def resource(self, uri):
        result = self._rpc("resources/read", {"uri": uri})
        return json.loads(result["contents"][0]["text"])

    def call(self, tool, args):
        result = self._rpc("tools/call", {"name": tool, "arguments": args})
        if result.get("isError"):
            text = " ".join(c.get("text", "") for c in result.get("content", []))
            raise McpError(text or f"{tool} refused")
        return result


class OpenRig(Driver):
    name = "openrig"

    DEFAULT_BANKS = [{"name": "OpenRig OUT", "live": "output"},
                     {"name": "OpenRig IN", "live": "input"}]

    def __init__(self, client=None):
        self.cli = client if client is not None else Http()
        self._ready = client is not None

    def _retry(self, operation):
        """Connect on first use -- OpenRig may start after the bridge -- and
        reconnect once when the session is gone (OpenRig restarted). A refused
        command or an unreachable server is Unsupported, never a crash."""
        for attempt in (1, 2):
            try:
                if not self._ready:
                    self.cli.connect()
                    self._ready = True
                return operation(self.cli)
            except McpError as e:
                raise Unsupported(f"openrig: {e}") from e
            except (OSError, urllib.error.URLError, ValueError) as e:
                self._ready = False
                if attempt == 2 or not hasattr(self.cli, "connect"):
                    raise Unsupported(f"openrig: not reachable at {URL} ({e})") from e

    def _strip(self, c, target):
        strips = c.resource("openrig://mixer")["strips"]
        for s in strips:
            if target in (s["id"], s["name"]):
                return s
        want = target.casefold()
        found = [s for s in strips if s["name"].casefold().startswith(want)]
        if len(found) == 1:
            return found[0]
        if not found:
            raise Unsupported(f"openrig: no mixer strip called {target!r}")
        raise Unsupported(f"openrig: {target!r} matches "
                          + ", ".join(repr(s["name"]) for s in found))

    def live_faders(self, which):
        """The first eight strips of one direction ("output" / "input"), as
        OpenRig lists them now."""
        strips = self._retry(lambda c: c.resource("openrig://mixer")["strips"])
        mine = [s for s in strips if s.get("direction") == which][:8]
        group = "in" if which == "input" else "out"
        return {n: {"target": s["id"], "label": s["name"], "group": group,
                    "mute": "mute:" + s["id"]}
                for n, s in enumerate(mine, start=1)}

    def read(self, target):
        if target.startswith("mute:"):
            name = target.removeprefix("mute:")
            return self._retry(lambda c: float(self._strip(c, name)["muted"]))
        return self._retry(lambda c: from_db(self._strip(c, target)["gain_db"]))

    def write(self, target, value):
        def op(c):
            c.call("set_mixer_fader", {"strip": self._strip(c, target)["id"],
                                       "gain_db": to_db(value)})
        self._retry(op)

    def toggle(self, target):
        target = target.removeprefix("mute:")

        def op(c):
            s = self._strip(c, target)
            muted = not s["muted"]
            c.call("set_mixer_mute", {"strip": s["id"], "muted": muted})
            return muted
        return self._retry(op)
