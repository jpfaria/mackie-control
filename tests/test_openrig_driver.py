import pytest

from mackie.bridge import drivers
from mackie.bridge.drivers import openrig


class FakeMcp:
    """OpenRig's MCP as the driver sees it: the mixer resource and two tools."""

    def __init__(self):
        self.strips = [
            {"id": "out:24,25@hd8", "name": "FRFR (ADAT out 11/12)", "gain_db": -16.3, "muted": True},
            {"id": "out:4,5@hd8", "name": "SYN-5050 (Out 5/6)", "gain_db": -29.5, "muted": False},
            {"id": "out:8,9@hd8", "name": "SYN-2 FX RETURN L/R (Out 9/10)", "gain_db": 0.0, "muted": False},
            {"id": "out:2@hd8", "name": "SYN-2 INST IN (Out 3)", "gain_db": 0.0, "muted": False},
        ]
        self.connects = 0

    def connect(self):
        self.connects += 1

    def resource(self, uri):
        assert uri == "openrig://mixer"
        return {"strips": self.strips}

    def _by_id(self, sid):
        return next(s for s in self.strips if s["id"] == sid)

    def call(self, tool, args):
        s = self._by_id(args["strip"])
        if tool == "set_mixer_fader":
            s["gain_db"] = max(-60.0, min(12.0, args["gain_db"]))
        elif tool == "set_mixer_mute":
            s["muted"] = args["muted"]
        else:
            raise openrig.McpError(f"unknown tool {tool}")


def test_fader_travel_is_linear_in_db_over_openrigs_range():
    assert openrig.to_db(0) == -60.0
    assert openrig.to_db(1) == 12.0
    assert openrig.to_db(5 / 6) == pytest.approx(0.0)
    assert openrig.to_db(7) == 12.0
    assert openrig.from_db(openrig.to_db(0.42)) == pytest.approx(0.42)


def test_write_reaches_the_strip_named_by_its_prefix_and_reads_back():
    mcp = FakeMcp()
    d = openrig.OpenRig(client=mcp)
    d.write("FRFR", 5 / 6)
    assert mcp.strips[0]["gain_db"] == pytest.approx(0.0)
    assert d.read("FRFR") == pytest.approx(5 / 6)


def test_a_strip_can_be_named_by_its_full_id():
    d = openrig.OpenRig(client=FakeMcp())
    assert d.read("out:4,5@hd8") == pytest.approx(openrig.from_db(-29.5))


def test_toggle_flips_the_strip_mute_and_reports_it():
    mcp = FakeMcp()
    d = openrig.OpenRig(client=mcp)
    assert d.toggle("FRFR") is False
    assert mcp.strips[0]["muted"] is False
    assert d.toggle("FRFR") is True


def test_an_ambiguous_name_is_refused_not_guessed():
    d = openrig.OpenRig(client=FakeMcp())
    with pytest.raises(drivers.Unsupported) as e:
        d.write("SYN-2", 0.5)
    assert "FX RETURN" in str(e.value)


def test_an_unknown_strip_is_unsupported():
    with pytest.raises(drivers.Unsupported):
        openrig.OpenRig(client=FakeMcp()).read("NOPE")


class RestartedMcp(FakeMcp):
    """OpenRig restarted: the old session is gone until connect() runs again."""

    def __init__(self):
        super().__init__()
        self.alive = False

    def connect(self):
        super().connect()
        self.alive = True

    def resource(self, uri):
        if not self.alive:
            raise OSError("session expired")
        return super().resource(uri)


def test_a_lost_session_reconnects_once_and_the_read_lands():
    mcp = RestartedMcp()
    d = openrig.OpenRig(client=mcp)
    assert d.read("SYN-5050") == pytest.approx(openrig.from_db(-29.5))
    assert mcp.connects == 1


class DownMcp(FakeMcp):
    def connect(self):
        raise OSError("connection refused")

    def resource(self, uri):
        raise OSError("connection refused")


def test_openrig_not_running_is_unsupported_not_a_crash():
    with pytest.raises(drivers.Unsupported) as e:
        openrig.OpenRig(client=DownMcp()).read("FRFR")
    assert "not reachable" in str(e.value)


def test_a_refused_command_is_unsupported():
    class Refusing(FakeMcp):
        def call(self, tool, args):
            raise openrig.McpError("strip not found")
    with pytest.raises(drivers.Unsupported):
        openrig.OpenRig(client=Refusing()).write("FRFR", 0.5)


def test_the_driver_is_registered():
    assert drivers.classes()["openrig"] is openrig.OpenRig


def test_mute_target_reads_the_mute_the_lamp_needs():
    mcp = FakeMcp()
    d = openrig.OpenRig(client=mcp)
    assert d.read("mute:FRFR") == 1.0
    assert d.toggle("mute:FRFR") is False
    assert d.read("mute:FRFR") == 0.0
