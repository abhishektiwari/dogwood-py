from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "dogwood" / "_version.py"


def main() -> int:
    version = _project_version() or _rust_package_version()
    VERSION_FILE.write_text(
        "# file generated during dogwood-py builds\n"
        f'__version__ = version = "{version}"\n'
        f'__version_tuple__ = version_tuple = tuple("{version}".replace("-", ".").split("."))\n'
    )
    print(version)
    return 0


def _project_version() -> str | None:
    section = ""
    for line in (ROOT / "pyproject.toml").read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            continue
        if section == "[project]":
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return None


def _rust_package_version() -> str:
    section = ""
    for line in (ROOT / "rust" / "Cargo.toml").read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            continue
        if section == "[package]":
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    raise RuntimeError("could not determine package version")


if __name__ == "__main__":
    raise SystemExit(main())
