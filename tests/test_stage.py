"""Tests for stage_project and the platform helpers."""

import tomllib

import pytest

import rizomwheel


def test_stage_project_copies_sources_and_writes_project_files(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "rizomuvlink", "win")

    for name in rizomwheel.MODULES:
        assert (build_dir / name).read_text(encoding="utf-8") == f"# {name}\n"
    assert (build_dir / "win" / "rizomuvlink_python39.pyd").is_file()
    assert not (build_dir / "mac").exists()
    assert not (build_dir / "linux").exists()
    for name in rizomwheel.METADATA_FILES:
        assert (build_dir / name).read_text(encoding="utf-8") == f"{name} from source\n"
    assert (build_dir / "hatch_build.py").is_file()


@pytest.mark.parametrize(
    ("platform", "tag"),
    [
        ("win", "py3-none-win_amd64"),
        ("mac", "py3-none-macosx_10_15_universal2"),
        ("linux", "py3-none-manylinux_2_24_x86_64"),
    ],
)
def test_stage_project_tags_the_wheel_for_its_platform(
    tmp_path, make_repo, platform, tag
):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "rizomuvlink", platform)

    hook = (build_dir / "hatch_build.py").read_text(encoding="utf-8")
    assert f'"{tag}"' in hook


def test_stage_project_creates_nested_build_dir(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "a" / "b" / "build"
    rizomwheel.stage_project(repo, build_dir, "rizomuvlink", "win")
    assert build_dir.is_dir()


def test_stage_project_generated_pyproject_is_valid_and_populated(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "my-dist", "linux")

    with (build_dir / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    assert data["project"]["name"] == "my-dist"
    assert data["project"]["version"] == rizomwheel.VERSION
    assert data["project"]["requires-python"] == ">=3.9"
    include = data["tool"]["hatch"]["build"]["targets"]["wheel"]["include"]
    assert include == [*rizomwheel.MODULES, "linux"]


def test_stage_project_substitutes_missing_metadata_files(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", metadata=[])
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "rizomuvlink", "win")

    for name in rizomwheel.METADATA_FILES:
        contents = (build_dir / name).read_text(encoding="utf-8")
        assert contents == f"See {rizomwheel.REPOSITORY_URL}\n"


def test_stage_project_fails_on_missing_module(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", modules=rizomwheel.MODULES[:1])
    with pytest.raises(SystemExit, match="Missing expected module"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink", "win")


def test_stage_project_fails_on_missing_package(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=[])
    with pytest.raises(SystemExit, match="Missing expected package"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink", "win")


def test_stage_project_fails_when_package_is_a_file(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=[])
    (repo / "win").write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Missing expected package"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink", "win")


def test_stage_project_fails_when_package_has_no_binaries(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=[])
    (repo / "win").mkdir()
    (repo / "win" / "__init__.py").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="No compiled modules"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink", "win")


def test_minimum_python_compares_versions_numerically(tmp_path):
    package = tmp_path / "win"
    package.mkdir()
    for version in ("36", "310", "313"):
        (package / f"rizomuvlink_python{version}.pyd").write_bytes(b"")
    assert rizomwheel.minimum_python(package) == "3.6"


def test_find_platforms_skips_absent_packages(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=["win"])
    assert rizomwheel.find_platforms(repo) == ["win"]


def test_find_platforms_fails_when_none_present(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=[])
    with pytest.raises(SystemExit, match="Missing expected package"):
        rizomwheel.find_platforms(repo)
