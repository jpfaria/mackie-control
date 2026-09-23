import pytest


@pytest.fixture(autouse=True)
def _state_in_tmp(tmp_path, monkeypatch):
    """The bridge remembers where the rig was under XDG_STATE_HOME. No test
    may write that into the real home directory."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
