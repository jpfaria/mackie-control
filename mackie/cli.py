"""CLI: run a bridge, list surfaces, or watch what a surface sends."""
from __future__ import annotations

import argparse
import sys

import mido

from . import protocol, surfaces
from .bridge.run import find_port


def cmd_bridge(a):
    from .bridge.run import run
    run(a.profile, port=a.port)


def cmd_surfaces(a):
    for name, s in surfaces.SURFACES.items():
        print(f"{name}: {s.name} -- {s.faders} faders, {s.encoders} encoders, "
              f"port {s.port_hint!r}")
        if s.notes:
            print(f"  {s.notes}")


def cmd_ports(a):
    print("inputs:")
    for n in mido.get_input_names():
        print(f"  {n}")
    print("outputs:")
    for n in mido.get_output_names():
        print(f"  {n}")


def cmd_watch(a):
    """Print what the surface sends, decoded -- how every mapping here was found."""
    surface = surfaces.get(a.surface)
    port = a.port or find_port(surface.port_hints, mido.get_input_names())
    print(f"listening on {port} for {a.seconds}s (Ctrl-C to stop)")
    import time
    end = time.time() + a.seconds
    with mido.open_input(port) as inp:
        while time.time() < end:
            for msg in inp.iter_pending():
                event = protocol.decode(msg)
                if event is not None:
                    print(f"  {event}")
            time.sleep(0.01)


def cmd_devices(a):
    """What each bank is: its device, its faders and the scenes it can load."""
    from .bridge import describe as desc
    from .bridge.defaults import expand
    from .bridge.drivers import build
    from .bridge.profile import load_profile

    profile = expand(load_profile(a.profile))
    drivers = {}
    for bank in profile.banks:
        name = bank.driver or desc._main_driver(bank)
        if name is not None and name not in drivers:
            try:
                drivers[name] = build(name)
            except Exception:
                drivers[name] = None
    for line in desc.describe(profile, drivers=drivers):
        print(line)


def cmd_service(a):
    """Keep the bridge running at login and after any exit (a LaunchAgent)."""
    from . import service
    if a.action == "install":
        if not a.profile:
            raise SystemExit("service install needs PROFILE.yaml")
        service.install(a.profile)
    elif a.action == "uninstall":
        service.uninstall()
    elif a.action == "restart":
        service.restart()
    else:
        print(service.status())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mackie", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("bridge", help="run a surface against a rig profile: bridge PROFILE.yaml")
    s.add_argument("profile")
    s.add_argument("--port", help="exact MIDI port, when the surface's hint is not enough")
    s.set_defaults(fn=cmd_bridge)

    s = sub.add_parser("surfaces", help="control surfaces this package knows")
    s.set_defaults(fn=cmd_surfaces)

    s = sub.add_parser("ports", help="MIDI ports visible right now")
    s.set_defaults(fn=cmd_ports)

    s = sub.add_parser("devices", help="what each bank is and which scenes it can load")
    s.add_argument("profile")
    s.set_defaults(fn=cmd_devices)

    s = sub.add_parser("watch", help="print decoded messages from a surface (mapping a new one)")
    s.add_argument("seconds", type=int, nargs="?", default=30)
    s.add_argument("--surface"); s.add_argument("--port")
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("service", help="run the bridge at login and restart it if it exits (macOS)")
    s.add_argument("action", choices=["install", "uninstall", "restart", "status"])
    s.add_argument("profile", nargs="?")
    s.set_defaults(fn=cmd_service)

    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 0
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
