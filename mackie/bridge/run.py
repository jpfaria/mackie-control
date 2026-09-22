"""Runs the bridge against real MIDI ports (mido), until Ctrl-C."""
from __future__ import annotations

import threading

import mido

from ..surfaces import get as get_surface
from .daemon import Bridge
from .profile import load_profile


def find_port(hints, names: list[str]) -> str:
    """The first port matching the first hint that matches anything. A surface
    gives several because the same device is named differently depending on how
    it is connected: `SMC-Mixer-Master` over USB, `SMC-Mixer Bluetooth` over
    BLE (measured 2026-09-22)."""
    for hint in hints:
        found = [n for n in names if hint in n]
        if found:
            return found[0]
    raise SystemExit(f"no MIDI port matching {list(hints)}: {names}")


def run(profile_path: str, port: str | None = None, log=print) -> None:
    profile = load_profile(profile_path)
    surface = get_surface(profile.surface)
    src = port or find_port(surface.port_hints, mido.get_input_names())
    dst = port or find_port(surface.port_hints, mido.get_output_names())

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
