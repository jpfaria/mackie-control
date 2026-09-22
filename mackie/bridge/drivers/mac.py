"""macOS volume: the system output, and one application's own volume."""
from __future__ import annotations

import subprocess

from . import Driver, Unsupported


def _osascript(script: str) -> str:
    out = subprocess.run(["osascript", "-e", script],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


class MacVolume(Driver):
    """System output volume.

    Only works when the default output is a device macOS controls. With an
    interface like the Quantum HD 8 selected, AppleScript answers
    "missing value" for output volume -- the volume lives in the interface,
    not in the OS -- and this driver says so instead of guessing."""
    name = "mac"

    _NO_SYSTEM_VOLUME = ("the Mac's default output has no system-controlled "
                         "volume (an audio interface is selected)")

    def read(self, target=None):
        raw = _osascript("output volume of (get volume settings)")
        if raw == "missing value":
            raise Unsupported(self._NO_SYSTEM_VOLUME)
        return int(raw) / 100

    def write(self, target, value):
        self.read()                      # fail early, with the right reason
        _osascript(f"set volume output volume {round(value * 100)}")

    def toggle(self, target=None):
        raw = _osascript("output muted of (get volume settings)")
        if raw == "missing value":
            raise Unsupported(self._NO_SYSTEM_VOLUME)
        muted = raw == "true"
        _osascript(f"set volume {'without' if muted else 'with'} output muted")
        return not muted


class AppVolume(Driver):
    """target = the application name, e.g. "Spotify"."""
    name = "app"
    BUTTONS = {"play": "playpause", "stop": "pause",
               "forward": "next track", "rewind": "previous track"}

    def read(self, target):
        try:
            return int(_osascript(f'tell application "{target}" to sound volume')) / 100
        except subprocess.CalledProcessError as e:
            raise Unsupported(f"{target} did not answer: {e}") from e

    def write(self, target, value):
        _osascript(f'tell application "{target}" to set sound volume to {round(value * 100)}')

    def toggle(self, target):
        return self.command(target, "playpause")

    def playing(self, target):
        """None while the app is closed -- asking a closed app about its
        player would launch it, which is not what a lamp is worth."""
        try:
            if _osascript(f'application "{target}" is running').strip() != "true":
                return None
            estado = _osascript(f'tell application "{target}" to player state')
        except subprocess.CalledProcessError:
            return None
        return estado.strip() == "playing"

    def command(self, target, name):
        """Any AppleScript command the app understands: playpause, pause,
        next track, previous track..."""
        try:
            _osascript(f'tell application "{target}" to {name}')
        except subprocess.CalledProcessError as e:
            raise Unsupported(f"{target} refused {name!r}: {e}") from e
        return True
