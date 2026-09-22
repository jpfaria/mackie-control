"""`mackie devices`: what is configured, and what it can load.

Answers from the profile first and the gear second, so it works away from the
rig: an unreachable device still lists the scenes the profile named, plus one
line saying the driver did not answer."""
from __future__ import annotations


def _scenes(bank, drivers, unreachable):
    """The profile's list when it has one, otherwise the device's. The device
    is asked either way: that is also how we find out it is not there, which
    is worth a line even when the profile could answer alone."""
    name = bank.driver or _main_driver(bank)
    from_gear = []
    if name is not None:
        try:
            from_gear = list(drivers[name].scenes())
        except Exception as e:
            unreachable.append(f"   {name}: could not be reached ({e})")
    return list(bank.scenes) if bank.scenes else from_gear


def _main_driver(bank):
    names = [d.driver for d in bank.faders.values()]
    return max(set(names), key=names.count) if names else None


def describe(profile, drivers=None) -> list[str]:
    drivers = drivers if drivers is not None else {}
    lines, unreachable = [], []
    for i, bank in enumerate(profile.banks, start=1):
        driver = bank.driver or _main_driver(bank) or "-"
        scenes = _scenes(bank, drivers, unreachable)
        shown = ("scenes: " + "  ".join(f"{n} {s}" for n, s in enumerate(scenes, start=1))
                 if scenes else "no scenes")
        lines.append(f"{i}  {bank.name:<8} ({driver})   "
                     f"{len(bank.faders)} faders   {shown}")
    return lines + unreachable
