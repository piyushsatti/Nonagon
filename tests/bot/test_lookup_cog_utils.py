from __future__ import annotations

from datetime import datetime, timezone

from app.bot.cogs.LookupCommandsCog import _build_lookup_embed
from app.domain.models.LookupModel import LookupEntry


def test_build_lookup_embed_includes_timestamp() -> None:
	entry = LookupEntry(
		guild_id=1,
		name="Guide",
		url="https://example.com/guide",
		created_by=10,
		created_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
	)
	entry.touch_updated(20, at=datetime(2030, 1, 2, tzinfo=timezone.utc))

	embed = _build_lookup_embed(entry)

	assert embed.title == "Guide"
	assert embed.fields[0].value == "https://example.com/guide"
	assert "Updated by <@20>" in embed.fields[1].value
