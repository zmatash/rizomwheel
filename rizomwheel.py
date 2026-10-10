"""Build a wheel from the RizomUVLink source on GitHub."""

import argparse
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY_URL = "https://github.com/RemiArq/RizomUVLink/archive/refs/heads/main.tar.gz"
# GitHub serves a source archive per commit under the same /archive/ path.
COMMIT_URL_TEMPLATE = "https://github.com/RemiArq/RizomUVLink/archive/{commit}.tar.gz"

MODULES = ["RizomUVLink.py", "RizomUVLinkBase.py"]
# Each platform's binaries live in their own package; a wheel can carry only one
# platform tag, so every package present in the source becomes its own wheel.
# mac: universal2 binaries built for macOS 10.15 (x86_64) and 11.0 (arm64).
# linux: x86_64 binaries needing glibc 2.17 but GLIBCXX_3.4.21, which is
# beyond what manylinux 2.17 allows, so the 2.24 policy is the honest tag.
PLATFORMS = {
    "win": "win_amd64",
    "mac": "macosx_10_15_universal2",
    "linux": "manylinux_2_24_x86_64",
}
# Compiled modules are named for the Python version they target.
BINARY_PATTERN = re.compile(r"^rizomuvlink_python(\d)(\d+)\.(?:pyd|so)$")
METADATA_FILES = ["README.md", "LICENSE.md"]

DEFAULT_NAME = "rizomuvlink"
DEFAULT_OUTPUT_DIR = "dist"
# valid name
NAME_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
# Full or abbreviated commit hash; anything else could not name a commit anyway.
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")

# Settings accepted under [tool.rizomwheel], mirroring the command line flags.
CONFIG_TABLE = "rizomwheel"
CONFIG_KEYS = ("name", "output-dir", "work-dir", "commit")
CONFIG_FILENAME = "pyproject.toml"

# Constant version, source doesn't provide one and I don't want to generate one.
VERSION = "1.0.0"

PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "{version}"
description = "Python bindings for the RizomUV Link API"
readme = "README.md"
license-files = ["LICENSE.md"]
requires-python = ">={requires_python}"

[tool.hatch.build.targets.wheel]
include = [{include}]
artifacts = ["{package}/*.pyd", "{package}/*.dll", "{package}/*.so"]

[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"
"""

BUILD_HOOK = """\
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        build_data["pure_python"] = False
        build_data["infer_tag"] = False
        build_data["tag"] = "py3-none-{platform_tag}"
"""


def find_config() -> Path | None:
    """Look for a pyproject.toml in the current directory, then its ancestors.

    The nearest one marks the project root, so the search stops there whether or
    not it carries a [tool.rizomwheel] table.
    """
    start = Path.cwd()
    for directory in [start, *start.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config() -> tuple[dict, Path]:
    """Read [tool.rizomwheel] settings, returning them and their base directory.

    Paths in the config are relative to the file holding it, so the returned
    directory is what they should be resolved against.
    """
    config_path = find_config()
    if config_path is None:
        return {}, Path.cwd()

    with config_path.open("rb") as handle:
        try:
            data = tomllib.load(handle)
        except tomllib.TOMLDecodeError as error:
            raise SystemExit(f"Could not parse {config_path}: {error}") from error

    table = data.get("tool", {}).get(CONFIG_TABLE, {})
    if not isinstance(table, dict):
        raise SystemExit(f"[tool.{CONFIG_TABLE}] in {config_path} is not a table")

    for key, value in table.items():
        if key not in CONFIG_KEYS:
            allowed = ", ".join(CONFIG_KEYS)
            raise SystemExit(
                f"Unknown setting {key!r} in [tool.{CONFIG_TABLE}]; expected one of: {allowed}"
            )
        if not isinstance(value, str):
            raise SystemExit(
                f"Setting {key!r} in [tool.{CONFIG_TABLE}] must be a string, got {type(value).__name__}"
            )

    if table:
        print(f"Using settings from [tool.{CONFIG_TABLE}] in {config_path}")
    return table, config_path.parent


def pick_path(
    cli_value: Path | None, config_value: str | None, base: Path
) -> Path | None:
    """Resolve a path setting, preferring the command line over the config."""
    if cli_value is not None:
        return cli_value.resolve()
    if config_value is not None:
        return (base / config_value).resolve()
    return None


def archive_url(commit: str | None) -> str:
    """URL of the source archive for a commit, or for the tip of main."""
    if commit is None:
        return REPOSITORY_URL
    return COMMIT_URL_TEMPLATE.format(commit=commit)


def download_repository(work_dir: Path, commit: str | None = None) -> Path:
    """Download and extract the source, returning the repository root.

    Without a commit this takes the current tip of the main branch.
    """
    url = archive_url(commit)
    archive = work_dir / "RizomUVLink.tar.gz"
    print(f"Downloading {url}")
    try:
        with (
            urllib.request.urlopen(url) as response,
            archive.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as error:
        if error.code == 404 and commit is not None:
            raise SystemExit(
                f"Download failed: no such commit in the repository: {commit}"
            ) from error
        raise SystemExit(f"Download failed: {error}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Download failed: {error}") from error

    extract_dir = work_dir / "src"
    with tarfile.open(archive) as tar:
        tar.extractall(extract_dir, filter="data")

    # GitHub archives wrap everything in a single "<repo>-<branch>" directory.
    roots = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise SystemExit(f"Expected one directory in the archive, found {len(roots)}")
    return roots[0]


def find_platforms(repo: Path) -> list[str]:
    """Platform packages present in the source, in PLATFORMS order.

    Older commits only ship some platforms, so absent ones are skipped.
    """
    platforms = [name for name in PLATFORMS if (repo / name).is_dir()]
    if not platforms:
        expected = ", ".join(PLATFORMS)
        raise SystemExit(f"Missing expected package in source: one of {expected}")
    return platforms


def minimum_python(package: Path) -> str:
    """Oldest Python version a platform package has a compiled module for."""
    versions = []
    for path in package.iterdir():
        match = BINARY_PATTERN.match(path.name)
        if match:
            versions.append((int(match[1]), int(match[2])))
    if not versions:
        raise SystemExit(f"No compiled modules found in source package: {package.name}")
    major, minor = min(versions)
    return f"{major}.{minor}"


def stage_project(repo: Path, build_dir: Path, dist_name: str, platform: str) -> None:
    """Copy the sources for one platform into build_dir with a generated project file."""
    build_dir.mkdir(parents=True, exist_ok=True)

    for name in MODULES:
        source = repo / name
        if not source.is_file():
            raise SystemExit(f"Missing expected module in source: {name}")
        shutil.copy2(source, build_dir / name)

    package = repo / platform
    if not package.is_dir():
        raise SystemExit(f"Missing expected package in source: {platform}")
    shutil.copytree(package, build_dir / platform)

    for name in METADATA_FILES:
        source = repo / name
        if source.is_file():
            shutil.copy2(source, build_dir / name)
        else:
            (build_dir / name).write_text(f"See {REPOSITORY_URL}\n", encoding="utf-8")

    include = ", ".join(f'"{name}"' for name in [*MODULES, platform])
    pyproject = PYPROJECT_TEMPLATE.format(
        name=dist_name,
        version=VERSION,
        include=include,
        package=platform,
        requires_python=minimum_python(package),
    )
    hook = BUILD_HOOK.format(platform_tag=PLATFORMS[platform])
    (build_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (build_dir / "hatch_build.py").write_text(hook, encoding="utf-8")


def build_wheel(build_dir: Path, output_dir: Path) -> None:
    """Run the PEP 517 build, writing the wheel into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "build",
        "--wheel",
        "--outdir",
        str(output_dir),
        str(build_dir),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Wheel build failed with exit code {result.returncode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a wheel from the RizomUVLink source."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help=f"Directory to write the wheel into (default: ./{DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Build in this directory instead of a temporary one, and keep it.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help=f"Distribution name for the generated wheel (default: {DEFAULT_NAME})",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help="Build from this commit hash instead of the latest main branch.",
    )
    return parser.parse_args()


def run(
    work_dir: Path, output_dir: Path, dist_name: str, commit: str | None = None
) -> None:
    repo = download_repository(work_dir, commit)
    platforms = find_platforms(repo)
    for platform in platforms:
        build_dir = work_dir / "build" / platform
        stage_project(repo, build_dir, dist_name, platform)
        build_wheel(build_dir, output_dir)
    print(f"Wheels for {', '.join(platforms)} written to {output_dir}")


def main():
    args = parse_args()
    config, base = load_config()

    dist_name = args.name or config.get("name") or DEFAULT_NAME
    if not NAME_PATTERN.match(dist_name):
        raise SystemExit(f"Not a valid distribution name: {dist_name!r}")

    commit = args.commit or config.get("commit")
    if commit is not None and not COMMIT_PATTERN.match(commit):
        raise SystemExit(f"Not a valid commit hash: {commit!r}")

    output_dir = pick_path(args.output_dir, config.get("output-dir"), base)
    if output_dir is None:
        output_dir = Path(DEFAULT_OUTPUT_DIR).resolve()
    work_dir = pick_path(args.work_dir, config.get("work-dir"), base)

    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        run(work_dir, output_dir, dist_name, commit)
        print(f"Build tree kept at {work_dir}")
    else:
        with tempfile.TemporaryDirectory(
            prefix="rizomwheel-", ignore_cleanup_errors=True
        ) as temp_dir:
            run(Path(temp_dir), output_dir, dist_name, commit)


if __name__ == "__main__":
    main()
