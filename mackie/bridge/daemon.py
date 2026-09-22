"""The bridge loop: a Mackie surface in, drivers out.

Everything the surface cannot know lives here: which fader owns which target
(the profile), whether a fader may take over yet (the surface has no motor and
never reports its position), what "solo" means on a mixer with no solo bus, and
which LEDs to light back."""
from __future__ import annotations

import threading
import time

from .. import protocol as mackie
from .drivers import Unsupported, build

INTERVAL = 0.03      # s: a fader sends ~40 messages/s, so write only the last
NEAR = 0.02          # takeover tolerance, in 0..1
BLINKS = 3           # how many times the bank number blinks after a change
BLINK = 0.12         # s of each on and each off phase


class Bridge:
    def __init__(self, profile, send=None, drivers=None, log=print):
        self.profile = profile
        self.send = send or (lambda **kwargs: None)
        self.log = log
        self._drivers = drivers if drivers is not None else {}
        self.bank_index = 0
        self.soloed = None          # fader currently soloed, if any
        self.muted_before = {}      # mute state before a solo, per fader
        self.value_before = {}      # value of targets silenced without a mute
        self.scene_loaded = None    # fader whose scene was loaded last
        self.took_over = set()      # (bank, channel) already in control
        self.last_seen = {}         # last position seen per fader
        self.pending = {}
        self.lock = threading.Lock()

    # -- drivers ---------------------------------------------------------------
    def driver(self, name):
        if name not in self._drivers:
            self._drivers[name] = build(name)
        return self._drivers[name]

    def _read(self, dest):
        try:
            return self.driver(dest.driver).read(dest.target)
        except Exception:
            return None

    def _write(self, dest, value):
        try:
            self.driver(dest.driver).write(dest.target, value)
            return True
        except Exception as e:
            self.log(f"  !! {dest.label}: {e}")
            return False

    # -- state -----------------------------------------------------------------
    @property
    def bank(self):
        return self.profile.bank(self.bank_index)

    def destination(self, fader):
        """A global fader wins over the bank's: it is the one that is always
        there, whichever bank is selected."""
        return self.profile.globals.faders.get(fader) or self.bank.faders.get(fader)

    def step_bank(self, step):
        self.select_bank((self.bank_index + step) % len(self.profile.banks))

    def select_bank(self, i):
        if 0 <= i < len(self.profile.banks):
            self.bank_index = i
            self.took_over.clear()
            self.log(f"** bank {i + 1}/{len(self.profile.banks)}: {self.bank.name}")
            self.push_state()
            self.flash_bank()

    def flash_bank(self, sleep=None):
        """Flash the bank number without blocking the MIDI loop."""
        if sleep is None:
            threading.Thread(target=self._flash, args=(time.sleep,),
                             daemon=True).start()
        else:
            self._flash(sleep)

    def _flash(self, sleep):
        """Show which bank is now active, then get out of the way.

        The surface has no display and the banks are a list of any length, so
        the number is shown as a grid: the top row of a channel strip (the mute
        button, right under the knob) is the row, the square button at the
        bottom is the column. Eight by eight addresses 64 banks. It is a flash,
        not a state: `push_state` puts the real LEDs back right after."""
        row, column = divmod(self.bank_index, 8)
        if row > 7:                       # beyond 64 banks there is nothing to show
            return
        for _ in range(BLINKS):
            for aceso in (True, False):
                self.send(**mackie.led(mackie.MUTE + row, aceso))
                self.send(**mackie.led(mackie.SELECT + column, aceso))
                sleep(BLINK)
        self.push_state()                 # real LEDs come back

    def push_state(self):
        """Everything the surface can show: fader positions and LEDs."""
        for fader in range(1, 9):
            dest = self.destination(fader)
            value = self._read(dest) if dest else None
            # Only a fader with a destination AND a readable value gets a
            # position: sending one to an unmapped fader makes the surface
            # blink it forever, because nothing will ever align.
            if value is not None and self.profile.positions:
                self.send(**mackie.fader_position(fader - 1, value))
            self.send(**mackie.led(mackie.MUTE + fader - 1, self._is_muted(fader)))
            self.send(**mackie.led(mackie.SOLO + fader - 1, self.soloed == fader))
            self.send(**mackie.led(mackie.REC + fader - 1, self.scene_loaded == fader))
            # The square button only gets a LED when the profile gave it a job.
            # Banks page with the arrows and there can be any number of them, so
            # eight lamps cannot stand for "the active bank".
            if self.bank.buttons.get("select") == "bank":
                self.send(**mackie.led(mackie.SELECT + fader - 1,
                                       self.bank_index == fader - 1))
            else:
                self.send(**mackie.led(mackie.SELECT + fader - 1, False))

    def _is_muted(self, fader):
        dest = self.destination(fader)
        if dest is None:
            return False
        if dest.mute is None:
            return dest.target in self.value_before
        try:
            return float(self.driver(dest.driver).read(dest.mute)) >= 0.5
        except Exception:
            return False

    # -- faders ----------------------------------------------------------------
    def fader(self, channel, value):
        dest = self.destination(channel + 1)
        if dest is None:
            return
        key = (self.bank_index, channel)
        if key not in self.took_over:
            current = self._read(dest)
            previous = self.last_seen.get(key)
            crossed = previous is not None and (previous - current) * (value - current) < 0
            if current is None or abs(value - current) <= NEAR or crossed:
                self.took_over.add(key)
                self.log(f"  .. fader {channel + 1} ({dest.label}) took over")
            else:
                if previous is None:
                    self.log(f"  .. fader {channel + 1} ({dest.label}) is held: "
                             f"move it to {current:.2f} to take over (now at {value:.2f})")
                self.last_seen[key] = value
                return
        self.last_seen[key] = value
        with self.lock:
            self.pending[channel] = value

    def drain_forever(self):
        """Apply the last position of each fader. Runs in its own thread."""
        while True:
            time.sleep(INTERVAL)
            self.drain()

    def drain(self):
        with self.lock:
            batch, self.pending = self.pending, {}
        for channel, value in batch.items():
            dest = self.destination(channel + 1)
            if dest is not None and self._write(dest, value) and self.profile.positions:
                self.send(**mackie.fader_position(channel, value))   # aligns the LED

    # -- buttons ---------------------------------------------------------------
    def mute(self, fader):
        dest = self.destination(fader)
        if dest is None:
            return
        try:
            if dest.mute is not None:
                self.driver(dest.driver).toggle(dest.mute)
            elif dest.target in self.value_before:       # no mute: hand it back
                self.driver(dest.driver).write(dest.target, self.value_before.pop(dest.target))
            else:                                        # no mute: zero it
                self.value_before[dest.target] = self._read(dest) or 0.0
                self.driver(dest.driver).write(dest.target, 0.0)
        except Exception as e:
            self.log(f"  !! mute {dest.label}: {e}")
        self.push_state()

    def solo(self, fader):
        """Only this fader's destination plays -- within its own group."""
        target = self.destination(fader)
        if target is None:
            return
        todos = {**self.bank.faders, **self.profile.globals.faders}
        peers = [(n, d) for n, d in todos.items() if d.group == target.group]
        if self.soloed == fader:
            for n, dest in peers:
                if dest.mute is not None:
                    self._set_mute(dest, self.muted_before.get(n, False))
                elif dest.target in self.value_before:
                    self._write(dest, self.value_before.pop(dest.target))
            self.soloed, self.muted_before = None, {}
            self.log("  -> solo off")
        else:
            if self.soloed is None:
                self.muted_before = {n: self._is_muted(n) for n, _ in peers}
            for n, dest in peers:
                silence = n != fader
                if dest.mute is not None:
                    self._set_mute(dest, silence)
                elif silence:
                    self.value_before.setdefault(dest.target, self._read(dest) or 0.0)
                    self._write(dest, 0.0)
                elif dest.target in self.value_before:
                    self._write(dest, self.value_before.pop(dest.target))
            self.soloed = fader
            self.log(f"  -> solo on {target.label}")
        self.push_state()

    def _set_mute(self, dest, muted):
        """One refused write must not abort the rest of a solo."""
        try:
            drv = self.driver(dest.driver)
            if (float(drv.read(dest.mute)) >= 0.5) != muted:
                drv.toggle(dest.mute)
        except Exception as e:
            self.log(f"  !! mute {dest.label}: {e}")

    def scene(self, fader):
        dest = self.destination(fader)
        if dest is None:
            return
        try:
            name = self.driver(dest.driver).load_scene(fader - 1)
            self.scene_loaded = fader
            self.soloed, self.muted_before = None, {}
            self.took_over.clear()
            self.log(f"  -> scene {name}")
        except Unsupported as e:
            self.log(f"  !! scene: {e}")
        self.push_state()

    # -- input -----------------------------------------------------------------
    def on_midi(self, msg):
        event = mackie.decode(msg)
        if isinstance(event, mackie.Fader):
            self.fader(event.channel, event.value)
        elif isinstance(event, mackie.Button) and event.pressed:
            self.button(event)

    def bank_driver(self):
        """The driver a bank's own buttons belong to: the one most of its
        faders use. With a single driver per bank (the usual case) this is just
        that driver."""
        nomes = [d.driver for d in self.bank.faders.values()]
        return max(set(nomes), key=nomes.count) if nomes else None

    def default_button(self, kind):
        """What the bank's driver says this button does, if the profile did
        not say. A driver declares its own buttons in BUTTONS."""
        nome = self.bank_driver()
        if nome is None:
            return None
        try:
            drv = self.driver(nome)
        except Exception:
            return None
        comando = type(drv).BUTTONS.get(kind)
        if comando is None:
            return None
        alvo = next((d.target for d in self.bank.faders.values()
                     if d.driver == nome), None)
        return nome, alvo, comando

    def button(self, b):
        actions = self.bank.buttons
        if b.kind in ("bank_right", "arrow_right"):
            self.step_bank(+1)
        elif b.kind in ("bank_left", "arrow_left"):
            self.step_bank(-1)
        elif b.kind == "mute":
            self.mute(b.channel + 1)
        elif b.kind == "solo":
            self.solo(b.channel + 1)
        elif b.kind == "rec" and (actions.get("rec") == "scene"
                                  or ("rec" not in actions
                                      and (self.default_button("rec") or (None, None, None))[2] == "scene")):
            self.scene(b.channel + 1)
        elif b.kind == "select" and actions.get("select") == "bank":
            self.select_bank(b.channel)
        elif b.kind in self.profile.globals.transport:
            self.run_command(self.profile.globals.transport[b.kind], b.kind)
        elif b.kind in self.bank.transport:
            self.run_command(self.bank.transport[b.kind], b.kind)
        else:
            padrao = self.default_button(b.kind)
            if padrao is not None:
                nome, alvo, comando = padrao
                from .profile import Command
                self.run_command(Command(nome, alvo, comando), b.kind)

    def run_command(self, cmd, label):
        try:
            self.driver(cmd.driver).command(cmd.target, cmd.command)
            self.log(f"  -> {label}: {cmd.command}")
        except Exception as e:
            self.log(f"  !! {label}: {e}")
