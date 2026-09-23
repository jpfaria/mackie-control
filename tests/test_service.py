import plistlib

import pytest

from mackie import service


class Launchctl:
    def __init__(self, stdout="", returncode=0):
        self.calls, self.stdout, self.returncode = [], stdout, returncode

    def __call__(self, args, **kw):
        self.calls.append(args)
        return type("R", (), {"returncode": self.returncode, "stdout": self.stdout})()


def test_install_writes_an_agent_that_restarts_the_bridge(tmp_path):
    profile = tmp_path / "rig.yaml"
    profile.write_text("surface: smc-mixer\n")
    run = Launchctl()
    dest = service.install(str(profile), run=run, home=tmp_path,
                           python="/py/bin/python3", log=lambda *_: None)
    data = plistlib.loads(dest.read_bytes())
    assert data["ProgramArguments"] == ["/py/bin/python3", "-m", "mackie", "bridge",
                                        str(profile.resolve())]
    assert data["KeepAlive"] is True and data["RunAtLoad"] is True
    assert data["StandardOutPath"] == str(tmp_path / "Library/Logs/mackie-control.log")
    assert run.calls[0][:2] == ["launchctl", "bootout"]      # old one out first
    assert run.calls[1][:2] == ["launchctl", "bootstrap"]


def test_install_refuses_a_missing_profile(tmp_path):
    with pytest.raises(SystemExit):
        service.install(str(tmp_path / "nope.yaml"), run=Launchctl(), home=tmp_path)


def test_uninstall_removes_the_agent(tmp_path):
    dest = service.agent_path(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("x")
    service.uninstall(run=Launchctl(), home=tmp_path, log=lambda *_: None)
    assert not dest.exists()


def test_status(tmp_path):
    assert service.status(run=Launchctl(), home=tmp_path) == "not installed"
    dest = service.agent_path(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("x")
    assert service.status(run=Launchctl(stdout="\tpid = 42\n"), home=tmp_path) == "running (pid = 42)"
    assert service.status(run=Launchctl(returncode=113), home=tmp_path) == "installed, not loaded"
