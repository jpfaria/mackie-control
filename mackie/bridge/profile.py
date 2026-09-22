"""The rig profile: what each fader and button of a bank is wired to.

    banks:
      - name: HD 8
        faders:
          1: {driver: hd8, target: global/mainOutVolume, label: MAIN, group: out}
          5: {driver: hd8, target: line/ch1/volume, label: GUITAR 1, group: in,
              mute: line/ch1/mute}
        buttons:
          rec: scene        # R n loads scene n of that fader's driver
          select: bank      # optional: the square button n jumps straight to bank n
                            # (banks always page with Channel / arrows)
        transport:          # the buttons along the bottom edge
          play: {driver: app, target: Spotify, command: playpause}
          forward: {driver: app, target: Spotify, command: next track}

A fader with `mute:` is muted with that parameter; one without is muted by
zeroing its own value, which is remembered and handed back. `group` keeps solo
honest: soloing an input must not mute the outputs.

Encoders are endless knobs: they nudge their destination up or down instead of
jumping to a position, so they need no takeover.

A top-level `global:` block holds faders, encoders and transport that work in
every bank:

    global:
      encoders:
        1: {driver: app, target: Spotify, label: Spotify}
      transport:
        play: {driver: app, target: Spotify, command: playpause}

See examples/ for complete profiles."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Destination:
    driver: str
    target: str | None = None
    label: str = ""
    group: str = "out"
    mute: str | None = None


@dataclass(frozen=True)
class Command:
    driver: str
    target: str | None
    command: str


@dataclass(frozen=True)
class Bank:
    name: str
    faders: dict[int, Destination] = field(default_factory=dict)
    encoders: dict[int, Destination] = field(default_factory=dict)
    buttons: dict[str, str] = field(default_factory=dict)
    transport: dict[str, Command] = field(default_factory=dict)


@dataclass(frozen=True)
class Profile:
    surface: str
    banks: list[Bank]
    # A bank of its own that is always in reach: its faders and transport work
    # whichever bank is selected. Controlling the music has nothing to do with
    # which set of faders you happen to be on.
    globals: Bank = field(default_factory=lambda: Bank(name="global"))
    # Sending a fader's real value back makes the surface blink that channel's
    # LED until the physical fader matches. Useful as a "you are out of sync"
    # sign, annoying if you never intend to chase it. Off by default.
    positions: bool = False

    def bank(self, i: int) -> Bank:
        return self.banks[i % len(self.banks)]


def _destination(raw: dict) -> Destination:
    if "driver" not in raw:
        raise SystemExit(f"destination without a driver: {raw}")
    return Destination(driver=raw["driver"], target=raw.get("target"),
                       label=raw.get("label", raw.get("target", "")),
                       group=raw.get("group", "out"), mute=raw.get("mute"))


def _command(raw: dict) -> Command:
    if "driver" not in raw or "command" not in raw:
        raise SystemExit(f"transport entry needs driver and command: {raw}")
    return Command(driver=raw["driver"], target=raw.get("target"),
                   command=raw["command"])


def parse_profile(data: dict) -> Profile:
    banks = data.get("banks") or []
    if not banks:
        raise SystemExit("profile has no banks")
    g = data.get("global") or {}
    return Profile(
        surface=data.get("surface", "smc-mixer"),
        positions=bool(data.get("positions", False)),
        globals=Bank(name="global",
                     faders={int(k): _destination(v)
                             for k, v in (g.get("faders") or {}).items()},
                     encoders={int(k): _destination(v)
                               for k, v in (g.get("encoders") or {}).items()},
                     buttons=dict(g.get("buttons") or {}),
                     transport={k: _command(v)
                                for k, v in (g.get("transport") or {}).items()}),
        banks=[Bank(name=b.get("name", f"bank {i + 1}"),
                    faders={int(k): _destination(v) for k, v in (b.get("faders") or {}).items()},
                    encoders={int(k): _destination(v)
                              for k, v in (b.get("encoders") or {}).items()},
                    buttons=dict(b.get("buttons") or {}),
                    transport={k: _command(v)
                               for k, v in (b.get("transport") or {}).items()})
               for i, b in enumerate(banks)],
    )


def load_profile(path: str | Path) -> Profile:
    path = Path(path).expanduser()
    if not path.exists():
        raise SystemExit(f"profile not found: {path}")
    return parse_profile(yaml.safe_load(path.read_text()) or {})
