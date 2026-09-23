"""Keep the bridge running as a macOS LaunchAgent.

Run from a terminal, the bridge dies with that terminal: on 2026-09-23 the
laptop was moved, the terminal went away, and the surface came back over
Bluetooth to a bridge that no longer existed. The bridge already survives the
surface going away (`bridge/run.py`); this makes it survive everything else --
it starts at login and launchd starts it again if it exits."""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "com.github.jpfaria.mackie-control"


def agent_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def log_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "Logs" / "mackie-control.log"


def plist(profile: str, python: str = sys.executable, home: Path | None = None,
          path: str | None = None) -> dict:
    """The agent runs this interpreter's `-m mackie`, not a `mackie` found on
    PATH: launchd's PATH is not the shell's, and a pyenv shim there would
    resolve to whatever Python happens to be global."""
    log = str(log_path(home))
    return {
        "Label": LABEL,
        "ProgramArguments": [python, "-m", "mackie", "bridge",
                             str(Path(profile).expanduser().resolve())],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "ProcessType": "Interactive",
        "StandardOutPath": log,
        "StandardErrorPath": log,
        "EnvironmentVariables": {
            "PATH": path or os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "PYTHONUNBUFFERED": "1",
        },
    }


def _domain() -> str:
    return f"gui/{os.getuid()}"


def install(profile: str, run=subprocess.run, home: Path | None = None,
            python: str = sys.executable, log=print) -> Path:
    if not Path(profile).expanduser().is_file():
        raise SystemExit(f"no profile at {profile}")
    dest = agent_path(home)
    dest.parent.mkdir(parents=True, exist_ok=True)
    log_path(home).parent.mkdir(parents=True, exist_ok=True)
    # Replacing a loaded agent needs it out first, or launchd keeps the old one.
    run(["launchctl", "bootout", f"{_domain()}/{LABEL}"], capture_output=True)
    dest.write_bytes(plistlib.dumps(plist(profile, python=python, home=home)))
    run(["launchctl", "bootstrap", _domain(), str(dest)], check=True)
    log(f"installed {dest}; log in {log_path(home)}")
    return dest


def uninstall(run=subprocess.run, home: Path | None = None, log=print) -> None:
    run(["launchctl", "bootout", f"{_domain()}/{LABEL}"], capture_output=True)
    dest = agent_path(home)
    if dest.exists():
        dest.unlink()
    log(f"removed {dest}")


def status(run=subprocess.run, home: Path | None = None) -> str:
    if not agent_path(home).exists():
        return "not installed"
    r = run(["launchctl", "print", f"{_domain()}/{LABEL}"],
            capture_output=True, text=True)
    if r.returncode != 0:
        return "installed, not loaded"
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("pid ="):
            return f"running ({line})"
    return "installed, not running"
