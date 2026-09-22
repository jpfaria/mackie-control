# Devices and scenes on the surface — design

**Status:** implemented 2026-09-22 (commit `56c4c74`), except the skill,
which is being written under `superpowers:writing-skills`.

## The problem

A bank is a device, and a device has scenes. Today the surface reaches eight of
them: `R n` loads the n-th scene of the bank's driver, and that is all. João
wants "8×8 devices, and 8×8 scenes each" — 64 and 64 — with the surface always
telling him where he is, because a rig with two mistakes in it sounds like a
rig with none until he plays.

## Navigation

| Control | Does |
|---|---|
| Arrow ◀ / ▶ (note `62`/`63`) | previous / next **scene** of the current device — **loads it immediately** |
| Arrow ▲ / ▼ (note `60`/`61`) | previous / next **device** (bank) |
| Channel ◀ / ▶ (note `2E`/`2F`) | unchanged: pages banks |

Loading on the arrow press is deliberate: João asked for it (2026-09-22). It
means stepping from scene 1 to scene 5 loads four scenes on the way, which is
how a pedalboard behaves and what he expects.

Both arrow pairs stop at the ends: no wrap. Wrapping means one press too many
puts the rig somewhere it has never been.

## Where am I

The surface has 32 lamps and no more: four rows of eight (R, S, M, square).
The knob has none of its own — CC `30`-`37` and notes `20`-`27` light nothing
(measured 2026-09-22). So a number from 1 to 64 costs two rows: one for the row
of eight, one for the column.

| Lamps | Says |
|---|---|
| lamp under the knob (pitch bend) | the row of eight — the page |
| R row | column, when the **device** is what changed |
| S row | column, when the **scene** is what changed |

**Only the one that just changed is shown** (João, 2026-09-22): the R row is
shared, so it cannot carry two numbers at once. Pressing ▲/▼ shows the device,
pressing ◀/▶ shows the scene, and the display stays as it is until something
changes again.

Device 12 is `knob 2` + `R 4`. Scene 5 is `knob 1` + `S 5`.

This replaces the three blinks of the bank number, which said less and only
right after a change.

## The profile

A bank gains a `scenes:` list. Left out, the device's own list is used, in the
order the device gives — a driver already answers `scenes()`.

```yaml
banks:
  - name: HD 8
    driver: hd8               # the device this bank is
    scenes: [MIXER-ON, SYN2-FRFR, MK300-FRFR]   # optional: which, and in which order
    faders: {...}
```

`scenes:` is how "configurable per how the user works" happens: the device may
hold thirty presets of which four matter on a given night, and the profile is
where that choice lives — never the code.

A bank whose driver has no scenes (`mac`, `app`) simply has none: ◀/▶ do
nothing there and the R and S rows stay dark.

## `mackie devices`

A command that answers "what is configured, and what can it load", from the
profile plus the gear:

```
$ mackie devices my-rig.yaml
1  HD 8   (hd8)   8 faders   scenes: 1 MIXER-ON*  2 SYN2-FRFR  3 MK300-FRFR
2  Mac    (mac)   2 faders   no scenes
```

`*` marks the scene the device reports as loaded. With the gear unreachable it
prints what the profile says and one line stating the driver could not be
reached — it must be usable away from the rig.

## The skill

`.claude/skills/configuring-devices/SKILL.md`: how to take a rig the user
describes and turn it into a profile — which driver, what a bank is worth, how
to find a parameter's path, how to check a scene exists before writing it down.
It edits the user's YAML; it never edits this repo's code.

Written with `superpowers:writing-skills` (baseline with a subagent first), as
the global rules require.

## What this does not do

- No new physical control: everything above is buttons the surface already has.
- No scene editing from the surface: loading only. Saving a scene by accident
  is unrecoverable.
- No change to faders, takeover, mute, solo or the drivers.
