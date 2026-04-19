#!/usr/bin/env python3
"""Bump the version across all forge packages in one atomic step.

Usage:
    python bump_version.py 0.1.17
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def bump(new_version: str) -> None:
    # 1. forge/version.py
    version_py = ROOT / "packages/forge-py/forge/version.py"
    content = version_py.read_text()
    content = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content)
    content = re.sub(r'TS_VERSION = "[^"]+"', f'TS_VERSION = "{new_version}"', content)
    version_py.write_text(content)
    print(f"  updated {version_py.relative_to(ROOT)}")

    # 2. forge-py/pyproject.toml
    forge_py_toml = ROOT / "packages/forge-py/pyproject.toml"
    content = forge_py_toml.read_text()
    content = re.sub(r'^version = "[^"]+"', f'version = "{new_version}"', content, flags=re.MULTILINE)
    forge_py_toml.write_text(content)
    print(f"  updated {forge_py_toml.relative_to(ROOT)}")

    # 3. forge-suite/pyproject.toml (package version + exact dependency pin)
    forge_suite_toml = ROOT / "packages/forge-suite/pyproject.toml"
    content = forge_suite_toml.read_text()
    content = re.sub(r'^version = "[^"]+"', f'version = "{new_version}"', content, flags=re.MULTILINE)
    content = re.sub(r'"forge-framework==[^"]+"', f'"forge-framework=={new_version}"', content)
    forge_suite_toml.write_text(content)
    print(f"  updated {forge_suite_toml.relative_to(ROOT)}")

    # 4. forge-ts/package.json
    pkg_json_path = ROOT / "packages/forge-ts/package.json"
    pkg = json.loads(pkg_json_path.read_text())
    pkg["version"] = new_version
    pkg_json_path.write_text(json.dumps(pkg, indent=2) + "\n")
    print(f"  updated {pkg_json_path.relative_to(ROOT)}")

    print(f"\nAll packages bumped to {new_version}")
    print("Next steps:")
    print("  1. Review the diff and commit")
    print("  2. Build and publish forge-framework first:")
    print("       cd packages/forge-py && python -m build && twine upload dist/*")
    print("  3. Then publish forge-suite:")
    print("       cd packages/forge-suite && python -m build && twine upload dist/*")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {Path(__file__).name} <new_version>")
        sys.exit(1)
    bump(sys.argv[1])
