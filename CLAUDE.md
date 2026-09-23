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
Outputs in one bank, guitars in another, the computer in a third. Eight faders
of mixed subjects on one screen is what makes a profile unreadable, and paging
is a keypress.

**L and R are two faders when the gear has two parameters** — do not decide for
the user that a pair should be linked (2026-09-22: "eu quero poder controlar L
e R separadamente"). On the HD 8 there is no such pair to split: MAIN and both
headphone outs have one volume parameter each, and an aux send is a whole
stereo bus (`aux/ch(4+k)` is the ADAT k/k+1 pair, so `aux/ch10` is all of ADAT
11/12). Splitting L and R there has to happen further down the chain.

That last fact came from reading `quantum-hd8/docs/` **after** telling João his
FRFR fader was moving one side of a pair, which was wrong: `aux/ch9` is the ADAT
9/10 bus, a different destination. The rig's own repos answer these questions —
read them before making a claim about his rig, not after.

## After every push, update João's machine and restart the service
The bridge runs as a LaunchAgent (`mackie service install PROFILE`), not in a
terminal. A pushed change is not live until it is installed and the service
restarted, so every push here is followed by:
`~/.pyenv/versions/3.12.3/bin/pip install -q --force-reinstall --no-deps git+https://github.com/jpfaria/mackie-control && ~/.pyenv/versions/3.12.3/bin/mackie service restart`,
then `mackie service status` and a look at `~/Library/Logs/mackie-control.log`.
(2026-09-23: "qdo a gente alterar alguma coisa aqui, vc precisa atualizar a
app na minha maquina e reiniciar o servico".)
