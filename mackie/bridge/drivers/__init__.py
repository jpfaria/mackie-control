"""One driver per thing a fader can control. Each speaks its own dialect; the
bridge only ever calls this interface:

    read(target)   -> 0..1 (or None when the driver cannot read it back)
    write(target, value)
    toggle(target) -> the new state
    scenes()       -> list of names
    load_scene(i)
    command(target, name)  -> run a named command (play, next track, ...)

A driver that cannot do something raises Unsupported -- the bridge turns that
into a warning, never a crash."""
from __future__ import annotations


class Unsupported(Exception):
    pass


class Driver:
    name = "driver"

    # Buttons this driver knows what to do with, as {button: command}. The
    # bridge uses these when the profile says nothing, so a profile does not
    # have to repeat what a driver already knows. "scene" is special: it means
    # load_scene(), everything else goes to command().
    BUTTONS: dict[str, str] = {}

    # The banks this device is worth on its own, as a profile would write them:
    # the same gear has the same knobs in every rig, so the map belongs to the
    # driver. A profile that writes its own faders is never touched.
    DEFAULT_BANKS: list[dict] = []

    def read(self, target):
        raise Unsupported(f"{self.name}: read {target}")

    def write(self, target, value):
        raise Unsupported(f"{self.name}: write {target}")

    def toggle(self, target):
        raise Unsupported(f"{self.name}: toggle {target}")

    def command(self, target, name):
        raise Unsupported(f"{self.name}: command {name!r}")

    def scenes(self):
        return []

    def load_scene(self, index):
        raise Unsupported(f"{self.name}: scenes")


def classes() -> dict[str, type]:
    """The driver classes, without building any: reading a class attribute
    (its default banks, its buttons) must not open a connection to gear."""
    from . import hd8, mac
    return {"hd8": hd8.HD8, "mac": mac.MacVolume, "app": mac.AppVolume}


def build(name: str, **opts) -> Driver:
    known = classes()
    try:
        return known[name](**opts)
    except KeyError:
        raise SystemExit(f"unknown driver {name!r}; known: {', '.join(known)}")
