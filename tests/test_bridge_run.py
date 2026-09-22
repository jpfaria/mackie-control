import pytest

from mackie.bridge import run


def test_find_port_matches_by_hint():
    assert run.find_port(("SMC-Mixer-Master",),
                         ["Quantum HD 8 MIDI", "SINCO SMC-Mixer-Master"]) \
        == "SINCO SMC-Mixer-Master"


def test_find_port_falls_back_to_the_next_hint():
    """Over Bluetooth the SMC-Mixer shows up as `SMC-Mixer Bluetooth`, with no
    -Master port at all (measured 2026-09-22)."""
    assert run.find_port(("SMC-Mixer-Master", "SMC-Mixer"),
                         ["Quantum HD 8 MIDI", "SMC-Mixer Bluetooth"]) \
        == "SMC-Mixer Bluetooth"


def test_find_port_prefers_the_earlier_hint():
    assert run.find_port(("SMC-Mixer-Master", "SMC-Mixer"),
                         ["SMC-Mixer-Private", "SMC-Mixer-Master"]) \
        == "SMC-Mixer-Master"


def test_find_port_without_a_match_names_every_hint():
    with pytest.raises(SystemExit) as e:
        run.find_port(("SMC-Mixer-Master", "SMC-Mixer"), ["Quantum HD 8 MIDI"])
    assert "no MIDI port" in str(e.value) and "SMC-Mixer" in str(e.value)
