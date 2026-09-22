"""A device's own banks.

The same gear has the same knobs in every rig, so the map of what a device is
worth belongs to its driver, not to each user's profile. A bank that names a
`driver:` and no faders is replaced by that driver's `DEFAULT_BANKS`; a bank
that writes its own faders is never touched."""
from __future__ import annotations

from dataclasses import replace

from .drivers import classes
from .profile import Bank, _destination


def _banks_of(bank: Bank) -> list[Bank]:
    if bank.driver is None or bank.faders or bank.encoders:
        return [bank]
    known = classes().get(bank.driver)
    padrao = getattr(known, "DEFAULT_BANKS", []) if known else []
    if not padrao:
        return [bank]
    if bank.default is not None:
        padrao = [b for b in padrao
                  if b["name"].upper().endswith(bank.default.upper())]
        if not padrao:
            nomes = ", ".join(b["name"] for b
                              in getattr(known, "DEFAULT_BANKS", []))
            raise SystemExit(f"{bank.driver} has no default bank "
                             f"{bank.default!r}; it has: {nomes}")
    return [replace(bank,
                    name=b.get("name", bank.name),
                    faders={int(k): _destination(v)
                            for k, v in (b.get("faders") or {}).items()})
            for b in padrao]


def expand(profile):
    """The profile as the bridge should see it, with every device's default
    banks in place."""
    banks = [b for bank in profile.banks for b in _banks_of(bank)]
    return replace(profile, banks=banks)
