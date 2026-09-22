# Bridge: a surface driving other gear

`mackie bridge PROFILE.yaml` reads a control surface (today the SMC-Mixer) and
writes wherever the profile says — the surface never knows what it controls.

```
surface (Mackie)  ->  Bridge  ->  driver  ->  gear
```

## Drivers

| Driver | Talks to |
|---|---|
| `hd8` | PreSonus Quantum HD 8, through the `quantum-hd8` library (UCNet). The HD 8 **does not receive MIDI**: a sweep of CC, pitch bend and notes on both of its ports changed none of its 1419 parameters (2026-09-20). |
| `mac` | macOS output volume. Unsupported when the default output is an audio interface — AppleScript answers `missing value`, because the volume lives in the interface. |
| `app` | One application's own volume (`Spotify`, …). |

A driver that cannot do something raises `Unsupported`; the bridge logs it and
carries on. One channel the device refuses must never abort a solo — that bug
cost an evening on 2026-09-21.

### Losing the gear and getting it back

Switching the HD 8 off and on again kills the UCNet session, and the library
does not notice: afterwards every write raises `OSError: Bad file descriptor`
while reads keep answering from a **stale cache**, so the bridge looks alive
and moves nothing (measured 2026-09-22). The `hd8` driver therefore reconnects
**once per operation** and retries it; if `ucdaemon` still refuses, that one
operation becomes `Unsupported` and the bridge carries on. Power-cycling the
interface no longer means restarting the bridge.

## Profile

```yaml
surface: smc-mixer
banks:
  - name: HD 8
    faders:
      1: {driver: hd8, target: global/mainOutVolume, label: MAIN, group: out, mute: global/mute}
      5: {driver: hd8, target: line/ch1/volume, label: GUITAR 1, group: in, mute: line/ch1/mute}
    buttons: {rec: scene, select: bank}
```

- `group` (`in`/`out`) is what keeps **solo** honest: soloing an input mutes the
  other inputs and leaves the outputs alone.
- A fader **without** `mute:` is silenced by zeroing its own value, which is
  remembered and handed back — the HD 8 has no mute for its headphone outputs.
- **Banks always page with Channel ◀/▶ and with the arrows ◀/▶.** That is the
  default and needs no configuration.
- `rec: scene` makes R n load the n-th scene of **the same list the arrows
  page** — the bank's `scenes:` when it has one, the device's own order
  otherwise. You rarely
  need to write it: **each driver declares the buttons it can use** (`hd8` →
  R = scene; `app` → play, stop, next, previous), and the bridge falls back to
  that. The profile only has to speak up when it wants something different.
- `select: bank` is optional: it makes the square button n jump straight to bank
  n. Left out (the default), the square buttons do nothing.

## Global faders and transport

A top-level `global:` block is a bank that is always in reach: its faders and
its transport work whichever bank is selected, and a global fader wins over the
bank's own.

```yaml
global:
  encoders:
    1: {driver: app, target: Spotify, label: Spotify}   # endless knob: no takeover
  transport:
    play: {driver: app, target: Spotify, command: playpause}
```

An **encoder** is an endless knob: it nudges its destination by a step per
detent instead of jumping to a position, so it needs no takeover and never
fights with where the control physically sits.

Controlling the music has nothing to do with which set of faders you are on —
without this, play does nothing while you are looking at the mixer bank.

## Devices and scenes

A bank is a device. The arrows move through both:

| Control | Does |
|---|---|
| ◀ / ▶ (notes `62`/`63`) | previous / next **scene** — loads it on the press |
| ▲ / ▼ (notes `60`/`61`) | previous / next **device** |
| Channel ◀ / ▶ | pages devices too, unchanged |

Neither wraps: one press too many must not put the rig somewhere it was
walking away from.

```yaml
banks:
  - name: HD 8
    driver: hd8                        # the device this bank is
    scenes: [MIXER-ON, SYN2-FRFR]      # optional: which, and in which order
```

Without `scenes:` the device's own list is used, in the order it reports. With
it, the profile chooses — the gear may hold thirty presets of which four matter
tonight, and that choice belongs to the user, never to the code.

**Where am I**: a number up to 64 is a row and a column. The **lamp under the
knob** is the row — it is the fader-position lamp, so the row is shown by a
pitch bend on that channel, and the flash ends by handing that channel back its
last known position, which is what stops it blinking. The column says which
number it is: **R for the device** (which resource), **S for the scene**. Only what just changed is
shown — the R row cannot carry two numbers at once — and the real mute and solo
LEDs come straight back after the flash.

`mackie devices PROFILE.yaml` prints the same thing in words, and works with
the gear switched off:

```
1  HD 8     (hd8)   8 faders   scenes: 1 ELEMENT  2 MIXER-ON  3 MK300-FRFR
2  Mac      (mac)   2 faders   no scenes
```

## Losing the surface and getting it back

Switching the surface off takes its port out of CoreMIDI **without any error
reaching the reader**: nothing is raised, nothing is logged, and the bridge
stays alive and silent forever (measured 2026-09-22). The loop therefore checks
the port list once a second instead of waiting for an exception, closes the dead
ports, and reopens the surface when it comes back — re-arming takeover and
pushing the LEDs, because the faders may have been moved while it was away.

```
** the surface is back (SINCO SMC-Mixer-Master)
```

The same device is named differently depending on how it is connected —
`SINCO SMC-Mixer-Master` over USB, `SMC-Mixer Bluetooth` over BLE — so a surface
carries several `port_hints`, tried in order.

## Takeover

The surface has no motors and cannot report where its faders are, so the bridge
never applies a fader until it **crosses the current value** (or starts within
2% of it). Without that, touching a fader would jump the volume to wherever the
knob happened to be sitting. Changing banks arms takeover again.

### Range

`range: [low, high]` keeps the whole fader travel inside a stretch of the
parameter. A preamp reaches +75 dB, so a fader at the top with no limit is a
blown take; `range: [0.2, 0.5]` makes the fader sweep only that part, and the
value is read back on the fader's own scale.

A destination can waive takeover with `takeover: false` — right for a player's own
volume, where a jump costs nothing, and wrong for a monitor bus.

## Feedback

On every bank change, scene load, mute and solo the bridge pushes state back:
the LEDs for mute, solo and the loaded scene (R), plus three blinks of the bank
number — the mute row is the row, the square button is the column, so 8×8
addresses 64 banks.

**Fader positions are not sent by default.** Sending one makes the surface blink
that channel's LED until the physical fader matches, which is a useful
out-of-sync sign and an irritation if you do not plan to chase it. Turn it on
with a top-level `positions: true` in the profile.

## Examples

| File | What it shows |
|---|---|
| [`examples/minimal.yaml`](../examples/minimal.yaml) | one fader on the system volume — the smallest useful profile |
| [`examples/quantum-hd8.yaml`](../examples/quantum-hd8.yaml) | a full desk: outputs, inputs, mutes, scenes on the R buttons, a second bank for the computer |

```bash
mackie bridge examples/minimal.yaml
```

## Where things live

| Question | File |
|---|---|
| What does the surface send? | [`protocol.md`](protocol.md), [`smc-mixer.md`](smc-mixer.md) |
| How do I map a new controller? | [`adding-a-surface.md`](adding-a-surface.md) |
| How do I control new gear? | [`adding-a-driver.md`](adding-a-driver.md) |
| What can a profile say? | this file, plus [`../examples/`](../examples/) |
| Why is it built this way? | [`../CLAUDE.md`](../CLAUDE.md) — the rules that came out of real bugs |

Everything in these docs was measured on hardware, with the date. When a
measurement contradicts a manual, the measurement wins and the doc says so.
