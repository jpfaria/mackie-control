"""Runs the bridge against real MIDI ports (mido), until Ctrl-C."""
from __future__ import annotations

import threading

import mido

from ..surfaces import get as get_surface
from .daemon import Bridge
from .profile import load_profile


def find_port(hint: str, names: list[str]) -> str:
    found = [n for n in names if hint in n]
    if not found:
        raise SystemExit(f"no MIDI port matching {hint!r}: {names}")
    return found[0]


def run(profile_path: str, port: str | None = None, log=print) -> None:
    profile = load_profile(profile_path)
    surface = get_surface(profile.surface)
    src = port or find_port(surface.port_hint, mido.get_input_names())
    dst = port or find_port(surface.port_hint, mido.get_output_names())

    with mido.open_output(dst) as out, mido.open_input(src) as inp:
        bridge = Bridge(profile, send=lambda **k: out.send(mido.Message(**k)), log=log)
        threading.Thread(target=bridge.drain_forever, daemon=True).start()
        log(f"bridge: {surface.name} ({src}) -> "
            + ", ".join(b.name for b in profile.banks))
        bridge.select_bank(0)
        try:
            for msg in inp:
                bridge.on_midi(msg)
        except KeyboardInterrupt:
            log("stopped")
