# OpenRig bank (idea, 2026-09-29)

With the HD 8 mixer in Bypass, the HD 8 only exposes MAIN and the two phones
volumes; the aux buses (FRFR = `aux/ch10`, SYN-5050 = `aux/ch2`) ignore writes.
The rig profile's HD 8 bank still holds MAIN, FRFR, SYN 5050, FONE 1, FONE 2:
FRFR and SYN 5050 are for the analog scenes (mixer on), where they work (João,
2026-09-29).

Next: a bank of its own for OpenRig, where faders drive the level OpenRig sends
to each output (FRFR, SYN-5050, ...). Needs an `openrig` driver talking to the
OpenRig MCP (`http://127.0.0.1:4123`). Not designed yet.
