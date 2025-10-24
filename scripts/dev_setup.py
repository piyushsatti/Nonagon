#!/usr/bin/env python3
"""
Developer bootstrap: install dev dependencies and pre-commit hooks.

Usage:
python scripts/dev_setup.py
"""
from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> int:
	print("$", " ".join(cmd))
	return subprocess.call(cmd)


def main() -> int:
	code = run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"]) or 0
	code = run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"]) or code
	code = run([sys.executable, "-m", "pre_commit", "install"]) or code
	if code == 0:
		print("Pre-commit installed. You can now run 'pre-commit run -a'.")
	else:
		print("There was an issue installing hooks. Try running 'pip install pre-commit' then 'pre-commit install'.")
	return code


if __name__ == "__main__":
	raise SystemExit(main())
