"""Tests for load_config, find_config and pick_path."""

from pathlib import Path

import pytest

import rizomwheel


def test_load_config_without_any_config_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config, base = rizomwheel.load_config()
    assert config == {}
    assert base == Path.cwd()


def test_load_config_reads_pyproject_in_cwd(tmp_path, monkeypatch, write_config):
    write_config(
        tmp_path,
        '[tool.rizomwheel]\nname = "custom"\noutput-dir = "out"\nwork-dir = "work"\n',
    )
    monkeypatch.chdir(tmp_path)
    config, base = rizomwheel.load_config()
    assert config == {"name": "custom", "output-dir": "out", "work-dir": "work"}
    assert base == tmp_path


def test_load_config_finds_pyproject_in_an_ancestor(tmp_path, monkeypatch, write_config):
    write_config(tmp_path, '[tool.rizomwheel]\nname = "custom"\noutput-dir = "out"\n')
    nested = tmp_path / "sub" / "deeper"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    config, base = rizomwheel.load_config()

    assert config == {"name": "custom", "output-dir": "out"}
    # Relative paths still resolve against the project root, not the cwd.
    assert base == tmp_path
    assert rizomwheel.pick_path(None, config["output-dir"], base) == tmp_path / "out"


def test_load_config_stops_at_the_nearest_pyproject(tmp_path, monkeypatch, write_config):
    write_config(tmp_path, '[tool.rizomwheel]\nname = "outer"\n')
    inner = tmp_path / "inner"
    inner.mkdir()
    write_config(inner, '[tool.rizomwheel]\nname = "inner"\n')
    monkeypatch.chdir(inner)

    config, base = rizomwheel.load_config()

    assert config == {"name": "inner"}
    assert base == inner


def test_load_config_stops_at_a_pyproject_without_our_table(
    tmp_path, monkeypatch, write_config
):
    """The nearest pyproject.toml wins even when it has nothing for us."""
    write_config(tmp_path, '[tool.rizomwheel]\nname = "outer"\n')
    inner = tmp_path / "inner"
    inner.mkdir()
    write_config(inner, '[project]\nname = "unrelated"\n')
    monkeypatch.chdir(inner)

    config, base = rizomwheel.load_config()

    assert config == {}
    assert base == inner


def test_load_config_ignores_unrelated_tables(tmp_path, monkeypatch, write_config):
    write_config(tmp_path, '[project]\nname = "something-else"\n')
    monkeypatch.chdir(tmp_path)
    config, base = rizomwheel.load_config()
    assert config == {}
    assert base == tmp_path


def test_load_config_rejects_unparsable_toml(tmp_path, monkeypatch, write_config):
    write_config(tmp_path, "this is not toml\n")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="Could not parse"):
        rizomwheel.load_config()


def test_load_config_rejects_non_table_section(tmp_path, monkeypatch, write_config):
    write_config(tmp_path, '[tool]\nrizomwheel = "oops"\n')
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="is not a table"):
        rizomwheel.load_config()


def test_load_config_rejects_unknown_key(tmp_path, monkeypatch, write_config):
    write_config(tmp_path, '[tool.rizomwheel]\nnmae = "typo"\n')
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="Unknown setting 'nmae'"):
        rizomwheel.load_config()


@pytest.mark.parametrize("value", ["1", "true", "[]", '{ a = "b" }'])
def test_load_config_rejects_non_string_value(tmp_path, monkeypatch, write_config, value):
    write_config(tmp_path, f"[tool.rizomwheel]\nname = {value}\n")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="must be a string"):
        rizomwheel.load_config()


def test_load_config_announces_the_settings_it_used(
    tmp_path, monkeypatch, write_config, capsys
):
    write_config(tmp_path, '[tool.rizomwheel]\nname = "custom"\n')
    monkeypatch.chdir(tmp_path)
    rizomwheel.load_config()
    assert "[tool.rizomwheel]" in capsys.readouterr().out


def test_find_config_returns_none_when_nothing_is_above_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert rizomwheel.find_config() is None


def test_pick_path_prefers_the_command_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    picked = rizomwheel.pick_path(Path("from-cli"), "from-config", tmp_path / "base")
    assert picked == (tmp_path / "from-cli").resolve()


def test_pick_path_resolves_config_value_against_base(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    picked = rizomwheel.pick_path(None, "out/wheels", base)
    assert picked == (base / "out" / "wheels").resolve()


def test_pick_path_returns_none_when_unset(tmp_path):
    assert rizomwheel.pick_path(None, None, tmp_path) is None
