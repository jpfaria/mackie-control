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
- `rec: scene` makes R n load the n-th scene of that fader's driver. You rarely
  need to write it: **each driver declares the buttons it can use** (`hd8` →
  R = scene; `app` → play, stop, next, previous), and the bridge falls back to
  that. The profile only has to speak up when it wants something different.
- `select: bank` is optional: it makes the square button n jump straight to bank
  n. Left out (the default), the square buttons do nothing.

## Takeover

The surface has no motors and cannot report where its faders are, so the bridge
never applies a fader until it **crosses the current value** (or starts within
2% of it). Without that, touching a fader would jump the volume to wherever the
knob happened to be sitting. Changing banks arms takeover again.

## Feedback

On every bank change, scene load, mute and solo the bridge pushes state back:
each fader's real value (Pitch Bend) and the LEDs for mute, solo, the loaded
scene (R) and the active bank (the square). A fader LED blinks while the
physical position disagrees with the value — that blink is information, not a
fault.

## Examples

| File | What it shows |
|---|---|
| [`examples/minimal.yaml`](../examples/minimal.yaml) | one fader on the system volume — the smallest useful profile |
| [`examples/quantum-hd8.yaml`](../examples/quantum-hd8.yaml) | a full desk: outputs, inputs, mutes, scenes on the R buttons, a second bank for the computer |

```bash
mackie bridge examples/minimal.yaml
```
