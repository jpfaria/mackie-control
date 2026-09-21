# mackie-control

A **Mackie Control surface** — faders, encoders and buttons — driving gear that
has nothing to do with Mackie: an audio interface, the system volume, a player.
The surface speaks a standard protocol; a **profile** says what each fader and
button touches; one **driver** per device does the writing.

```
superficie (Mackie)  ->  Bridge  ->  driver  ->  aparelho
```

Built because a PreSonus **Quantum HD 8 does not receive MIDI**: a sweep of CC,
pitch bend and notes on both of its CoreMIDI ports changed none of its 1419
parameters (measured 2026-09-20). A MIDI fader could never reach it directly —
the computer has to translate.

## Install

```bash
pip install git+https://github.com/jpfaria/mackie-control
pip install 'mackie-control[hd8] @ git+https://github.com/jpfaria/mackie-control'   # com o driver da HD 8
```

## Use

```bash
mackie ports                         # portas MIDI visiveis agora
mackie surfaces                      # superficies conhecidas
mackie watch 30                      # imprime o que a superficie manda, decodificado
mackie bridge meu-rig.yaml           # roda a ponte
```

## The profile

```yaml
surface: smc-mixer
banks:
  - name: HD 8
    faders:
      1: {driver: hd8, target: global/mainOutVolume, label: MAIN,    group: out, mute: global/mute}
      2: {driver: hd8, target: aux/ch10/volume,      label: FRFR,    group: out, mute: aux/ch10/mute}
      3: {driver: hd8, target: global/phones1_volume, label: FONE 1, group: out}
      5: {driver: hd8, target: line/ch1/volume,      label: GUITA 1, group: in,  mute: line/ch1/mute}
    buttons: {rec: scene, select: bank}
  - name: Mac
    faders:
      1: {driver: mac, label: Volume do Mac}
      2: {driver: app, target: Spotify, label: Spotify}
```

Rig novo = arquivo novo. Nada do rig entra no código.

## O que cada campo faz

| Campo | Efeito |
|---|---|
| `driver` | quem escreve: `hd8`, `mac`, `app` |
| `target` | o que esse driver entende (um path do mixer, o nome do app) |
| `label` | o nome que aparece no log |
| `group` | `in` ou `out` — **o solo só age dentro do grupo** |
| `mute` | parâmetro de mute do aparelho; sem ele, o M zera o valor e devolve depois |

## Documentação

- [`docs/bridge.md`](docs/bridge.md) — a ponte, os drivers, o perfil, o feedback
- [`docs/smc-mixer.md`](docs/smc-mixer.md) — o M-VAVE SMC-Mixer, medido
- [`docs/protocol.md`](docs/protocol.md) — Mackie Control como este repo o usa
- [`docs/adding-a-surface.md`](docs/adding-a-surface.md) — mapear um controlador novo
- [`docs/adding-a-driver.md`](docs/adding-a-driver.md) — controlar um aparelho novo

## Testes

```bash
python3 -m pytest -q
```

36 testes, sem hardware: os drivers e a superfície entram por injeção.
