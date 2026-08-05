"""Tests for build_wheel and the run pipeline."""

import subprocess

import pytest

import rizomwheel


@pytest.fixture
def fake_subprocess_run(monkeypatch):
    """Record ``subprocess.run`` calls and return a chosen exit code."""
    calls = []

    def install(returncode: int = 0):
        def run(command, check=False):
            calls.append(command)
            return subprocess.CompletedProcess(command, returncode)

        monkeypatch.setattr(rizomwheel.subprocess, "run", run)
        return calls

    return install


def test_build_wheel_invokes_the_build_module(tmp_path, fake_subprocess_run):
    calls = fake_subprocess_run(returncode=0)
    build_dir = tmp_path / "build"
    output_dir = tmp_path / "out" / "wheels"

    rizomwheel.build_wheel(build_dir, output_dir)

    assert output_dir.is_dir()
    assert len(calls) == 1
    command = calls[0]
    expected = [rizomwheel.sys.executable, "-m", "build", "--wheel", "--outdir"]
    assert command[:5] == expected
    assert command[5] == str(output_dir)
    assert command[6] == str(build_dir)


def test_build_wheel_reports_a_failed_build(tmp_path, fake_subprocess_run):
    fake_subprocess_run(returncode=2)
    with pytest.raises(SystemExit, match="exit code 2"):
        rizomwheel.build_wheel(tmp_path / "build", tmp_path / "out")


def test_run_chains_download_stage_and_build(tmp_path, make_repo, monkeypatch, capsys):
    repo = make_repo(tmp_path / "repo")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    output_dir = tmp_path / "out"
    seen = {}

    monkeypatch.setattr(rizomwheel, "download_repository", lambda w: repo)
    monkeypatch.setattr(
        rizomwheel,
        "stage_project",
        lambda r, b, n: seen.update(repo=r, build=b, name=n),
    )
    monkeypatch.setattr(
        rizomwheel, "build_wheel", lambda b, o: seen.update(built=(b, o))
    )

    rizomwheel.run(work_dir, output_dir, "custom")

    assert seen["repo"] == repo
    assert seen["build"] == work_dir / "build"
    assert seen["name"] == "custom"
    assert seen["built"] == (work_dir / "build", output_dir)
    assert str(output_dir) in capsys.readouterr().out
