import json

from mackie.bridge import daemon, profile
from mackie.bridge.state import State

from test_bridge_daemon import FakeDriver, SCENES


def _bridge(tmp_path, raw=SCENES):
    fake = FakeDriver()
    b = daemon.Bridge(profile.parse_profile(raw), send=lambda **k: None,
                      drivers={"fake": fake}, log=lambda *a: None,
                      state=State(tmp_path / "state.json"))
    return b, fake


def test_the_device_and_scene_survive_a_restart(tmp_path):
    b, _ = _bridge(tmp_path)
    b.step_bank(+1)                  # device 2
    b.step_bank(-1)                  # back to device 1
    b.step_scene(+1)                 # scene 1 there
    b.step_scene(+1)                 # scene 2
    b.step_bank(+1)                  # end on device 2

    novo, fake = _bridge(tmp_path)
    novo.restore()
    assert novo.bank_index == 1
    novo.step_bank(-1)
    assert novo.scene_index == 1     # device 1 remembered its scene 2


def test_restoring_reloads_nothing(tmp_path):
    """Remembering where the rig was must not change the rig: no scene is
    loaded on start, the position is only the starting point of the arrows."""
    b, _ = _bridge(tmp_path)
    b.step_scene(+1)
    novo, fake = _bridge(tmp_path)
    fake.loaded = None
    novo.restore()
    assert fake.loaded is None


def test_scenes_are_remembered_by_bank_name_not_position(tmp_path):
    """Adding a bank at the top of the YAML must not hand device 1's scene to
    whatever is now first."""
    b, _ = _bridge(tmp_path)
    b.step_scene(+1)
    b.step_scene(+1)                 # "HD 8" on scene 2
    novo_raw = {"banks": [{"name": "NEW", "faders": {}}] + SCENES["banks"]}
    novo, _ = _bridge(tmp_path, novo_raw)
    novo.restore()
    assert novo.profile.banks[novo.bank_index].name == "HD 8"
    assert novo.scene_index == 1


def test_a_missing_or_broken_state_file_is_a_fresh_start(tmp_path):
    (tmp_path / "state.json").write_text("{ not json")
    b, _ = _bridge(tmp_path)
    b.restore()
    assert b.bank_index == 0 and b.scene_index is None


def test_the_file_is_plain_json_a_person_can_read(tmp_path):
    b, _ = _bridge(tmp_path)
    b.step_scene(+1)
    dados = json.loads((tmp_path / "state.json").read_text())
    assert dados["device"] == "HD 8"
    assert dados["scenes"] == {"HD 8": 0}
