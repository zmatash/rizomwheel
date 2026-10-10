# rizomwheel

Builds an installable wheel from the latest [RizomUVLink](https://github.com/RemiArq/RizomUVLink)
source on GitHub.

The source project ships as loose files rather than a package. rizomwheel downloads the main branch and generates a wheel package.

## Requirements

- Python 3.13+

## Install

```sh
uv tool install git+https://github.com/zmatash/rizomwheel.git
```

To run it once without installing:

```sh
uvx --from git+https://github.com/zmatash/rizomwheel.git rizomwheel
```

## Usage 

```sh
rizomwheel [-o OUTPUT_DIR] [--work-dir WORK_DIR] [--name NAME] [--commit COMMIT]
```

The default run downloads the source, builds, and writes the wheels to `./dist`.

One wheel is built for each platform the source ships binaries for. pip picks the right one
for the machine it installs on:

| Platform | Wheel tag | Python |
| --- | --- | --- |
| Windows | `win_amd64` | 3.6+ |
| macOS | `macosx_10_15_universal2` (Intel and Apple Silicon) | 3.9+ |
| Linux | `manylinux_2_24_x86_64` | 3.9+ |

Older commits that only ship some platforms build only those wheels.

### Options

| Flag | Default | Description |
| --- | --- | --- |
| `-o`, `--output-dir` | `./dist` | Directory to write the wheel into. Created if missing. |
| `--work-dir` | a temporary directory | Build in this directory instead, and keep it afterwards. Useful for inspecting the staged project. |
| `--name` | `rizomuvlink` | Distribution name for the generated wheel. |
| `--commit` | latest on `main` | Build from this commit instead. Full or abbreviated hash (7+ characters). |
| `-h`, `--help` | | Show usage and exit. |

Examples:

```sh
# write somewhere else
rizomwheel --output-dir C:/wheels

# keep the build tree to see what was staged
rizomwheel --work-dir ./scratch

# override the wheel name
rizomwheel --name rizomuvlink-alt

# pin the source to a commit
rizomwheel --commit dfe9502
```

The wheel version is always `1.0.0`. The source repo does not publish a version, and one is not
added here.

## Configuration file

Settings can live in a `[tool.rizomwheel]` table. The nearest `pyproject.toml` is found by searching the current directory and then
its ancestors.

```toml
[tool.rizomwheel]
name = "rizomuvlink"
output-dir = "dist"
work-dir = "build/rizomwheel"
commit = "dfe9502"
```

## Disclaimer

This is an unofficial, third-party tool. It is not affiliated with Rizom-Lab.
