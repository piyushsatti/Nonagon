#!/usr/bin/env python3
"""
Reset demo data for a given Discord guild database.

Usage:
	python scripts/reset_demo.py --guild-id <guild_id>
"""
from __future__ import annotations

import argparse
import logging

from app.bot import database


def reset_demo(guild_id: str) -> None:
	logging.info("Dropping demo database %s", guild_id)
	database.delete_db(guild_id)
	logging.info("Deleted database %s. It will be recreated on next bot startup.", guild_id)


def main() -> None:
	parser = argparse.ArgumentParser(description="Reset Nonagon demo data")
	parser.add_argument("--guild-id", required=True, help="Discord guild id backing the demo database")
	args = parser.parse_args()

	logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
	reset_demo(args.guild_id)


if __name__ == "__main__":
	main()
