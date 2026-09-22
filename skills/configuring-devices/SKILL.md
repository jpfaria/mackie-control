---
name: configuring-devices
description: Use when putting a piece of gear on a control surface with mackie-control — writing or changing a rig profile YAML, choosing what a fader or a scene button touches, or adding a driver for gear the package does not know yet.
---

# Configuring a device

A profile says what each fader and button touches. Every line of it is a claim
about someone's gear, and a wrong claim does not look wrong: the fader moves,
the log says nothing, and the sound does not change. The whole job is refusing
to write a claim you have not checked.

## The loop, per fader

1. **Read the rig's own notes first.** The user has already written down what is
   plugged into what. Read it before asking them anything — `grep -rli <gear>
   ~/Documents/Obsidian/` and the rig's repo. Asking what they already wrote
   burns their patience and gets you a worse answer.
2. **Find candidate targets from the device**, not from a manual:
   `mackie devices PROFILE.yaml` for what is configured, and the driver's own
   listing for what exists.
3. **Prove the target moves.** Read it, write a different value, read it back,
   then put the original value back in the same breath.
4. **Prove it moves the thing on the label.** A parameter that accepts a write
   still may not be in the signal path the label names.
5. Only then write the line.

## Proving a target, safely

```python
from quantum_hd8.client import Client, WriteNotConfirmed
c = Client(); c.connect()
P = "line/ch19/trim"
before = c.state.get(P)                 # 1. what it is now
try:
    c.set_raw(P, 0.55)                  # 2. a different value
    print("moved to", c.state.get(P))
except WriteNotConfirmed:
    print(P, "is ignored by the device")
finally:
    c.set_raw(P, before)                # 3. always hand it back
```

Run on 2026-09-22 this printed `ignored` for `line/ch19/trim` and moved for
`line/ch1/trim`: the HD 8 has no trim on its ADAT channels, though the
parameter is in its table for all of them. Two faders in the user's profile had
been doing nothing for a day.

**Borrowed state comes back in the `finally`**, and in Ctrl-C too. Leaving gear
in a mode its normal use never selects costs the user an evening of hunting.

## What a bank is

One bank is one device. Its `driver:` is that device; `scenes:` is which of the
device's scenes matter, in the order the user wants to walk them. Left out, the
device's own list is used, in its own order.

```yaml
banks:
  - name: HD 8
    driver: hd8
    scenes: [MIXER-ON, SYN2-FRFR]        # tonight's four, not the gear's thirty
    faders:
      1: {driver: hd8, target: global/mainOutVolume, label: MAIN, group: out,
          mute: global/mute}
```

`scenes:` must name scenes the device actually reports — check against the
driver's own list before writing them down. A name that does not exist fails at
the press of a button, on stage.

## Quick reference

| Field | Write it when |
|---|---|
| `driver:` | always, on a bank that is one device |
| `scenes:` | the user wants a subset or a different order; otherwise leave out |
| `group: in`/`out` | always — solo only acts inside the group |
| `mute:` | the device has a real mute for that channel; without it M zeroes the value |
| `range: [lo, hi]` | the full travel can damage something (a preamp reaching +75 dB) |
| `takeover: false` | a jump costs nothing (a player's volume); never on a monitor bus |

## Common mistakes

- **Writing a target because it has the right name.** `line/ch19/trim` is
  spelled like a trim and is not one. Prove it.
- **Inventing a scene list.** A list computed from a naming scheme instead of
  read from the device is a guess with 300 entries.
- **Putting the user's rig in the package.** Setlists, channel names and mixer
  paths live in their YAML. A *driver* belongs in the repo; what they plugged
  into it does not.
- **A fader whose value cannot be read.** Takeover needs to read the current
  value; without one the first touch jumps. Say so out loud, in the profile,
  rather than leaving the user to find it with their hands.
- **Answering from the manual.** The SMC-Mixer ignores the Mackie Device Query
  and the HD 8 receives no MIDI at all; neither manual says so.

## Red flags

- "The parameter exists, so it works"
- "I'll write the profile and he can tell me if it does nothing"
- "The device probably names its patches A1-1, A1-2…"
- "I'll leave the gear in this mode, it's easier to test"

Every one of these means: go and measure it.
