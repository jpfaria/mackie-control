import pytest

from mackie.bridge import drivers
from mackie.bridge.drivers import hd8, mac


class FakeClient:
    def __init__(self):
        self.values = {"global/mainOutVolume": 0.5, "global/mute": 0.0}
        self.scenes = ["A.scene", "B.scene"]
        self.loaded = None

    def get(self, path):
        return self.values[path]

    def set_raw(self, path, v):
        self.values[path] = v

    def set(self, path, v):
        self.values[path] = float(v)

    def load_scene(self, nome, keep_gains=False):
        self.loaded = (nome, keep_gains)


def test_hd8_write_is_clamped_and_read_back():
    d = hd8.HD8(client=FakeClient())
    d.write("global/mainOutVolume", 2.0)
    assert d.read("global/mainOutVolume") == 1.0
    d.write("global/mainOutVolume", -1)
    assert d.read("global/mainOutVolume") == 0.0


def test_hd8_toggle_flips_and_reports():
    d = hd8.HD8(client=FakeClient())
    assert d.toggle("global/mute") is True
    assert d.read("global/mute") == 1.0
    assert d.toggle("global/mute") is False


def test_hd8_scenes_lose_the_extension_and_keep_gains():
    c = FakeClient()
    d = hd8.HD8(client=c)
    assert d.scenes() == ["A", "B"]
    assert d.load_scene(1) == "B"
    assert c.loaded == ("B", True)


def test_hd8_refuses_a_scene_that_does_not_exist():
    d = hd8.HD8(client=FakeClient())
    with pytest.raises(drivers.Unsupported):
        d.load_scene(9)


def test_mac_says_why_when_the_output_has_no_system_volume(monkeypatch):
    monkeypatch.setattr(mac, "_osascript", lambda script: "missing value")
    with pytest.raises(drivers.Unsupported) as e:
        mac.MacVolume().read()
    assert "audio interface" in str(e.value)


def test_unknown_driver_is_refused():
    with pytest.raises(SystemExit):
        drivers.build("nope")


class DyingClient(FakeClient):
    """A client whose socket died: writes raise OSError, reads keep answering
    from a stale cache -- what the HD 8 does after the interface is power-cycled
    (measured 2026-09-22)."""

    def set_raw(self, path, v):
        raise OSError(9, "Bad file descriptor")

    def set(self, path, v):
        raise OSError(9, "Bad file descriptor")


def test_hd8_reconnects_when_the_socket_died_and_the_write_lands():
    fresh = FakeClient()
    d = hd8.HD8(client=DyingClient(), connect=lambda: fresh)
    d.write("global/mainOutVolume", 0.25)
    assert fresh.values["global/mainOutVolume"] == 0.25


def test_hd8_reconnects_before_a_toggle():
    fresh = FakeClient()
    d = hd8.HD8(client=DyingClient(), connect=lambda: fresh)
    assert d.toggle("global/mute") is True
    assert fresh.values["global/mute"] == 1.0


def test_hd8_reconnects_only_once_per_operation():
    tries = []

    def connect():
        tries.append(1)
        return DyingClient()

    d = hd8.HD8(client=DyingClient(), connect=connect)
    with pytest.raises(drivers.Unsupported):
        d.write("global/mainOutVolume", 0.25)
    assert len(tries) == 1


def test_hd8_says_why_when_it_cannot_reconnect():
    def connect():
        raise ConnectionRefusedError("ucdaemon is not answering")

    d = hd8.HD8(client=DyingClient(), connect=connect)
    with pytest.raises(drivers.Unsupported) as e:
        d.write("global/mainOutVolume", 0.25)
    assert "ucdaemon is not answering" in str(e.value)


def test_hd8_without_a_way_to_reconnect_refuses_instead_of_crashing():
    d = hd8.HD8(client=DyingClient())
    with pytest.raises(drivers.Unsupported):
        d.write("global/mainOutVolume", 0.25)


def test_hd8_closes_the_dead_client_before_reconnecting():
    dead = DyingClient()
    dead.closed = False
    dead.close = lambda: setattr(dead, "closed", True)
    d = hd8.HD8(client=dead, connect=FakeClient)
    d.write("global/mainOutVolume", 0.25)
    assert dead.closed is True


def test_app_reports_nothing_when_the_app_is_not_open(monkeypatch):
    """A closed app must not be asked about its player: AppleScript would
    launch it (2026-09-22)."""
    monkeypatch.setattr(mac, "_osascript", lambda s: "false")
    assert mac.AppVolume().playing("Spotify") is None


def test_app_reports_whether_it_is_playing(monkeypatch):
    respostas = {"running": "true", "state": "playing"}
    monkeypatch.setattr(mac, "_osascript",
                        lambda s: respostas["running"] if "is running" in s
                        else respostas["state"])
    d = mac.AppVolume()
    assert d.playing("Spotify") is True
    respostas["state"] = "paused"
    assert d.playing("Spotify") is False
