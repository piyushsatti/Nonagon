#!/usr/bin/env python3
"""Fail if any provided Python file has leading indentation containing tabs."""

from __future__ import annotations

import pathlib
import re
import sys

TAB_LEADING = re.compile(r"^(\t+)\S")
MIXED_LEADING = re.compile(r"^( +\t+)\S")


def check_file(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as exc:  # pragma: no cover
        return [f"{path}: unable to read file: {exc}"]

    for i, line in enumerate(text, start=1):
        if not line or line.strip() == "":
            continue
        if MIXED_LEADING.match(line):
            problems.append(f"{path}:{i}: leading indentation mixes spaces and tabs")
            continue
        if TAB_LEADING.match(line):
            problems.append(f"{path}:{i}: leading indentation uses tabs; use spaces")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) <= 1:
        return 0
    all_problems: list[str] = []
    for name in argv[1:]:
        path = pathlib.Path(name)
        if not path.exists():
            continue
        all_problems.extend(check_file(path))
    if all_problems:
        print("Python indentation policy violation (spaces required):", file=sys.stderr)
        for problem in all_problems:
            print(problem, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv))
