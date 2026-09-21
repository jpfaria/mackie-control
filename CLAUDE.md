# mackie-control

## Toda mudança é commitada E empurrada
Qualquer mudança aqui termina com `git commit` + `git push` no `origin/main` no
mesmo turno. O jpfaria instala por `pip install git+https://github.com/jpfaria/mackie-control`;
commit parado na máquina não existe para ele nem para as outras sessões.
Rodar `python3 -m pytest -q` e conferir o código de saída antes de commitar.

## O que este repo é — e o que ele não é
É a **superfície** (Mackie) e a **ponte**. Não é um repo de um aparelho: nada do
rig de ninguém entra no código. Destino de fader, nome de canal e path de mixer
moram no **perfil YAML do usuário**, fora daqui.
**Por quê:** a primeira versão desta ponte nasceu dentro do repo do rig do
jpfaria, com `line/ch1/volume` cravado no meio do código; em 21/09 ela teve que
ser movida duas vezes de casa por isso.

## Protocolo se mede, não se lembra
Nota, CC e comportamento de aparelho entram aqui **medidos**, com data, e a
medição vai para `docs/`. Manual de fabricante é ponto de partida, não prova —
o SMC-Mixer, por exemplo, não responde ao Device Query do Mackie, coisa que
nenhum manual diz.

## Driver que falha não derruba nada
Um parâmetro que o aparelho recusa vira `Unsupported` + aviso no log, e o resto
da operação segue. Em 21/09 uma escrita recusada (`line/ch20/mute`) abortava o
solo inteiro no meio, deixando o mixer em estado quebrado e o botão sem desfazer.

## Teste sem hardware
Driver e cliente entram por injeção (`HD8(client=...)`), e o perfil é dado.
Nenhum teste deste repo pode exigir aparelho ligado.
