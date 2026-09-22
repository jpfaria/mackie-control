"""What the two USB pedals have in common: they are often unplugged.

A pedal that is not connected must not bring the bridge down, and must be
picked up again once it is plugged in -- so the connection is opened on first
use, dropped on any failure, and tried again on the next operation."""
from __future__ import annotations

from . import Driver, Unsupported


class Pedal(Driver):
    LABEL = "pedal"

    def __init__(self, connect=None):
        self._connect = connect or self._real
        self._client = None

    def _real(self):                     # pragma: no cover - needs the pedal
        raise NotImplementedError

    def _use(self, operation):
        if self._client is None:
            try:
                self._client = self._connect()
            except Exception as e:
                raise Unsupported(f"{self.LABEL} is not connected ({e})") from e
        try:
            return operation(self._client)
        except Unsupported:
            raise
        except Exception as e:
            self._client = None          # try a fresh connection next time
            raise Unsupported(f"{self.LABEL}: {e}") from e
