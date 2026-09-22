# mackie-control

A **Mackie Control surface** — faders, encoders and buttons — driving gear that
has nothing to do with Mackie: an audio interface, the system volume, a player.
The surface speaks a standard protocol; a **profile** says what each fader and
button touches; one **driver** per device does the writing.

```
surface (Mackie)  ->  Bridge  ->  driver  ->  gear
```

Built because a PreSonus **Quantum HD 8 does not receive MIDI**: a sweep of CC,
pitch bend and notes on both of its CoreMIDI ports changed none of its 1419
parameters (measured 2026-09-20). A MIDI fader can never reach it directly — the
computer has to translate.

## Install

```bash
pip install git+https://github.com/jpfaria/mackie-control
pip install 'mackie-control[hd8] @ git+https://github.com/jpfaria/mackie-control'   # with the HD 8 driver
```

**Upgrading needs `--force-reinstall`** unless the version in `pyproject.toml`
changed: `pip install -U` compares version strings, not commits, so it clones
the new commit, sees the same version and installs nothing — silently leaving
the old code in place (2026-09-22: a fixed bug came back twice this way).

```bash
pip install --force-reinstall --no-deps git+https://github.com/jpfaria/mackie-control
```

## Use

```bash
mackie ports                         # MIDI ports visible right now
mackie surfaces                      # surfaces this package knows
mackie watch 30                      # print what the surface sends, decoded
mackie bridge my-rig.yaml            # run the bridge
```

## The profile

```yaml
surface: smc-mixer

global:                 # always in reach, whichever bank is selected
  encoders:
    1: {driver: app, target: Spotify, label: Spotify}   # endless knob: no takeover
  transport:
    play: {driver: app, target: Spotify, command: playpause}

banks:
  - name: HD 8
    faders:
      1: {driver: hd8, target: global/mainOutVolume, label: MAIN,    group: out, mute: global/mute}
      2: {driver: hd8, target: aux/ch10/volume,      label: FRFR,    group: out, mute: aux/ch10/mute}
      3: {driver: hd8, target: global/phones1_volume, label: PHONES 1, group: out}
      5: {driver: hd8, target: line/ch1/volume,      label: GUITAR 1, group: in,  mute: line/ch1/mute}
    buttons: {rec: scene, select: bank}
  - name: Mac
    faders:
      1: {driver: mac, label: System volume}
      2: {driver: app, target: Spotify, label: Spotify}
```

A different rig is a different file. Nothing about a rig goes into the code.

## What each field does

| Field | Effect |
|---|---|
| `driver` | who writes: `hd8`, `mac`, `app` |
| `target` | whatever that driver understands (a mixer path, an app name) |
| `label` | the name that shows up in the log |
| `group` | `in` or `out` — **solo only acts inside the group** |
| `mute` | the device's own mute parameter; without one, M zeroes the value and gives it back |
| `range` | `[low, high]` in 0..1 — the fader's whole travel stays inside it (a preamp reaching +75 dB is a blown take) |
| `takeover` | `false` waives the takeover for that destination |

Faders jump to a position, so they wait for **takeover**: a fader starts writing
only once it crosses the value already in the gear. Encoders are endless knobs —
they nudge, so they need none of that.

| Block | What it holds |
|---|---|
| `banks:` | the list of banks; page through them with Channel ◀ / ▶ or the arrows, any number of them |
| `global:` | faders, encoders and transport that work in **every** bank (a global fader wins over the bank's) |
| `positions: true` | send fader values back, so the surface blinks a channel until its fader matches (off by default) |

## Documentation

- [`docs/bridge.md`](docs/bridge.md) — the bridge, the drivers, the profile, the feedback
- [`docs/smc-mixer.md`](docs/smc-mixer.md) — the M-VAVE SMC-Mixer, as measured
- [`docs/protocol.md`](docs/protocol.md) — Mackie Control as this repo uses it
- [`docs/adding-a-surface.md`](docs/adding-a-surface.md) — mapping a new controller
- [`docs/adding-a-driver.md`](docs/adding-a-driver.md) — controlling new gear

## Tests

```bash
python3 -m pytest -q
```

71 tests, no hardware: drivers and surfaces go in by injection.
