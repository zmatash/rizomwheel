"""Builders shared by the test modules."""

import tarfile
from pathlib import Path

import pytest

import rizomwheel


@pytest.fixture
def write_config():
    """Write a pyproject.toml holding a given body and return its path."""

    def write(directory: Path, body: str) -> Path:
        path = directory / "pyproject.toml"
        path.write_text(body, encoding="utf-8")
        return path

    return write


@pytest.fixture
def make_repo():
    """Create a directory tree that looks like an extracted RizomUVLink repo."""

    def make(root: Path, *, modules=None, packages=None, metadata=None) -> Path:
        modules = rizomwheel.MODULES if modules is None else modules
        packages = rizomwheel.PACKAGES if packages is None else packages
        metadata = rizomwheel.METADATA_FILES if metadata is None else metadata

        root.mkdir(parents=True, exist_ok=True)
        for name in modules:
            (root / name).write_text(f"# {name}\n", encoding="utf-8")
        for name in packages:
            package = root / name
            package.mkdir()
            (package / "RizomUVLink.pyd").write_bytes(b"\x00binary")
        for name in metadata:
            (root / name).write_text(f"{name} from source\n", encoding="utf-8")
        return root

    return make


@pytest.fixture
def make_archive(tmp_path):
    """Pack a repo into a .tar.gz the way a GitHub source archive is laid out."""

    def make(repo: Path, arcname: str) -> Path:
        archive = tmp_path / "archive.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(repo, arcname=arcname)
        return archive

    return make
