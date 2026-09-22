import mido
import pytest

from mackie import protocol as mackie
from mackie.bridge import daemon, profile
from mackie.bridge.drivers import Driver, Unsupported


class FakeDriver(Driver):
    name = "fake"
    BUTTONS = {"rec": "scene"}      # like a mixer: R loads a stored scene

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


PROFILE = {"positions": True, "banks": [
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
    # Since 2026-09-22 the side arrows are scenes; the device moves on the
    # vertical pair and on Channel.
    b.on_midi(mido.Message("note_on", note=mackie.ARROW_UP, velocity=127))
    assert b.bank.name == "rig"
    b.on_midi(mido.Message("note_on", note=mackie.SELECT + 1, velocity=127))
    assert b.bank.name == "rig"          # square does nothing without select: bank


def test_square_jumps_to_a_bank_only_when_the_profile_asks():
    com_select = {"banks": [dict(PROFILE["banks"][0], buttons={"select": "bank"}),
                            PROFILE["banks"][1]]}
    b = daemon.Bridge(profile.parse_profile(com_select),
                      drivers={"fake": FakeDriver()}, log=lambda *a: None)
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
    assert select and select[0]["velocity"] == mackie.OFF   # no job, no lamp


def test_the_square_lamp_only_lights_when_it_selects_banks():
    com_select = {"banks": [dict(PROFILE["banks"][0], buttons={"select": "bank"}),
                            PROFILE["banks"][1]]}
    b = daemon.Bridge(profile.parse_profile(com_select),
                      drivers={"fake": FakeDriver()}, log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_state()
    select = [k for k in sent if k["type"] == "note_on" and k["note"] == mackie.SELECT]
    assert select and select[0]["velocity"] == mackie.ON


class Commandable(FakeDriver):
    def __init__(self):
        super().__init__()
        self.ran = []

    def command(self, target, name):
        self.ran.append((target, name))
        return True


TRANSPORT = {"banks": [{"name": "rig", "faders": {},
                        "transport": {"play": {"driver": "fake", "target": "Spotify",
                                               "command": "playpause"},
                                      "forward": {"driver": "fake", "target": "Spotify",
                                                  "command": "next track"}}}]}


def test_transport_buttons_run_the_profiles_command():
    fake = Commandable()
    b = daemon.Bridge(profile.parse_profile(TRANSPORT), drivers={"fake": fake},
                      log=lambda *a: None)
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))
    b.on_midi(mido.Message("note_on", note=mackie.FORWARD, velocity=127))
    assert fake.ran == [("Spotify", "playpause"), ("Spotify", "next track")]


def test_a_transport_button_with_no_entry_is_ignored(bridge):
    b, _ = bridge
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))   # must not raise


def test_a_driver_that_cannot_run_the_command_only_warns():
    linhas = []
    b = daemon.Bridge(profile.parse_profile(TRANSPORT),
                      drivers={"fake": FakeDriver()}, log=linhas.append)
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))
    assert any("play" in l for l in linhas)


def test_push_state_does_not_send_positions_for_unmapped_faders(bridge):
    b, _ = bridge
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_state()
    canais = {k["channel"] for k in sent if k["type"] == "pitchwheel"}
    assert canais == {0, 1, 4, 5}        # os quatro faders do perfil, so eles


def test_push_state_skips_a_destination_it_cannot_read():
    class Cego(FakeDriver):
        def read(self, target):
            raise RuntimeError("sem leitura")

    b = daemon.Bridge(profile.parse_profile(PROFILE), drivers={"fake": Cego()},
                      log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_state()
    assert not [k for k in sent if k["type"] == "pitchwheel"]


class DriverComBotoes(Commandable):
    BUTTONS = {"play": "playpause", "rec": "scene"}


BANCO_SIMPLES = {"banks": [{"name": "app", "faders": {
    1: {"driver": "fake", "target": "Spotify", "label": "SPOTIFY"}}}]}


def test_driver_declares_its_own_buttons():
    fake = DriverComBotoes()
    b = daemon.Bridge(profile.parse_profile(BANCO_SIMPLES), drivers={"fake": fake},
                      log=lambda *a: None)
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))
    assert fake.ran == [("Spotify", "playpause")]


def test_a_driver_button_of_kind_scene_loads_a_scene():
    fake = DriverComBotoes()
    b = daemon.Bridge(profile.parse_profile(BANCO_SIMPLES), drivers={"fake": fake},
                      log=lambda *a: None)
    b.on_midi(mido.Message("note_on", note=mackie.REC, velocity=127))
    assert fake.loaded == "ONE"


def test_the_profile_wins_over_the_driver_default():
    fake = DriverComBotoes()
    perfil = {"banks": [dict(BANCO_SIMPLES["banks"][0],
                             transport={"play": {"driver": "fake", "target": "Outro",
                                                 "command": "pause"}})]}
    b = daemon.Bridge(profile.parse_profile(perfil), drivers={"fake": fake},
                      log=lambda *a: None)
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))
    assert fake.ran == [("Outro", "pause")]


def test_a_driver_without_that_button_does_nothing(bridge):
    b, fake = bridge
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))   # FakeDriver.BUTTONS = {}
    assert not hasattr(fake, "ran")


def _acesos(sent, base):
    return [k["note"] - base for k in sent
            if k["type"] == "note_on" and base <= k["note"] < base + 8
            and k["velocity"] == mackie.ON]


def test_bank_change_blinks_row_and_column_three_times():
    muitos = {"banks": [{"name": f"b{i}", "faders": {}} for i in range(20)]}
    b = daemon.Bridge(profile.parse_profile(muitos), log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.bank_index = 11                       # linha 1, coluna 3
    b.flash_bank(sleep=lambda s: None)
    assert _acesos(sent, mackie.REC) == [3] * daemon.BLINKS


def test_the_blink_touches_only_its_own_cell():
    muitos = {"banks": [{"name": f"b{i}", "faders": {}} for i in range(20)]}
    b = daemon.Bridge(profile.parse_profile(muitos), log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.bank_index = 11
    b.flash_bank(sleep=lambda s: None)
    blink = [k for k in sent if k["type"] == "note_on"][:daemon.BLINKS * 2]
    assert {k["note"] for k in blink} == {mackie.REC + 3}   # so a sua coluna


def test_beyond_64_banks_there_is_nothing_to_flash():
    muitos = {"banks": [{"name": f"b{i}", "faders": {}} for i in range(70)]}
    b = daemon.Bridge(profile.parse_profile(muitos), log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.bank_index = 64
    b.flash_bank(sleep=lambda s: None)
    assert not sent


def test_the_flash_puts_the_real_leds_back_on_its_own(bridge):
    b, _ = bridge
    sent = []
    b.send = lambda **k: sent.append(k)
    b.flash_bank(sleep=lambda s: None)
    # depois do flash o proprio push_state roda: as ultimas mensagens de LED
    # sao o estado real, nao a grade
    ultimos = {}
    for k in sent:
        if k["type"] == "note_on":
            ultimos[k["note"]] = k["velocity"]
    assert ultimos[mackie.MUTE] == mackie.OFF
    assert ultimos[mackie.SELECT] == mackie.OFF


GLOBAL = {"banks": PROFILE["banks"],
          "global": {"faders": {8: {"driver": "fake", "target": "g2", "label": "SEMPRE"}},
                     "transport": {"play": {"driver": "fake", "target": "Spotify",
                                            "command": "playpause"}}}}


def test_a_global_fader_works_in_every_bank():
    fake = Commandable()
    b = daemon.Bridge(profile.parse_profile(GLOBAL), drivers={"fake": fake},
                      log=lambda *a: None)
    for _ in range(2):
        b.fader(7, 0.8)                     # g2 esta em 0.8: assume de imediato
        b.fader(7, 0.3)
        b.drain()
        assert fake.values["g2"] == 0.3
        fake.values["g2"] = 0.8
        b.step_bank(+1)


def test_global_transport_works_in_every_bank():
    fake = Commandable()
    b = daemon.Bridge(profile.parse_profile(GLOBAL), drivers={"fake": fake},
                      log=lambda *a: None)
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))
    b.step_bank(+1)
    b.on_midi(mido.Message("note_on", note=mackie.PLAY, velocity=127))
    assert fake.ran == [("Spotify", "playpause")] * 2


def test_a_global_fader_wins_over_the_banks():
    fake = Commandable()
    perfil = {"banks": [{"name": "x", "faders": {
                  8: {"driver": "fake", "target": "main", "label": "DO BANCO"}}}],
              "global": {"faders": {
                  8: {"driver": "fake", "target": "g2", "label": "GLOBAL"}}}}
    b = daemon.Bridge(profile.parse_profile(perfil), drivers={"fake": fake},
                      log=lambda *a: None)
    assert b.destination(8).label == "GLOBAL"


ENCODERS = {"banks": PROFILE["banks"],
            "global": {"encoders": {1: {"driver": "fake", "target": "g2",
                                        "label": "SPOTIFY"}}}}


def test_an_encoder_nudges_its_destination_up_and_down():
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(ENCODERS), drivers={"fake": fake},
                      log=lambda *a: None)
    antes = fake.values["g2"]
    b.on_midi(mido.Message("control_change", control=mackie.VPOT, value=1))
    b.drain()
    assert fake.values["g2"] == pytest.approx(antes + daemon.STEP)
    b.on_midi(mido.Message("control_change", control=mackie.VPOT, value=0x41))
    b.drain()
    assert fake.values["g2"] == pytest.approx(antes)


def test_an_encoder_never_leaves_the_range():
    fake = FakeDriver()
    fake.values["g2"] = 0.99
    b = daemon.Bridge(profile.parse_profile(ENCODERS), drivers={"fake": fake},
                      log=lambda *a: None)
    for _ in range(10):
        b.on_midi(mido.Message("control_change", control=mackie.VPOT, value=1))
        b.drain()
    assert fake.values["g2"] == 1.0


def test_a_global_encoder_works_in_every_bank():
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(ENCODERS), drivers={"fake": fake},
                      log=lambda *a: None)
    b.step_bank(+1)
    antes = fake.values["g2"]
    b.on_midi(mido.Message("control_change", control=mackie.VPOT, value=1))
    b.drain()
    assert fake.values["g2"] > antes


def test_an_unmapped_encoder_is_ignored(bridge):
    b, fake = bridge
    b.on_midi(mido.Message("control_change", control=mackie.VPOT + 3, value=1))   # no raise


def test_a_destination_can_waive_takeover():
    fake = FakeDriver()
    perfil = {"banks": [{"name": "app", "faders": {
        1: {"driver": "fake", "target": "main", "label": "SPOTIFY",
            "takeover": False}}}]}
    b = daemon.Bridge(profile.parse_profile(perfil), drivers={"fake": fake},
                      log=lambda *a: None)
    b.fader(0, 0.05)                 # main esta em 0.5: sem takeover, escreve ja
    b.drain()
    assert fake.values["main"] == 0.05


RANGE = {"banks": [{"name": "r", "faders": {
    1: {"driver": "fake", "target": "main", "label": "GAIN",
        "range": [0.2, 0.6], "takeover": False}}}]}


def test_a_range_keeps_the_whole_travel_inside_it():
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(RANGE), drivers={"fake": fake},
                      log=lambda *a: None)
    b.fader(0, 1.0)
    b.drain()
    assert fake.values["main"] == pytest.approx(0.6)      # topo do fader = topo do range
    b.fader(0, 0.0)
    b.drain()
    assert fake.values["main"] == pytest.approx(0.2)
    b.fader(0, 0.5)
    b.drain()
    assert fake.values["main"] == pytest.approx(0.4)


def test_a_ranged_value_is_read_back_on_the_faders_scale():
    fake = FakeDriver()
    fake.values["main"] = 0.4
    b = daemon.Bridge(profile.parse_profile(RANGE), drivers={"fake": fake},
                      log=lambda *a: None)
    assert b._read(b.destination(1)) == pytest.approx(0.5)


def test_a_bad_range_is_refused():
    for ruim in ([0.5, 0.5], [0.8, 0.2], [-1, 0.5], ["a", "b"]):
        with pytest.raises(SystemExit):
            profile.parse_profile({"banks": [{"faders": {
                1: {"driver": "fake", "target": "x", "range": ruim}}}]})


# -- devices and scenes on the surface (spec 2026-09-22) ----------------------

SCENES = {"banks": [
    {"name": "HD 8", "driver": "fake", "faders": {1: {"driver": "fake", "target": "main"}}},
    {"name": "Mac", "faders": {1: {"driver": "fake", "target": "main"}}},
    {"name": "Third", "faders": {1: {"driver": "fake", "target": "main"}}},
]}


@pytest.fixture
def rig():
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(SCENES), send=lambda **k: None,
                      drivers={"fake": fake}, log=lambda *a: None)
    return b, fake


NOTES = {"arrow_left": mackie.ARROW_LEFT, "arrow_right": mackie.ARROW_RIGHT,
         "arrow_up": mackie.ARROW_UP, "arrow_down": mackie.ARROW_DOWN}


def _press(b, kind, channel=0):
    b.button(mackie.Button(note=NOTES[kind], pressed=True))


def test_the_right_arrow_loads_the_next_scene(rig):
    b, fake = rig
    _press(b, "arrow_right")
    assert fake.loaded == "ONE"
    _press(b, "arrow_right")
    assert fake.loaded == "TWO"


def test_the_left_arrow_loads_the_previous_scene(rig):
    b, fake = rig
    _press(b, "arrow_right")
    _press(b, "arrow_right")
    _press(b, "arrow_left")
    assert fake.loaded == "ONE"


def test_the_scenes_do_not_wrap_around(rig):
    b, fake = rig
    for _ in range(5):
        _press(b, "arrow_right")
    assert fake.loaded == "TWO"           # the driver has two, and it stops there
    for _ in range(5):
        _press(b, "arrow_left")
    assert fake.loaded == "ONE"


def test_the_up_and_down_arrows_change_device(rig):
    b, _ = rig
    _press(b, "arrow_down")
    assert b.bank_index == 1
    _press(b, "arrow_up")
    assert b.bank_index == 0


def test_the_devices_do_not_wrap_around(rig):
    b, _ = rig
    for _ in range(5):
        _press(b, "arrow_up")
    assert b.bank_index == 0
    for _ in range(5):
        _press(b, "arrow_down")
    assert b.bank_index == 2


def test_a_device_with_no_scenes_ignores_the_side_arrows():
    b = daemon.Bridge(profile.parse_profile({"banks": [{"name": "empty", "faders": {}}]}),
                      log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    _press(b, "arrow_right")
    assert b.scene_index is None


def test_the_profile_chooses_which_scenes_and_in_which_order():
    chosen = {"banks": [{"name": "HD 8", "driver": "fake", "scenes": ["TWO"],
                         "faders": {1: {"driver": "fake", "target": "main"}}}]}
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(chosen), send=lambda **k: None,
                      drivers={"fake": fake}, log=lambda *a: None)
    assert b.scene_names() == ["TWO"]
    _press(b, "arrow_right")
    assert fake.loaded == "TWO"


def test_changing_device_shows_it_under_the_knobs_and_on_the_square():
    muitos = {"banks": [{"name": f"b{i}", "faders": {}} for i in range(20)]}
    b = daemon.Bridge(profile.parse_profile(muitos), log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.bank_index = 11                       # row 1, column 3
    b.flash_number(b.bank_index, mackie.REC, sleep=lambda s: None)
    assert _acesos(sent, mackie.REC) == [3] * daemon.BLINKS


def test_changing_scene_shows_it_under_the_knobs_and_on_the_s_row(bridge):
    b, fake = bridge
    b.last_seen[(0, 1)] = 0.4               # fader 2 = row 1, position known
    sent = []
    b.send = lambda **k: sent.append(k)
    b.flash_number(9, mackie.SOLO, sleep=lambda s: None)   # row 1, column 1
    assert [k["channel"] for k in sent if k["type"] == "pitchwheel"][0] == 1
    assert _acesos(sent, mackie.SOLO) == [1] * daemon.BLINKS
    # e devolve o valor do aparelho, senao aquele knob pisca para sempre
    do_canal = [k for k in sent if k["type"] == "pitchwheel" and k["channel"] == 1]
    assert do_canal[-1] == mackie.fader_position(1, 0.4)


def test_the_r_button_and_the_arrows_page_the_same_list():
    """R n loaded the n-th scene of the device while the arrows paged the
    profile's list, so the two disagreed on any bank with `scenes:`."""
    chosen = {"banks": [{"name": "HD 8", "driver": "fake", "scenes": ["TWO", "ONE"],
                         "faders": {1: {"driver": "fake", "target": "main"},
                                    2: {"driver": "fake", "target": "phones"}}}]}
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(chosen), send=lambda **k: None,
                      drivers={"fake": fake}, log=lambda *a: None)
    b.scene(1)
    assert fake.loaded == "TWO"           # the first of the profile's list
    b.scene(2)
    assert fake.loaded == "ONE"
    assert b.scene_index == 1             # the arrows now carry on from here


def test_the_knob_lamp_is_handed_back_where_the_fader_really_is(bridge):
    """The surface compares against the physical fader, so only the position
    that fader itself reported stops the blink. Sending the gear's value left
    it blinking for ever (measured 2026-09-22)."""
    b, fake = bridge
    b.last_seen[(0, 1)] = 0.4                # where fader 2 physically sits
    fake.values["phones"] = 0.9              # the gear disagrees; irrelevant
    sent = []
    b.send = lambda **k: sent.append(k)
    b.flash_number(9, mackie.SOLO, sleep=lambda s: None)
    bends = [k for k in sent if k["type"] == "pitchwheel" and k["channel"] == 1]
    assert bends[0] == mackie.fader_position(1, 0.0)    # acende a linha
    assert bends[1] == mackie.fader_position(1, 0.4)    # e devolve o fader


def test_a_row_is_shown_even_before_that_fader_has_been_touched():
    """It blinks until someone touches that fader, and a blinking lamp on the
    right channel still says which row you are on. Showing nothing did not."""
    muitos = {"banks": [{"name": f"b{i}", "faders": {}} for i in range(20)]}
    b = daemon.Bridge(profile.parse_profile(muitos), log=lambda *a: None)
    sent = []
    b.send = lambda **k: sent.append(k)
    b.bank_index = 11                       # linha 1
    b.flash_bank(sleep=lambda s: None)
    bends = [k for k in sent if k["type"] == "pitchwheel"]
    assert bends and bends[0]["channel"] == 1


# -- encoders do not block the MIDI thread (2026-09-22) ----------------------

UM_ENCODER = {"banks": [{"name": "rig", "faders": {},
                         "encoders": {1: {"driver": "fake", "target": "main",
                                          "label": "SPOTIFY"}}}]}


def _com_encoder():
    fake = FakeDriver()
    return daemon.Bridge(profile.parse_profile(UM_ENCODER), send=lambda **k: None,
                         drivers={"fake": fake}, log=lambda *a: None), fake


def test_an_encoder_detent_writes_nothing_until_the_drain():
    """A write can take a tenth of a second (AppleScript to Spotify: 117 ms
    measured). Doing it on the MIDI thread backs up every other message."""
    b, fake = _com_encoder()
    b.encoder(0, +1)
    assert fake.values["main"] == 0.5          # untouched so far
    b.drain()
    assert fake.values["main"] > 0.5


def test_detents_are_added_up_and_applied_once():
    b, fake = _com_encoder()
    for _ in range(4):
        b.encoder(0, +1)
    b.drain()
    assert fake.values["main"] == pytest.approx(0.5 + 4 * daemon.STEP)


def test_a_detent_the_other_way_cancels_one():
    b, fake = _com_encoder()
    b.encoder(0, +3)
    b.encoder(0, -1)
    b.drain()
    assert fake.values["main"] == pytest.approx(0.5 + 2 * daemon.STEP)


def test_push_state_reads_nothing_when_positions_are_off():
    """Reading a fader costs a round trip -- 117 ms to Spotify through
    AppleScript -- and the value is only used to send a position back. With
    positions off, reading all eight on every bank change blocked the surface
    for the best part of a second (2026-09-22)."""
    lido = []

    class Lenta(FakeDriver):
        def read(self, target):
            lido.append(target)
            return super().read(target)

    b = daemon.Bridge(profile.parse_profile({"banks": PROFILE["banks"]}),
                      send=lambda **k: None, drivers={"fake": Lenta()},
                      log=lambda *a: None)
    b.push_state()
    assert [t for t in lido if not t.endswith("/mute")] == []


# -- transport lamps follow the player (2026-09-22) --------------------------

class Player(FakeDriver):
    name = "fake"
    BUTTONS = {"play": "playpause"}

    def __init__(self):
        super().__init__()
        self.state = None            # None = the app is not open

    def playing(self, target):
        return self.state


TRANSPORTE = {"banks": [{"name": "rig", "faders": {}}],
              "global": {"transport": {"play": {"driver": "fake",
                                                "target": "Spotify",
                                                "command": "playpause"}}}}


def _com_player():
    p = Player()
    b = daemon.Bridge(profile.parse_profile(TRANSPORTE), drivers={"fake": p},
                      log=lambda *a: None)
    return b, p


def test_the_play_lamp_is_dark_while_the_app_is_closed():
    b, p = _com_player()
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_transport()
    assert [k["velocity"] for k in sent if k["note"] == mackie.PLAY] == [mackie.OFF]


def test_the_play_lamp_goes_dark_when_the_app_is_closed():
    b, p = _com_player()
    p.state = True
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_transport()
    assert [k["velocity"] for k in sent if k["note"] == mackie.PLAY] == [mackie.ON]
    p.state = None                        # fechou o app
    sent.clear()
    b.push_transport()
    assert [k["velocity"] for k in sent if k["note"] == mackie.PLAY] == [mackie.OFF]


def test_the_player_is_asked_only_when_something_is_bound_to_it(bridge):
    """No transport in the profile, no round trip to any app."""
    b, _ = bridge
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_transport()
    assert not sent


def test_every_bound_transport_button_lights_while_the_app_is_open():
    b, p = _com_player()
    p.state = False                       # open, paused
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_transport()
    assert [k["velocity"] for k in sent if k["note"] == mackie.PLAY] == [mackie.ON]








def test_nothing_is_sent_to_lamps_the_surface_does_not_have(rig):
    """Measured 2026-09-22, with the bridge stopped: notes 60-63 (the four
    arrows) and 2E/2F (Channel) light nothing on the SMC-Mixer. Sending to
    them is noise on the wire and a lie in the docs."""
    b, _ = rig
    sent = []
    b.send = lambda **k: sent.append(k)
    b.push_state()
    mudas = {mackie.ARROW_UP, mackie.ARROW_DOWN, mackie.ARROW_LEFT,
             mackie.ARROW_RIGHT, mackie.BANK_LEFT, mackie.BANK_RIGHT}
    assert not [k for k in sent if k.get("note") in mudas]
