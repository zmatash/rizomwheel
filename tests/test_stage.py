"""Tests for stage_project."""

import tomllib

import pytest

import rizomwheel


def test_stage_project_copies_sources_and_writes_project_files(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "rizomuvlink")

    for name in rizomwheel.MODULES:
        assert (build_dir / name).read_text(encoding="utf-8") == f"# {name}\n"
    for name in rizomwheel.PACKAGES:
        assert (build_dir / name / "RizomUVLink.pyd").is_file()
    for name in rizomwheel.METADATA_FILES:
        assert (build_dir / name).read_text(encoding="utf-8") == f"{name} from source\n"
    assert (build_dir / "hatch_build.py").read_text(encoding="utf-8") == (
        rizomwheel.BUILD_HOOK
    )


def test_stage_project_creates_nested_build_dir(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "a" / "b" / "build"
    rizomwheel.stage_project(repo, build_dir, "rizomuvlink")
    assert build_dir.is_dir()


def test_stage_project_generated_pyproject_is_valid_and_populated(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo")
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "my-dist")

    with (build_dir / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)

    assert data["project"]["name"] == "my-dist"
    assert data["project"]["version"] == rizomwheel.VERSION
    include = data["tool"]["hatch"]["build"]["targets"]["wheel"]["include"]
    assert include == rizomwheel.MODULES + rizomwheel.PACKAGES


def test_stage_project_substitutes_missing_metadata_files(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", metadata=[])
    build_dir = tmp_path / "build"

    rizomwheel.stage_project(repo, build_dir, "rizomuvlink")

    for name in rizomwheel.METADATA_FILES:
        contents = (build_dir / name).read_text(encoding="utf-8")
        assert contents == f"See {rizomwheel.REPOSITORY_URL}\n"


def test_stage_project_fails_on_missing_module(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", modules=rizomwheel.MODULES[:1])
    with pytest.raises(SystemExit, match="Missing expected module"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink")


def test_stage_project_fails_on_missing_package(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=[])
    with pytest.raises(SystemExit, match="Missing expected package"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink")


def test_stage_project_fails_when_package_is_a_file(tmp_path, make_repo):
    repo = make_repo(tmp_path / "repo", packages=[])
    (repo / rizomwheel.PACKAGES[0]).write_text("not a directory\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Missing expected package"):
        rizomwheel.stage_project(repo, tmp_path / "build", "rizomuvlink")
