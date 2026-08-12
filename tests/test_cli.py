"""Tests for argument parsing, name validation and main."""

import re
from pathlib import Path

import pytest

import rizomwheel


@pytest.fixture
def cli(monkeypatch):
    """Set the command line ``main`` and ``parse_args`` will see."""

    def install(*argv):
        monkeypatch.setattr(rizomwheel.sys, "argv", ["rizomwheel", *argv])

    return install


@pytest.fixture
def fake_run(monkeypatch):
    """Replace ``run`` so ``main`` can be exercised without building anything."""
    calls = []
    monkeypatch.setattr(
        rizomwheel,
        "run",
        lambda work_dir, output_dir, dist_name, commit: calls.append(
            (work_dir, output_dir, dist_name, commit)
        ),
    )
    return calls


def test_parse_args_defaults_to_none(cli):
    cli()
    args = rizomwheel.parse_args()
    assert args.output_dir is None
    assert args.work_dir is None
    assert args.name is None
    assert args.commit is None


def test_parse_args_reads_every_flag(cli):
    cli(
        "-o", "out",
        "--work-dir", "work",
        "--name", "custom",
        "--commit", "abc1234",
    )
    args = rizomwheel.parse_args()
    assert args.output_dir == Path("out")
    assert args.work_dir == Path("work")
    assert args.name == "custom"
    assert args.commit == "abc1234"


def test_parse_args_rejects_a_config_flag(cli):
    cli("--config", "cfg.toml")
    with pytest.raises(SystemExit):
        rizomwheel.parse_args()


@pytest.mark.parametrize(
    "name", ["rizomuvlink", "a", "A1", "my-pkg", "my_pkg", "my.pkg", "pkg2"]
)
def test_name_pattern_accepts_valid_names(name):
    assert rizomwheel.NAME_PATTERN.match(name)


@pytest.mark.parametrize(
    "name", ["", "-leading", "trailing-", ".dot", "has space", "has/slash", "über"]
)
def test_name_pattern_rejects_invalid_names(name):
    assert not rizomwheel.NAME_PATTERN.match(name)


@pytest.mark.parametrize(
    "commit",
    ["abc1234", "ABC1234", "0" * 40, "3f7a9c1b2d4e5f60718293a4b5c6d7e8f9012345"],
)
def test_commit_pattern_accepts_hashes(commit):
    assert rizomwheel.COMMIT_PATTERN.match(commit)


@pytest.mark.parametrize(
    "commit",
    ["", "abc123", "main", "0" * 41, "abc1234 ", "abc123z", "../../other"],
)
def test_commit_pattern_rejects_anything_else(commit):
    assert not rizomwheel.COMMIT_PATTERN.match(commit)


def test_main_uses_defaults_and_a_temporary_work_dir(
    tmp_path, monkeypatch, cli, fake_run
):
    monkeypatch.chdir(tmp_path)
    cli()

    rizomwheel.main()

    (work_dir, output_dir, dist_name, _) = fake_run[0]
    assert dist_name == rizomwheel.DEFAULT_NAME
    assert output_dir == (tmp_path / rizomwheel.DEFAULT_OUTPUT_DIR).resolve()
    assert work_dir.name.startswith("rizomwheel-")
    assert not work_dir.exists()
    # No commit asked for, so the build takes the tip of main.
    assert fake_run[0][3] is None


def test_main_keeps_an_explicit_work_dir(tmp_path, monkeypatch, cli, fake_run, capsys):
    monkeypatch.chdir(tmp_path)
    cli("--work-dir", "keepme")

    rizomwheel.main()

    (work_dir, _, _, _) = fake_run[0]
    assert work_dir == (tmp_path / "keepme").resolve()
    assert work_dir.is_dir()
    assert "Build tree kept at" in capsys.readouterr().out


def test_main_reads_settings_from_pyproject(
    tmp_path, monkeypatch, write_config, cli, fake_run
):
    write_config(
        tmp_path,
        '[tool.rizomwheel]\nname = "from-config"\noutput-dir = "wheels"\n'
        'work-dir = "scratch"\n',
    )
    monkeypatch.chdir(tmp_path)
    cli()

    rizomwheel.main()

    (work_dir, output_dir, dist_name, _) = fake_run[0]
    assert dist_name == "from-config"
    assert output_dir == (tmp_path / "wheels").resolve()
    assert work_dir == (tmp_path / "scratch").resolve()


def test_main_command_line_overrides_config(
    tmp_path, monkeypatch, write_config, cli, fake_run
):
    write_config(
        tmp_path,
        '[tool.rizomwheel]\nname = "from-config"\noutput-dir = "wheels"\n',
    )
    monkeypatch.chdir(tmp_path)
    cli("--name", "from-cli", "-o", "elsewhere")

    rizomwheel.main()

    (_, output_dir, dist_name, _) = fake_run[0]
    assert dist_name == "from-cli"
    assert output_dir == (tmp_path / "elsewhere").resolve()


def test_main_resolves_config_paths_against_the_config_file(
    tmp_path, monkeypatch, write_config, cli, fake_run
):
    write_config(tmp_path, '[tool.rizomwheel]\noutput-dir = "wheels"\n')
    nested = tmp_path / "sub"
    nested.mkdir()
    monkeypatch.chdir(nested)
    cli()

    rizomwheel.main()

    (_, output_dir, _, _) = fake_run[0]
    assert output_dir == (tmp_path / "wheels").resolve()


def test_main_passes_the_requested_commit_through(tmp_path, monkeypatch, cli, fake_run):
    monkeypatch.chdir(tmp_path)
    cli("--commit", "abc1234")

    rizomwheel.main()

    assert fake_run[0][3] == "abc1234"


def test_main_reads_the_commit_from_config(
    tmp_path, monkeypatch, write_config, cli, fake_run
):
    write_config(tmp_path, '[tool.rizomwheel]\ncommit = "abc1234"\n')
    monkeypatch.chdir(tmp_path)
    cli()

    rizomwheel.main()

    assert fake_run[0][3] == "abc1234"


def test_main_command_line_commit_overrides_config(
    tmp_path, monkeypatch, write_config, cli, fake_run
):
    write_config(tmp_path, '[tool.rizomwheel]\ncommit = "aaaaaaa"\n')
    monkeypatch.chdir(tmp_path)
    cli("--commit", "bbbbbbb")

    rizomwheel.main()

    assert fake_run[0][3] == "bbbbbbb"


def test_main_rejects_an_invalid_commit(tmp_path, monkeypatch, cli, fake_run):
    monkeypatch.chdir(tmp_path)
    cli("--commit", "not-a-hash")

    with pytest.raises(SystemExit, match=re.escape("Not a valid commit hash")):
        rizomwheel.main()

    assert fake_run == []


def test_main_rejects_an_invalid_distribution_name(
    tmp_path, monkeypatch, cli, fake_run
):
    monkeypatch.chdir(tmp_path)
    cli("--name", "bad name")

    with pytest.raises(SystemExit, match=re.escape("Not a valid distribution name")):
        rizomwheel.main()

    assert fake_run == []
