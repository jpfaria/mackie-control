"""Where the rig was when the bridge last stopped.

The bridge is restarted all the time, and the HD 8 cannot say which scene it
has loaded (measured 2026-09-22), so without this every restart forgot the
device on screen and made the first arrow start from scene 1. What is kept is
only a *position*: restoring it loads nothing and changes nothing on the gear.

Scenes are keyed by bank name, not by position, so adding a bank to the YAML
does not hand one device's scene to another. The file is plain JSON."""
from __future__ import annotations

import json
import os
from pathlib import Path


def default_path(profile_path: str) -> Path:
    """One state file per profile, under the user's state directory -- never
    beside the profile, which lives in a git repo."""
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "mackie-control" / (Path(profile_path).stem + ".json")


class State:
    def __init__(self, path):
        self.path = Path(path) if path is not None else None

    def load(self) -> dict:
        if self.path is None:
            return {}
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}                    # missing or broken: a fresh start
        return data if isinstance(data, dict) else {}

    def save(self, device: str, scenes: dict[str, int]) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"device": device, "scenes": scenes},
                                      indent=2, ensure_ascii=False))
            tmp.replace(self.path)
        except OSError:
            pass                         # losing a position must not stop the rig
