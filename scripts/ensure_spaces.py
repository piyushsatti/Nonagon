#!/usr/bin/env python3
"""Pre-commit helper: ensure leading indentation uses spaces for Python files.

This script scans files passed as arguments (or all .py files under the
repository if none provided) and exits with code 1 if any line begins with a
tab character. It's intentionally small and dependency-free so pre-commit can
run it in CI and locally.
"""
import sys
from pathlib import Path


def check_file(path: Path) -> int:
    has_error = 0
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0

    for i, line in enumerate(text.splitlines(), start=1):
        if line.startswith("\t"):
            print(f"{path}:{i}: Leading tab character found")
            has_error = 1
    return has_error


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        files = [Path(p) for p in argv[1:]]
    else:
        files = list(Path('.').rglob('*.py'))

    exit_code = 0
    for f in files:
        exit_code |= check_file(f)

    return exit_code


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
