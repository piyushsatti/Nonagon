#!/usr/bin/env python3
"""
Convert leading indentation in Python files from spaces/tabs mix to tabs only.

Rules:
- A tab stop is considered width 4.
- Leading indentation is converted to tabs so that the resulting visual
	indentation is >= the original (never less). This avoids under-indenting.
- Any residual leading spaces are removed by rounding up to the next tab.

Use with care; review diffs. Intended for bulk migration to a tabs-only policy.
"""
from __future__ import annotations

import pathlib
import sys

TABSTOP = 4


def to_tabs_prefix(s: str) -> str:
	# Compute visual columns of the leading whitespace
	cols = 0
	i = 0
	n = len(s)
	while i < n and s[i] in (" ", "\t"):
		if s[i] == "\t":
			cols += TABSTOP - (cols % TABSTOP)
		else:
			cols += 1
		i += 1
	# Round up to next tab boundary to eliminate any partial spaces
	if cols % TABSTOP != 0:
		cols += TABSTOP - (cols % TABSTOP)
	tabs = "\t" * (cols // TABSTOP)
	return tabs + s[i:]


def convert_file(path: pathlib.Path) -> bool:
	text = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
	changed = False
	for idx, line in enumerate(text):
		if not line or line[0] not in (" ", "\t"):
			continue
		new_line = to_tabs_prefix(line)
		if new_line != line:
			text[idx] = new_line
			changed = True
	if changed:
		path.write_text("".join(text), encoding="utf-8")
	return changed


def main(argv: list[str]) -> int:
	if len(argv) <= 1:
		return 0
	total_changed = 0
	for name in argv[1:]:
		p = pathlib.Path(name)
		if not p.exists() or not p.is_file():
			continue
		if convert_file(p):
			total_changed += 1
	print(f"Converted {total_changed} files to tabs (where needed)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv))
