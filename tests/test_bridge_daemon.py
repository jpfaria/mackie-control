import mido
import pytest

from mackie import protocol as mackie
from mackie.bridge import daemon, profile
from mackie.bridge.drivers import Driver, Unsupported


class FakeDriver(Driver):
    name = "fake"

    def __init__(self):
        self.values = {"main": 0.5, "phones": 0.4, "g1": 0.2, "g2": 0.8,
                       "main/mute": 0.0, "g1/mute": 0.0, "g2/mute": 0.0}
        self.loaded = None

    def read(self, target):
        return self.values[target]

    def write(self, target, value):
        self.values[target] = value

    def toggle(self, target):
        new = 0.0 if self.values[target] >= 0.5 else 1.0
        self.values[target] = new
        return new >= 0.5

    def scenes(self):
        return ["ONE", "TWO"]

    def load_scene(self, index):
        if index >= 2:
            raise Unsupported("no such scene")
        self.loaded = self.scenes()[index]
        return self.loaded


PROFILE = {"banks": [
    {"name": "rig", "faders": {
        1: {"driver": "fake", "target": "main", "label": "MAIN", "group": "out",
            "mute": "main/mute"},
        2: {"driver": "fake", "target": "phones", "label": "PHONES", "group": "out"},
        5: {"driver": "fake", "target": "g1", "label": "G1", "group": "in",
            "mute": "g1/mute"},
        6: {"driver": "fake", "target": "g2", "label": "G2", "group": "in",
            "mute": "g2/mute"}}},
    {"name": "mac", "faders": {1: {"driver": "fake", "target": "main"}}},
]}


@pytest.fixture
def bridge():
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(PROFILE), send=lambda **k: None,
                      drivers={"fake": fake}, log=lambda *a: None)
    return b, fake


def test_a_fader_far_from_the_value_writes_nothing(bridge):
    b, fake = bridge
    b.fader(0, 0.9)                        # main sits at 0.5
    b.drain()
    assert fake.values["main"] == 0.5


def test_a_fader_takes_over_when_it_crosses_the_value(bridge):
    b, fake = bridge
    b.fader(0, 0.9)
    b.fader(0, 0.1)                        # crossed 0.5
    b.drain()
    assert fake.values["main"] == 0.1


def test_a_fader_already_near_takes_over_at_once(bridge):
    b, fake = bridge
    b.fader(0, 0.51)
    b.drain()
    assert fake.values["main"] == 0.51


def test_drain_applies_only_the_last_position(bridge):
    b, fake = bridge
    b.fader(0, 0.5)
    for v in (0.6, 0.7, 0.8):
        b.fader(0, v)
    b.drain()
    assert fake.values["main"] == 0.8


def test_solo_mutes_its_group_and_gives_it_back(bridge):
    b, fake = bridge
    b.solo(5)
    assert fake.values["g1/mute"] == 0.0 and fake.values["g2/mute"] == 1.0
    assert fake.values["main/mute"] == 0.0     # outputs stay out of an input solo
    b.solo(5)
    assert fake.values["g2/mute"] == 0.0


def test_solo_on_an_output_zeroes_whoever_has_no_mute(bridge):
    b, fake = bridge
    b.solo(1)
    assert fake.values["phones"] == 0.0
    b.solo(1)
    assert fake.values["phones"] == 0.4        # handed back as it was


def test_mute_without_a_parameter_zeroes_and_gives_back(bridge):
    b, fake = bridge
    b.mute(2)
    assert fake.values["phones"] == 0.0
    b.mute(2)
    assert fake.values["phones"] == 0.4


def test_bank_buttons(bridge):
    b, _ = bridge
    b.on_midi(mido.Message("note_on", note=mackie.BANK_RIGHT, velocity=127))
    assert b.bank.name == "mac"
    b.on_midi(mido.Message("note_on", note=mackie.ARROW_LEFT, velocity=127))
    assert b.bank.name == "rig"
    b.on_midi(mido.Message("note_on", note=mackie.SELECT + 1, velocity=127))
    assert b.bank.name == "mac"


def test_changing_bank_arms_takeover_again(bridge):
    b, fake = bridge
    b.fader(0, 0.51)
    b.drain()
    b.step_bank(+1)
    b.step_bank(-1)
    b.fader(0, 0.95)
    b.drain()
    assert fake.values["main"] == 0.51


def test_rec_loads_a_scene_and_marks_it(bridge):
    b, fake = bridge
    b.on_midi(mido.Message("note_on", note=mackie.REC + 1, velocity=127))
    assert fake.loaded == "TWO" and b.scene_loaded == 2


def test_a_missing_scene_does_not_bring_it_down(bridge):
    b, _ = bridge
    b.on_midi(mido.Message("note_on", note=mackie.REC + 5, velocity=127))
    assert b.scene_loaded is None


def test_a_fader_with_no_destination_is_ignored(bridge):
    b, _ = bridge
    b.fader(7, 0.5)
    b.drain()                                  # must not raise


def test_a_refused_write_does_not_abort_the_solo():
    class Refusing(FakeDriver):
        def toggle(self, target):
            if target == "g2/mute":
                raise RuntimeError("the daemon did not confirm the write")
            return super().toggle(target)

    fake = Refusing()
    b = daemon.Bridge(profile.parse_profile(PROFILE), drivers={"fake": fake},
                      log=lambda *a: None)
    b.solo(5)
    assert b.soloed == 5                       # carried on despite the failure


def test_push_state_sends_positions_and_leds(bridge):
    b, _ = bridge
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_state()
    assert any(k["type"] == "pitchwheel" for k in sent)
    select = [k for k in sent if k["type"] == "note_on" and k["note"] == mackie.SELECT]
    assert select and select[0]["velocity"] == mackie.ON
