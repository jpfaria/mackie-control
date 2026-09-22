"""Hotone Ampero II Stage, through the `ampero2` library (USB SysEx).

The patch volume can be written but not read -- the protocol has no query for
it. So `read` answers None until the driver has written a value (the bridge
then applies a fader at once instead of waiting for takeover), and forgets it
when a patch loads, because the volume belongs to the patch. The patches (300)
are its scenes."""
from __future__ import annotations

from ._pedal import Pedal


class _Real:                             # pragma: no cover - needs the pedal
    def __init__(self):
        from ampero2.device import Ampero
        self._dev = Ampero()

    def set_volume(self, v):
        from ampero2.protocol import msg_set_patch_volume
        self._dev.send(msg_set_patch_volume(v))

    def patch_names(self):
        from ampero2.patch import decode_reply, patch_names
        from ampero2.protocol import msg_query_inventory
        return patch_names(decode_reply(
            self._dev.request_dump(msg_query_inventory("patches"))))

    def load_patch(self, i):
        from ampero2.protocol import msg_load_patch
        self._dev.send(msg_load_patch(i))


class Ampero2(Pedal):
    name = "ampero2"
    LABEL = "Ampero II"
    BUTTONS = {"rec": "scene"}
    DEFAULT_BANKS = [
        {"name": "AMPERO",
         "faders": {1: {"driver": "ampero2", "target": "volume",
                        "label": "AMPERO VOL", "group": "out"}}},
    ]

    def __init__(self, connect=None):
        super().__init__(connect)
        self._written = None
        self._names = None               # 300 names: ask once, not per press

    def _real(self):                     # pragma: no cover - needs the pedal
        return _Real()

    def read(self, target):
        return self._written

    def write(self, target, value):
        v = round(max(0.0, min(1.0, value)) * 100)
        self._use(lambda c: c.set_volume(v))
        self._written = v / 100

    def scenes(self):
        if self._names is None:
            self._names = self._use(lambda c: list(c.patch_names()))
        return self._names

    def load_scene(self, index):
        names = self.scenes()
        self._use(lambda c: c.load_patch(index))
        self._written = None
        return names[index]
