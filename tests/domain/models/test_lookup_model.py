from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.models.LookupModel import LookupEntry


def test_normalize_name_collapses_whitespace() -> None:
	assert LookupEntry.normalize_name("  Foo   Bar  ") == "foo bar"


def test_validate_entry_requires_valid_fields() -> None:
	entry = LookupEntry(
		guild_id=123,
		name="Staff Guide",
		url="https://example.com/guide",
		created_by=42,
	)
	entry.validate_entry()  # should not raise


@pytest.mark.parametrize(
	"name",
	["", "   ", "\ninvalid"],
)
def test_validate_entry_rejects_bad_names(name: str) -> None:
	entry = LookupEntry(
		guild_id=1,
		name=name,
		url="https://example.com",
		created_by=1,
	)
	with pytest.raises(ValueError):
		entry.validate_entry()


@pytest.mark.parametrize(
	"url",
	["example.com", "ftp://example.com", "http://"],
)
def test_validate_entry_rejects_bad_urls(url: str) -> None:
	entry = LookupEntry(
		guild_id=1,
		name="Valid",
		url=url,
		created_by=1,
	)
	with pytest.raises(ValueError):
		entry.validate_entry()


def test_touch_updated_sets_metadata() -> None:
	entry = LookupEntry(
		guild_id=1,
		name="Valid",
		url="https://example.com",
		created_by=1,
	)
	at = datetime(2030, 1, 1, tzinfo=timezone.utc)
	entry.touch_updated(7, at=at)
	assert entry.updated_by == 7
	assert entry.updated_at == at
