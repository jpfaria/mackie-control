"""M-VAVE MK-300, through the `mvave` library (USB SysEx).

Everything here is read back from the pedal's edit buffer, so a fader on it
takes over like any other. The presets (160) are its scenes."""
from __future__ import annotations

from ._pedal import Pedal


class _Real:                             # pragma: no cover - needs the pedal
    """The few calls the driver needs, on top of `mvave`."""

    def __init__(self):
        from mvave import devices
        from mvave.device import MVave
        import mvave.devices.mk300 as mk
        self._mk = mk
        self._dev = MVave(devices.get("mk300"), None)

    def volume(self):
        return self._dev.read_preset().volume

    def set_volume(self, v):
        self._dev.set_u16(self._mk.OFF_VOL, v)

    def preset_names(self):
        return self._dev.preset_names()

    def load_preset(self, i):
        self._dev.load_preset(i)

    def current(self):
        return self._dev.current_preset_index()


class MK300(Pedal):
    name = "mk300"
    LABEL = "MK-300"
    BUTTONS = {"rec": "scene"}
    DEFAULT_BANKS = [
        {"name": "MK-300",
         "faders": {1: {"driver": "mk300", "target": "volume",
                        "label": "MK-300 VOL", "group": "out"}}},
    ]

    def __init__(self, connect=None):
        super().__init__(connect)
        # Reading the 160 names takes a second on the pedal (measured
        # 2026-09-22): read them once, not on every arrow press.
        self._names = None

    def _real(self):                     # pragma: no cover - needs the pedal
        return _Real()

    def read(self, target):
        return self._use(lambda c: c.volume() / 100)

    def write(self, target, value):
        v = round(max(0.0, min(1.0, value)) * 100)
        self._use(lambda c: c.set_volume(v))

    def scenes(self):
        if self._names is None:
            self._names = [n.strip() for n in self._use(lambda c: list(c.preset_names()))]
        return self._names

    def current_scene(self):
        return self._use(lambda c: c.current())

    def load_scene(self, index):
        names = self.scenes()
        self._use(lambda c: c.load_preset(index))
        return names[index]
