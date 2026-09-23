import pytest

from mackie.bridge.drivers import Unsupported, classes
from mackie.bridge.drivers import ampero2, mk300


class FakeMK300:
    def __init__(self):
        self.vol = 70
        self.loaded = None

    def volume(self):
        return self.vol

    def set_volume(self, v):
        self.vol = v

    def preset_names(self):
        return ["CLEAN", "CRUNCH", "LEAD"]

    def load_preset(self, i):
        self.loaded = i


class FakeAmpero:
    def __init__(self):
        self.vol = None
        self.loaded = None

    def set_volume(self, v):
        self.vol = v

    def patch_names(self):
        return ["DET-LUGA", "AMBIENT"]

    def load_patch(self, i):
        self.loaded = i


# -- MK-300 -------------------------------------------------------------------

def test_mk300_volume_reads_and_writes_as_0_to_1():
    fake = FakeMK300()
    d = mk300.MK300(connect=lambda: fake)
    assert d.read("volume") == pytest.approx(0.70)
    d.write("volume", 0.42)
    assert fake.vol == 42


def test_mk300_scenes_are_its_presets():
    fake = FakeMK300()
    d = mk300.MK300(connect=lambda: fake)
    assert d.scenes() == ["CLEAN", "CRUNCH", "LEAD"]
    assert d.load_scene(2) == "LEAD"
    assert fake.loaded == 2


def test_mk300_unplugged_is_unsupported_not_a_crash():
    def nada():
        raise RuntimeError("no MIDI port containing 'USB Composite Device'")
    d = mk300.MK300(connect=nada)
    with pytest.raises(Unsupported) as e:
        d.read("volume")
    assert "MK-300" in str(e.value)


def test_mk300_reconnects_once_it_is_plugged_in():
    tentativas = []

    def connect():
        tentativas.append(1)
        if len(tentativas) == 1:
            raise RuntimeError("not there yet")
        return FakeMK300()

    d = mk300.MK300(connect=connect)
    with pytest.raises(Unsupported):
        d.read("volume")
    assert d.read("volume") == pytest.approx(0.70)


# -- Ampero II ----------------------------------------------------------------

def test_ampero_volume_is_write_only_so_read_is_none_until_written():
    """The protocol has no query for the patch volume: a fader on it cannot
    take over, so read answers None (the bridge then applies at once) and,
    after a write, the value it wrote."""
    fake = FakeAmpero()
    d = ampero2.Ampero2(connect=lambda: fake)
    assert d.read("volume") is None
    d.write("volume", 0.30)
    assert fake.vol == 30
    assert d.read("volume") == pytest.approx(0.30)


def test_ampero_forgets_the_volume_when_a_patch_loads():
    """The volume belongs to the patch: a new patch brings its own."""
    fake = FakeAmpero()
    d = ampero2.Ampero2(connect=lambda: fake)
    d.write("volume", 0.30)
    d.load_scene(1)
    assert d.read("volume") is None


def test_ampero_scenes_are_its_patches():
    fake = FakeAmpero()
    d = ampero2.Ampero2(connect=lambda: fake)
    assert d.scenes() == ["DET-LUGA", "AMBIENT"]
    assert d.load_scene(1) == "AMBIENT"
    assert fake.loaded == 1


def test_both_pedals_are_known_and_ship_a_bank():
    known = classes()
    for nome in ("mk300", "ampero2"):
        assert nome in known
        assert known[nome].DEFAULT_BANKS


def test_mk300_reads_the_preset_names_once():
    """Reading the 160 names takes a second on the real pedal (measured
    2026-09-22); doing it on every arrow press would stall the surface."""
    fake = FakeMK300()
    pedidos = []
    original = fake.preset_names
    fake.preset_names = lambda: pedidos.append(1) or original()
    d = mk300.MK300(connect=lambda: fake)
    d.scenes(); d.scenes(); d.load_scene(1)
    assert len(pedidos) == 1


def test_mk300_names_lose_their_padding():
    fake = FakeMK300()
    fake.preset_names = lambda: ["UK Clean ", "UK OD "]
    assert mk300.MK300(connect=lambda: fake).scenes() == ["UK Clean", "UK OD"]


def test_mk300_says_which_preset_is_loaded():
    fake = FakeMK300()
    fake.current = lambda: 2
    assert mk300.MK300(connect=lambda: fake).current_scene() == 2


def test_ampero_says_which_patch_is_loaded():
    fake = FakeAmpero()
    fake.current = lambda: 1
    assert ampero2.Ampero2(connect=lambda: fake).current_scene() == 1
