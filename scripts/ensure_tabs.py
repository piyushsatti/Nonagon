#!/usr/bin/env python3
"""
Fail if any provided Python file has leading indentation that contains spaces.

Rules:
- Leading indentation must use tabs only (no spaces).
- Mixed indentation (tabs then spaces) is also rejected.

This is intentionally strict to keep a consistent tab policy.
"""

from __future__ import annotations

import pathlib
import re
import sys

SPACE_LEADING = re.compile(r"^( +)\S")
MIXED_LEADING = re.compile(r"^(\t+ +)\S")


def check_file(path: pathlib.Path) -> list[str]:
	problems: list[str] = []
	try:
		text = path.read_text(encoding="utf-8", errors="replace").splitlines()
	except Exception as exc:  # pragma: no cover
		return [f"{path}: unable to read file: {exc}"]

	for i, line in enumerate(text, start=1):
		# Ignore empty or all-whitespace lines
		if not line or line.strip() == "":
			continue
		# Mixed indentation: tabs followed by spaces at the start
		if MIXED_LEADING.match(line):
			problems.append(f"{path}:{i}: leading indentation mixes tabs and spaces")
			continue
		# Any leading spaces at the start are disallowed
		if SPACE_LEADING.match(line):
			problems.append(f"{path}:{i}: leading indentation uses spaces; use tabs")
			continue
	return problems


def main(argv: list[str]) -> int:
	if len(argv) <= 1:
		# pre-commit may pass no files depending on filters
		return 0
	all_problems: list[str] = []
	for name in argv[1:]:
		path = pathlib.Path(name)
		if not path.exists():
			continue
		all_problems.extend(check_file(path))
	if all_problems:
		print("Python indentation policy violation (tabs required):", file=sys.stderr)
		for p in all_problems:
			print(p, file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":  # pragma: no cover
	raise SystemExit(main(sys.argv))
