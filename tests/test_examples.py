"""The shipped examples must stay loadable -- a broken example is a broken doc."""
from pathlib import Path

import pytest

from mackie.bridge import profile

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.yaml"))


def test_there_are_examples():
    assert EXAMPLES, "examples/ should ship at least one profile"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_parses_and_has_a_known_shape(path):
    p = profile.load_profile(path)
    assert p.banks
    for bank in p.banks:
        for fader, dest in bank.faders.items():
            assert 1 <= fader <= 8, f"{path.name}: fader {fader} is out of range"
            assert dest.driver in ("hd8", "mac", "app"), \
                f"{path.name}: unknown driver {dest.driver}"
            assert dest.group in ("in", "out"), \
                f"{path.name}: unknown group {dest.group}"
