from mackie.bridge import describe, profile
from mackie.bridge.drivers import Driver, Unsupported


class FakeDriver(Driver):
    name = "fake"

    def scenes(self):
        return ["ONE", "TWO"]


class Unreachable(Driver):
    name = "gone"

    def scenes(self):
        raise Unsupported("ucdaemon is not answering")


PROFILE = {"banks": [
    {"name": "HD 8", "driver": "fake",
     "faders": {1: {"driver": "fake", "target": "main"},
                2: {"driver": "fake", "target": "phones"}}},
    {"name": "Mac", "faders": {1: {"driver": "mac"}}},
]}


def _lines(raw, drivers):
    return describe.describe(profile.parse_profile(raw), drivers=drivers)


def test_every_device_is_listed_with_its_driver_and_faders():
    lines = _lines(PROFILE, {"fake": FakeDriver()})
    assert lines[0].startswith("1  HD 8")
    assert "fake" in lines[0] and "2 faders" in lines[0]


def test_the_scenes_of_a_device_are_listed_in_order():
    lines = _lines(PROFILE, {"fake": FakeDriver()})
    assert "1 ONE" in lines[0] and "2 TWO" in lines[0]


def test_a_device_without_scenes_says_so():
    lines = _lines(PROFILE, {"fake": FakeDriver()})
    assert "no scenes" in lines[1]


def test_the_profile_list_wins_over_the_device_list():
    raw = {"banks": [dict(PROFILE["banks"][0], scenes=["TWO"])]}
    assert "1 TWO" in _lines(raw, {"fake": FakeDriver()})[0]
    assert "ONE" not in _lines(raw, {"fake": FakeDriver()})[0]


def test_gear_that_cannot_be_reached_still_lists_the_profile():
    """It has to be usable away from the rig."""
    raw = {"banks": [{"name": "HD 8", "driver": "gone", "scenes": ["MIXER-ON"],
                      "faders": {1: {"driver": "gone", "target": "main"}}}]}
    lines = _lines(raw, {"gone": Unreachable()})
    assert "1 MIXER-ON" in lines[0]
    assert any("could not be reached" in l for l in lines)
