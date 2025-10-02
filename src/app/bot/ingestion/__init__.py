"""Consolidated quest ingestion helpers for the Discord bot."""

from .links import DiscordMessageKey, resolve_linked_quests
from .pipeline import (
    LinkedQuestRecord,
    ParsedQuest,
    ParseError,
    QuestRecord,
    ValidationError,
    ValidationIssue,
    document_to_record,
    map_parsed_to_record,
    parse_message,
    record_to_document,
    validate,
)

__all__ = [
    "DiscordMessageKey",
    "resolve_linked_quests",
    "ParseError",
    "ParsedQuest",
    "QuestRecord",
    "LinkedQuestRecord",
    "ValidationError",
    "ValidationIssue",
    "parse_message",
    "validate",
    "map_parsed_to_record",
    "record_to_document",
    "document_to_record",
]
