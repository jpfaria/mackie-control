"""CLI: run a bridge, list surfaces, or watch what a surface sends."""
from __future__ import annotations

import argparse
import sys

import mido

from . import protocol, surfaces


def cmd_bridge(a):
    from .bridge.run import run
    run(a.profile, port=a.port)


def cmd_surfaces(a):
    for nome, s in surfaces.SURFACES.items():
        print(f"{nome}: {s.name} -- {s.faders} faders, {s.encoders} encoders, "
              f"porta {s.port_hint!r}")
        if s.notes:
            print(f"  {s.notes}")


def cmd_ports(a):
    print("entradas:")
    for n in mido.get_input_names():
        print(f"  {n}")
    print("saidas:")
    for n in mido.get_output_names():
        print(f"  {n}")


def cmd_watch(a):
    """Print what the surface sends, decoded -- how every mapping here was found."""
    surface = surfaces.get(a.surface)
    porta = a.port or next((n for n in mido.get_input_names()
                            if surface.port_hint in n), None)
    if porta is None:
        raise SystemExit(f"nenhuma porta com {surface.port_hint!r}; veja `mackie ports`")
    print(f"ouvindo {porta} por {a.seconds}s (Ctrl-C para sair)")
    import time
    fim = time.time() + a.seconds
    with mido.open_input(porta) as inp:
        while time.time() < fim:
            for msg in inp.iter_pending():
                evento = protocol.decode(msg)
                if evento is not None:
                    print(f"  {evento}")
            time.sleep(0.01)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mackie", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("bridge", help="run a surface against a rig profile: bridge PERFIL.yaml")
    s.add_argument("profile")
    s.add_argument("--port", help="porta MIDI exata, se o palpite da superficie nao servir")
    s.set_defaults(fn=cmd_bridge)

    s = sub.add_parser("surfaces", help="control surfaces this package knows")
    s.set_defaults(fn=cmd_surfaces)

    s = sub.add_parser("ports", help="MIDI ports visible right now")
    s.set_defaults(fn=cmd_ports)

    s = sub.add_parser("watch", help="print decoded messages from a surface (mapping a new one)")
    s.add_argument("seconds", type=int, nargs="?", default=30)
    s.add_argument("--surface"); s.add_argument("--port")
    s.set_defaults(fn=cmd_watch)

    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 0
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
