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
    requested = []

    def install(archive: Path | None = None, error: Exception | None = None):
        def urlopen(url):
            requested.append(url)
            if error is not None:
                raise error
            return archive.open("rb")

        monkeypatch.setattr(rizomwheel.urllib.request, "urlopen", urlopen)
        return requested

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


def test_archive_url_defaults_to_the_main_branch():
    assert rizomwheel.archive_url(None) == rizomwheel.REPOSITORY_URL


def test_archive_url_points_at_the_requested_commit():
    url = rizomwheel.archive_url("abc1234")
    assert url.endswith("/archive/abc1234.tar.gz")


def test_download_repository_fetches_the_requested_commit(
    tmp_path, make_repo, make_archive, fake_download, capsys
):
    repo = make_repo(tmp_path / "source")
    requested = fake_download(make_archive(repo, "RizomUVLink-abc1234"))

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    root = rizomwheel.download_repository(work_dir, "abc1234")

    assert requested == [rizomwheel.archive_url("abc1234")]
    assert root == work_dir / "src" / "RizomUVLink-abc1234"
    assert (root / "RizomUVLink.py").is_file()
    assert "abc1234" in capsys.readouterr().out


def test_download_repository_reports_an_unknown_commit(tmp_path, fake_download):
    fake_download(
        error=urllib.error.HTTPError(
            rizomwheel.archive_url("abc1234"), 404, "Not Found", {}, None
        )
    )
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    with pytest.raises(SystemExit, match="no such commit"):
        rizomwheel.download_repository(work_dir, "abc1234")


def test_download_repository_reports_other_http_errors(tmp_path, fake_download):
    fake_download(
        error=urllib.error.HTTPError(
            rizomwheel.REPOSITORY_URL, 500, "Server Error", {}, None
        )
    )
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    with pytest.raises(SystemExit, match="Download failed: HTTP Error 500"):
        rizomwheel.download_repository(work_dir)


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
