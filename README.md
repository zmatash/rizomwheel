# rizomwheel

Builds an installable wheel from the latest [RizomUVLink](https://github.com/RemiArq/RizomUVLink)
source on GitHub.

The source project ships as loose files rather than a package. rizomwheel downloads the main branch and generates a wheel package.

## Requirements

- Python 3.13+

## Install

```sh
uv add rizomwheel
```

## Usage 

```sh
rizomwheel [-o OUTPUT_DIR] [--work-dir WORK_DIR] [--name NAME]
```

The default run downloads the source, builds, and writes the wheel to `./dist`:

### Options

| Flag | Default | Description |
| --- | --- | --- |
| `-o`, `--output-dir` | `./dist` | Directory to write the wheel into. Created if missing. |
| `--work-dir` | a temporary directory | Build in this directory instead, and keep it afterwards. Useful for inspecting the staged project. |
| `--name` | `rizomuvlink` | Distribution name for the generated wheel. |
| `-h`, `--help` | | Show usage and exit. |

Examples:

```sh
# write somewhere else
rizomwheel --output-dir C:/wheels

# keep the build tree to see what was staged
rizomwheel --work-dir ./scratch

# override the wheel name
rizomwheel --name rizomuvlink-alt
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
```
