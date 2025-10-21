#!/usr/bin/env python3
"""
Backfill the `guild_id` field for legacy MongoDB documents.

The bot historically operated in a single-guild mode and stored records
without a guild identifier. This script fills in missing `guild_id` values
and ensures the supporting compound indexes exist so that documents can be
scoped per guild going forward.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple

from pymongo import ASCENDING, MongoClient

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.infra.settings import DB_NAME, MONGODB_URI  # noqa: E402

CollectionSpec = Tuple[Iterable[Tuple[str, int]], Dict[str, object]]

INDEX_SPECS: Dict[str, Tuple[CollectionSpec, ...]] = {
    "users": (
        ((("guild_id", ASCENDING), ("user_id.value", ASCENDING)), {"unique": True, "name": "guild_user_value"}),
        ((("guild_id", ASCENDING), ("discord_id", ASCENDING)), {"unique": True, "sparse": True, "name": "guild_discord_id"}),
    ),
    "quests": (
        ((("guild_id", ASCENDING), ("quest_id.value", ASCENDING)), {"unique": True, "name": "guild_quest_value"}),
        ((("guild_id", ASCENDING), ("channel_id", ASCENDING), ("message_id", ASCENDING)), {"unique": True, "name": "guild_channel_message"}),
    ),
    "characters": (
        ((("guild_id", ASCENDING), ("character_id.value", ASCENDING)), {"unique": True, "name": "guild_character_value"}),
        ((("guild_id", ASCENDING), ("owner_id.value", ASCENDING)), {"name": "guild_character_owner"}),
    ),
    "summaries": (
        ((("guild_id", ASCENDING), ("summary_id.value", ASCENDING)), {"unique": True, "name": "guild_summary_value"}),
        ((("guild_id", ASCENDING), ("author_id.value", ASCENDING)), {"name": "guild_summary_author"}),
    ),
}

BACKFILL_COLLECTIONS = tuple(INDEX_SPECS.keys())


def ensure_indexes(db) -> None:
    """Create the per-guild compound indexes required by the new schema."""
    for coll_name, specs in INDEX_SPECS.items():
        coll = db[coll_name]
        for keys, kwargs in specs:
            coll.create_index(list(keys), **kwargs)


def _missing_guild_filter(_: int) -> Dict[str, object]:
    """
    Build a filter that matches documents without an integer guild_id.

    Documents are considered missing if the field is absent, null, or stored as a
    non-integer type (legacy string/float encodings).
    """
    return {
        "$or": [
            {"guild_id": {"$exists": False}},
            {"guild_id": None},
            {"guild_id": {"$type": "string"}},
            {"guild_id": {"$type": "double"}},
            {"guild_id": {"$type": "decimal"}},
            {"guild_id": {"$type": "long"}},
        ]
    }


def backfill_guild_id(db, guild_id: int, dry_run: bool) -> Dict[str, Dict[str, int]]:
    """Populate the `guild_id` field for each collection and return a summary."""
    summary: Dict[str, Dict[str, int]] = {}
    filter_doc = _missing_guild_filter(guild_id)
    update_doc = {"$set": {"guild_id": guild_id}}

    for coll_name in BACKFILL_COLLECTIONS:
        coll = db[coll_name]
        if dry_run:
            matched = coll.count_documents(filter_doc)
            summary[coll_name] = {"matched": matched, "modified": 0}
            logging.info("[DRY RUN] %s would update %s documents", coll_name, matched)
            continue

        result = coll.update_many(filter_doc, update_doc)
        summary[coll_name] = {
            "matched": result.matched_count,
            "modified": result.modified_count,
        }
        logging.info(
            "%s: matched=%s modified=%s",
            coll_name,
            result.matched_count,
            result.modified_count,
        )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing guild_id fields for legacy Nonagon data."
    )
    parser.add_argument(
        "--guild-id",
        type=int,
        required=True,
        help="Discord guild id that should be written to records missing guild_id.",
    )
    parser.add_argument(
        "--uri",
        default=MONGODB_URI,
        help="MongoDB connection string (default: %(default)s).",
    )
    parser.add_argument(
        "--database",
        default=DB_NAME,
        help="Database name containing legacy collections (default: %(default)s).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write changes; only report the number of documents that would update.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.info(
        "Running guild_id backfill for db=%s (guild=%s) [dry_run=%s]",
        args.database,
        args.guild_id,
        args.dry_run,
    )

    client = MongoClient(args.uri)
    db = client[args.database]

    ensure_indexes(db)
    summary = backfill_guild_id(db, args.guild_id, args.dry_run)

    logging.info("Backfill summary: %s", summary)
    client.close()


if __name__ == "__main__":
    main()
