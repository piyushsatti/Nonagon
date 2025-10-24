from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass(slots=True)
class ForgePreviewState:
	thread_id: Optional[int] = None
	preview_message_id: Optional[int] = None
	last_rendered_at: Optional[datetime] = None


@dataclass(slots=True)
class ForgeDraft:
	raw: str
	title: Optional[str] = None
	description: Optional[str] = None
	starting_at: Optional[datetime] = None
	duration: Optional[timedelta] = None
	image_url: Optional[str] = None


TITLE_KEYS = {"title", "name", "quest"}
START_KEYS = {"start", "starts", "when"}
DURATION_KEYS = {"duration", "length"}
IMAGE_KEYS = {"image", "cover", "thumbnail"}


def parse_start_datetime(value: str) -> Optional[datetime]:
	"""Parse a start timestamp from user-provided text."""
	text = (value or "").strip()
	if not text:
		return None

	match = re.search(r"<t:(\d+)", text)
	if match:
		seconds = int(match.group(1))
		return datetime.fromtimestamp(seconds, tz=timezone.utc)

	normalized = text.replace("UTC", "+00:00").replace("utc", "+00:00")
	for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
		try:
			dt = datetime.strptime(normalized, fmt)
			return dt.replace(tzinfo=timezone.utc)
		except ValueError:
			continue

	try:
		dt = datetime.fromisoformat(normalized)
		if dt.tzinfo is None:
			dt = dt.replace(tzinfo=timezone.utc)
		return dt.astimezone(timezone.utc)
	except ValueError:
		return None


def parse_duration(value: str) -> Optional[timedelta]:
	"""Parse a quest duration from user-provided text."""
	text = (value or "").strip().lower()
	if not text:
		return None

	hours = 0
	minutes = 0

	hour_matches = re.findall(r"(\d+)\s*h", text)
	if hour_matches:
		hours = sum(int(entry) for entry in hour_matches)

	minute_matches = re.findall(r"(\d+)\s*m", text)
	if minute_matches:
		minutes = sum(int(entry) for entry in minute_matches)

	if hours == 0 and minutes == 0:
		try:
			hours = int(text)
		except ValueError:
			return None

	return timedelta(hours=hours, minutes=minutes)


def _assign_metadata(key: str, value: str, draft: ForgeDraft) -> bool:
	lowered = key.lower().strip()
	stripped_value = value.strip()

	if lowered in TITLE_KEYS and not draft.title:
		draft.title = stripped_value or None
		return True

	if lowered in START_KEYS:
		parsed_start = parse_start_datetime(stripped_value)
		if parsed_start is not None:
			draft.starting_at = parsed_start
			return True
		return False

	if lowered in DURATION_KEYS:
		parsed_duration = parse_duration(stripped_value)
		if parsed_duration is not None:
			draft.duration = parsed_duration
			return True
		return False

	if lowered in IMAGE_KEYS and stripped_value.lower().startswith("http"):
		draft.image_url = stripped_value
		return True

	return False


def parse_forge_draft(raw: str) -> ForgeDraft:
	"""Convert forge channel markdown into a structured draft."""
	draft = ForgeDraft(raw=raw)
	body_lines: list[str] = []

	for line in (raw or "").splitlines():
		stripped = line.strip()
		if not stripped:
			body_lines.append(stripped)
			continue

		key, sep, value = stripped.partition(":")
		if not sep or not _assign_metadata(key, value, draft):
			body_lines.append(stripped)

	if draft.title is None:
		for idx, line in enumerate(body_lines):
			if line:
				draft.title = line
				body_lines = body_lines[idx + 1 :]
				break

	draft.description = "\n".join(body_lines).strip() or None
	return draft
