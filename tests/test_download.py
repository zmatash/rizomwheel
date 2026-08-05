"""Tests for download_repository."""

import io
import tarfile
import urllib.error
from pathlib import Path

import pytest

import rizomwheel


@pytest.fixture
def fake_download(monkeypatch):
    """Serve a local archive from ``urlopen``, or raise a URLError."""

    def install(archive: Path | None = None, error: Exception | None = None):
        def urlopen(url):
            if error is not None:
                raise error
            return archive.open("rb")

        monkeypatch.setattr(rizomwheel.urllib.request, "urlopen", urlopen)

    return install


def test_download_repository_returns_the_extracted_root(
    tmp_path, make_repo, make_archive, fake_download, capsys
):
    repo = make_repo(tmp_path / "source")
    fake_download(make_archive(repo, "RizomUVLink-main"))

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    root = rizomwheel.download_repository(work_dir)

    assert root == work_dir / "src" / "RizomUVLink-main"
    assert (root / "RizomUVLink.py").is_file()
    assert (root / "win").is_dir()
    assert (work_dir / "RizomUVLink.tar.gz").is_file()
    assert rizomwheel.REPOSITORY_URL in capsys.readouterr().out


def test_download_repository_reports_network_failure(tmp_path, fake_download):
    fake_download(error=urllib.error.URLError("no route to host"))
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    with pytest.raises(SystemExit, match="Download failed"):
        rizomwheel.download_repository(work_dir)


def test_download_repository_rejects_archive_without_single_root(
    tmp_path, make_repo, fake_download
):
    first = make_repo(tmp_path / "first")
    second = make_repo(tmp_path / "second")
    archive = tmp_path / "two-roots.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(first, arcname="RizomUVLink-main")
        tar.add(second, arcname="RizomUVLink-other")
    fake_download(archive)

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    with pytest.raises(SystemExit, match="Expected one directory"):
        rizomwheel.download_repository(work_dir)


def test_download_repository_rejects_archive_without_any_directory(
    tmp_path, fake_download
):
    archive = tmp_path / "flat.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("README.md")
        info.size = 5
        tar.addfile(info, io.BytesIO(b"hello"))
    fake_download(archive)

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    with pytest.raises(SystemExit, match="Expected one directory"):
        rizomwheel.download_repository(work_dir)
