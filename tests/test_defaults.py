from mackie.bridge import defaults, profile


def _expand(raw):
    return defaults.expand(profile.parse_profile(raw))


def test_a_bank_with_only_a_driver_becomes_that_device_s_default_banks():
    p = _expand({"banks": [{"name": "HD 8", "driver": "hd8"}]})
    assert [b.name for b in p.banks] == ["HD 8 IN", "HD 8 OUT"]


def test_the_input_bank_is_the_eight_analog_channels():
    p = _expand({"banks": [{"driver": "hd8"}]})
    ins = p.banks[0]
    assert len(ins.faders) == 8
    assert ins.faders[1].target == "line/ch1/volume"
    assert ins.faders[1].mute == "line/ch1/mute"
    assert ins.faders[8].target == "line/ch8/volume"
    assert all(d.group == "in" for d in ins.faders.values())


def test_the_output_bank_starts_at_main_and_the_two_headphones():
    p = _expand({"banks": [{"driver": "hd8"}]})
    outs = p.banks[1]
    assert outs.faders[1].target == "global/mainOutVolume"
    assert outs.faders[1].mute == "global/mute"
    assert outs.faders[2].target == "global/phones1_volume"
    assert outs.faders[3].target == "global/phones2_volume"
    assert len(outs.faders) == 8
    assert all(d.group == "out" for d in outs.faders.values())


def test_the_scenes_and_the_driver_travel_to_both_banks():
    p = _expand({"banks": [{"driver": "hd8", "scenes": ["MIXER-ON"]}]})
    assert all(b.driver == "hd8" and b.scenes == ["MIXER-ON"] for b in p.banks)


def test_a_bank_that_names_its_own_faders_is_left_alone():
    raw = {"banks": [{"name": "meu", "driver": "hd8",
                      "faders": {1: {"driver": "hd8", "target": "global/mainOutVolume"}}}]}
    p = _expand(raw)
    assert [b.name for b in p.banks] == ["meu"]
    assert len(p.banks[0].faders) == 1


def test_a_driver_with_no_default_is_left_alone():
    p = _expand({"banks": [{"name": "Mac", "driver": "mac"}]})
    assert [b.name for b in p.banks] == ["Mac"]
    assert p.banks[0].faders == {}


def test_the_bridge_runs_against_the_expanded_profile(monkeypatch, tmp_path):
    """A profile that says only `driver: hd8` must reach the surface with the
    device's faders already in place."""
    from mackie.bridge import run

    yaml_file = tmp_path / "rig.yaml"
    yaml_file.write_text("banks:\n  - name: HD 8\n    driver: hd8\n")
    seen = {}

    class FakeMidi:
        def get_input_names(self):
            return ["SMC-Mixer Bluetooth"]

        get_output_names = get_input_names

        def open_input(self, name):
            raise KeyboardInterrupt

        open_output = open_input

        def Message(self, **k):
            return k

    class FakeBridge:
        bank_index = 0

        def __init__(self, profile, **k):
            seen["p"] = profile

        def drain_forever(self):
            pass

        def select_bank(self, i):
            pass

    monkeypatch.setattr(run, "Bridge", FakeBridge)
    try:
        run.run(str(yaml_file), midi=FakeMidi(), log=lambda *a: None, sleep=lambda s: None)
    except KeyboardInterrupt:
        pass
    assert [b.name for b in seen["p"].banks] == ["HD 8 IN", "HD 8 OUT"]
