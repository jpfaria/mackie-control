"""PreSonus Quantum HD 8, through the `quantum-hd8` library (UCNet).

The HD 8 does not receive MIDI: a full sweep of CC, pitch bend and notes on
both of its CoreMIDI ports changed none of its 1419 parameters (2026-09-20).
Every write here goes to `ucdaemon` over TCP instead.

That TCP session does not survive the interface being switched off: afterwards
every write raises `OSError: Bad file descriptor` while reads keep answering
from a stale cache, so the bridge looks alive and moves nothing (measured
2026-09-22). The driver therefore reconnects once per operation and retries."""
from __future__ import annotations

from . import Driver, Unsupported


def _connect():
    try:
        from quantum_hd8.client import Client
    except ImportError as e:          # pragma: no cover - depends on the host
        raise Unsupported("quantum-hd8 is not installed: "
                          "pipx install git+https://github.com/jpfaria/quantum-hd8") from e
    client = Client()
    client.connect()
    return client


class HD8(Driver):
    name = "hd8"
    BUTTONS = {"rec": "scene"}        # R n loads the n-th stored scene

    # Two banks, because that is how the desk is read: what comes in, and
    # where it goes. The eight analogue inputs are the eight the HD 8 has;
    # `aux/ch(4+k)` is the ADAT k/k+1 bus (measured, quantum-hd8 docs).
    DEFAULT_BANKS = [
        {"name": "HD 8 IN",
         "faders": {n: {"driver": "hd8", "target": f"line/ch{n}/volume",
                        "label": f"IN {n}", "group": "in",
                        "mute": f"line/ch{n}/mute"}
                    for n in range(1, 9)}},
        {"name": "HD 8 OUT",
         "faders": {
             1: {"driver": "hd8", "target": "global/mainOutVolume",
                 "label": "MAIN", "group": "out", "mute": "global/mute"},
             2: {"driver": "hd8", "target": "global/phones1_volume",
                 "label": "PHONES 1", "group": "out"},
             3: {"driver": "hd8", "target": "global/phones2_volume",
                 "label": "PHONES 2", "group": "out"},
             **{3 + k: {"driver": "hd8", "target": f"aux/ch{4 + k}/volume",
                        "label": f"ADAT {2 * k - 1}/{2 * k}", "group": "out",
                        "mute": f"aux/ch{4 + k}/mute"}
                for k in range(1, 6)}}},
    ]

    def __init__(self, client=None, connect=None):
        # A client passed without a way to rebuild it (the tests) cannot be
        # reconnected: the driver then refuses instead of crashing.
        self._connect = connect or (None if client is not None else _connect)
        self.cli = client if client is not None else self._connect()

    def _retry(self, operation):
        """Run an operation, and if the socket is gone, reconnect once and run
        it again. A second failure is Unsupported, not a crash."""
        try:
            return operation(self.cli)
        except OSError as e:
            self.cli = self._reconnect(e)
            try:
                return operation(self.cli)
            except OSError as again:
                raise Unsupported(f"hd8: {again}") from again

    def _reconnect(self, cause):
        if self._connect is None:
            raise Unsupported(f"hd8: lost the connection to ucdaemon ({cause})") from cause
        close = getattr(self.cli, "close", None)
        if close is not None:
            try:
                close()
            except OSError:
                pass
        try:
            return self._connect()
        except Unsupported:
            raise
        except Exception as e:
            raise Unsupported(f"hd8: cannot reconnect to ucdaemon ({e})") from e

    def read(self, target):
        return self._retry(lambda c: float(c.get(target)))

    def write(self, target, value):
        v = max(0.0, min(1.0, value))
        self._retry(lambda c: c.set_raw(target, v))

    def toggle(self, target):
        on = self._retry(lambda c: float(c.get(target))) >= 0.5
        self._retry(lambda c: c.set(target, 0 if on else 1))
        return not on

    def scenes(self):
        return [n.removesuffix(".scene") for n in self._retry(lambda c: c.scenes)]

    def load_scene(self, index):
        names = self.scenes()
        if not 0 <= index < len(names):
            raise Unsupported(f"scene {index + 1} does not exist (there are {len(names)})")
        self._retry(lambda c: c.load_scene(names[index], keep_gains=True))
        return names[index]
