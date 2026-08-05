"""Build a wheel from the latest RizomUVLink source on GitHub."""

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

MODULES = ["RizomUVLink.py", "RizomUVLinkBase.py"]
PACKAGES = ["win"]
METADATA_FILES = ["README.md", "LICENSE.md"]

DEFAULT_NAME = "rizomuvlink"
DEFAULT_OUTPUT_DIR = "dist"
# valid name
NAME_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")

# Settings accepted under [tool.rizomwheel], mirroring the command line flags.
CONFIG_TABLE = "rizomwheel"
CONFIG_KEYS = ("name", "output-dir", "work-dir")
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
requires-python = ">=3.6"

[tool.hatch.build.targets.wheel]
include = [{include}]
artifacts = ["win/*.pyd", "win/*.dll"]

[tool.hatch.build.targets.wheel.hooks.custom]
path = "hatch_build.py"
"""

BUILD_HOOK = """\
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        build_data["pure_python"] = False
        build_data["infer_tag"] = False
        build_data["tag"] = "py3-none-win_amd64"
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


def download_repository(work_dir: Path) -> Path:
    """Download and extract the latest source, returning the repository root."""
    archive = work_dir / "RizomUVLink.tar.gz"
    print(f"Downloading {REPOSITORY_URL}")
    try:
        with (
            urllib.request.urlopen(REPOSITORY_URL) as response,
            archive.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
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


def stage_project(repo: Path, build_dir: Path, dist_name: str) -> None:
    """Copy the sources into build_dir alongside a generated project file."""
    build_dir.mkdir(parents=True, exist_ok=True)

    for name in MODULES:
        source = repo / name
        if not source.is_file():
            raise SystemExit(f"Missing expected module in source: {name}")
        shutil.copy2(source, build_dir / name)

    for name in PACKAGES:
        source = repo / name
        if not source.is_dir():
            raise SystemExit(f"Missing expected package in source: {name}")
        shutil.copytree(source, build_dir / name)

    for name in METADATA_FILES:
        source = repo / name
        if source.is_file():
            shutil.copy2(source, build_dir / name)
        else:
            (build_dir / name).write_text(f"See {REPOSITORY_URL}\n", encoding="utf-8")

    include = ", ".join(f'"{name}"' for name in MODULES + PACKAGES)
    pyproject = PYPROJECT_TEMPLATE.format(
        name=dist_name, version=VERSION, include=include
    )
    (build_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (build_dir / "hatch_build.py").write_text(BUILD_HOOK, encoding="utf-8")


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
        description="Build a wheel from the latest RizomUVLink source."
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
    return parser.parse_args()


def run(work_dir: Path, output_dir: Path, dist_name: str) -> None:
    repo = download_repository(work_dir)
    build_dir = work_dir / "build"
    stage_project(repo, build_dir, dist_name)
    build_wheel(build_dir, output_dir)
    print(f"Wheel written to {output_dir}")


def main():
    args = parse_args()
    config, base = load_config()

    dist_name = args.name or config.get("name") or DEFAULT_NAME
    if not NAME_PATTERN.match(dist_name):
        raise SystemExit(f"Not a valid distribution name: {dist_name!r}")

    output_dir = pick_path(args.output_dir, config.get("output-dir"), base)
    if output_dir is None:
        output_dir = Path(DEFAULT_OUTPUT_DIR).resolve()
    work_dir = pick_path(args.work_dir, config.get("work-dir"), base)

    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        run(work_dir, output_dir, dist_name)
        print(f"Build tree kept at {work_dir}")
    else:
        with tempfile.TemporaryDirectory(
            prefix="rizomwheel-", ignore_cleanup_errors=True
        ) as temp_dir:
            run(Path(temp_dir), output_dir, dist_name)


if __name__ == "__main__":
    main()
