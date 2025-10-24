from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

import discord

from app.domain.models.QuestModel import QuestStatus


@dataclass
class QuestEmbedRoster:
	"""Container for roster sections rendered in the quest embed."""

	selected: Sequence[str] = field(default_factory=list)
	pending: Sequence[str] = field(default_factory=list)
	waitlist: Sequence[str] = field(default_factory=list)


@dataclass
class QuestEmbedData:
	"""Lightweight aggregate describing how to render a quest embed."""

	quest_id: str
	title: str | None = None
	description: str | None = None
	status: QuestStatus | str | None = None
	starting_at: datetime | None = None
	duration: timedelta | None = None
	referee_display: str | None = None
	roster: QuestEmbedRoster = field(default_factory=QuestEmbedRoster)
	image_url: str | None = None
	last_updated_at: datetime | None = None
	approved_by_display: str | None = None


def build_quest_embed(data: QuestEmbedData) -> discord.Embed:
	"""Return a quest embed with consistent sections used across flows."""

	title = data.title or "Untitled Quest"
	description = data.description or "No description provided."

	embed = discord.Embed(title=title, description=description, colour=discord.Color.blurple())

	embed.add_field(name="🎯 Quest", value=_format_quest_section(data), inline=False)
	embed.add_field(name="⏰ Time", value=_format_time_section(data.starting_at, data.duration), inline=False)
	embed.add_field(name="🧑‍🤝‍🧑 Players", value=_format_players_section(data.roster), inline=False)

	footer_text = _format_footer(
		quest_id=data.quest_id,
		status=data.status,
		approved_by=data.approved_by_display,
		last_updated=data.last_updated_at,
	)
	embed.set_footer(text=footer_text)

	if data.image_url:
		embed.set_image(url=data.image_url)

	return embed


def _format_quest_section(data: QuestEmbedData) -> str:
	status_text = _format_status(data.status)
	referee = data.referee_display or "Unassigned"
	lines = [f"Status: {status_text}", f"Referee: {referee}"]
	return "\n".join(lines)


def _format_time_section(starting_at: datetime | None, duration: timedelta | None) -> str:
	if starting_at is None and duration is None:
		return "Schedule: To be announced"

	lines: list[str] = []

	if starting_at is not None:
		if starting_at.tzinfo is None:
			starting_at = starting_at.replace(tzinfo=timezone.utc)
		epoch = int(starting_at.timestamp())
		lines.append(f"Starts: <t:{epoch}:F>")
		lines.append(f"Countdown: <t:{epoch}:R>")
	else:
		lines.append("Starts: Not scheduled")

	if duration is not None:
		hours = max(int(duration.total_seconds() // 3600), 0)
		minutes = int((duration.total_seconds() % 3600) // 60)
		if hours and minutes:
			lines.append(f"Duration: {hours}h {minutes}m")
		elif hours:
			lines.append(f"Duration: {hours}h")
		elif minutes:
			lines.append(f"Duration: {minutes}m")
		else:
			lines.append("Duration: < 1m")
	else:
		lines.append("Duration: Not set")

	return "\n".join(lines)


def _format_players_section(roster: QuestEmbedRoster) -> str:
	blocks: list[str] = []

	if roster.selected:
		blocks.append(_format_labeled_list("Selected", roster.selected))

	if roster.pending:
		blocks.append(_format_labeled_list("Pending", roster.pending))

	if roster.waitlist:
		blocks.append(_format_labeled_list("Waitlist", roster.waitlist))

	if not blocks:
		return "No sign-ups yet."

	return "\n\n".join(blocks)


def _format_labeled_list(label: str, items: Iterable[str]) -> str:
	lines = [f"{label}:"]
	for item in items:
		lines.append(f"- {item}")
	return "\n".join(lines)


def _format_footer(
	*,
	quest_id: str,
	status: QuestStatus | str | None,
	approved_by: str | None,
	last_updated: datetime | None,
) -> str:
	indicator = _format_state_indicator(status)
	parts = [f"Quest ID: {quest_id}", indicator]

	meta_bits: list[str] = []
	if approved_by:
		meta_bits.append(f"Approved by {approved_by}")

	if last_updated is not None:
		if last_updated.tzinfo is None:
			last_updated = last_updated.replace(tzinfo=timezone.utc)
		epoch = int(last_updated.timestamp())
		meta_bits.append(f"Updated <t:{epoch}:R>")

	if meta_bits:
		parts.append(" - ".join(meta_bits))

	return " • ".join(parts)


def _format_status(status: QuestStatus | str | None) -> str:
	if status is None:
		return "Unknown"

	if isinstance(status, QuestStatus):
		label = status.value
	else:
		label = str(status)

	normalized = label.replace("_", " ").title()
	return normalized


def _format_state_indicator(status: QuestStatus | str | None) -> str:
	concrete = _coerce_status(status)
	if concrete in {QuestStatus.ANNOUNCED, QuestStatus.DRAFT}:
		return "🟢 Active"
	if concrete in {QuestStatus.SIGNUP_CLOSED, QuestStatus.COMPLETED, QuestStatus.CANCELLED}:
		return "🔴 Closed"
	return f"⚪ {_format_status(status)}"


def _coerce_status(status: QuestStatus | str | None) -> QuestStatus | None:
	if isinstance(status, QuestStatus):
		return status
	if isinstance(status, str):
		try:
			return QuestStatus(status.upper())
		except ValueError:
			return None
	return None
