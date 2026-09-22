# mackie-control

## Every change is committed AND pushed
Any change here ends with `git commit` + `git push` to `origin/main` in the same
turn. João installs this with `pip install git+https://github.com/jpfaria/mackie-control`;
an unpushed commit does not exist for him or for his other sessions. Run
`python3 -m pytest -q` and check the exit code before committing.

## What this repo is — and is not
It is the **surface** (Mackie) and the **bridge**. It is not a repo about one
piece of gear, and **nobody's rig belongs in the code**: fader destinations,
channel names and mixer paths live in the user's **YAML profile**, outside this
repo.
**Why:** this bridge was born inside João's rig repo with `line/ch1/volume`
hardcoded in the middle of it, and on 2026-09-21 it had to move house twice
because of that.

## Protocol is measured, never remembered
Notes, CCs and device behaviour land here **measured**, with the date, and the
measurement goes into `docs/`. A manufacturer's manual is a starting point, not
proof — the SMC-Mixer, for one, does not answer the Mackie Device Query, which
no manual mentions.

## A failing driver brings nothing down
A parameter the device refuses becomes `Unsupported` plus a line in the log, and
the rest of the operation continues. On 2026-09-21 one refused write
(`line/ch20/mute`) aborted a whole solo halfway through, leaving the mixer in a
broken state and the button unable to undo it.

## Tests run without hardware
Drivers and clients go in by injection (`HD8(client=...)`), and the profile is
data. No test in this repo may require a device to be plugged in.

## Language
Code, comments, docs and log messages are in **English**. João reads Portuguese
in chat, not in a public repo.

## Answers are short
Four lines is the ceiling for an answer in chat; a decision question is one
line of fact plus one line per option. Findings, measurements and reasoning go
into `docs/`, never into the reply. João stops reading long answers, so a long
answer buries the one line that mattered (2026-09-22: "seja simples na
resposta, nao vou ler um texto do tamanho de um livro").

## A bank is one subject
One fader per thing, and never two faders for the L and R of the same pair —
the HD 8 links them. Eight faders of mixed subjects on one screen is what makes
a profile unreadable: outputs in one bank, guitars in another, the computer in
a third. Paging is a keypress.
