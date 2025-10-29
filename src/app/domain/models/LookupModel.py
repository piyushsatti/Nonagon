from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse


@dataclass(slots=True)
class LookupEntry:
    guild_id: int
    name: str
    url: str
    created_by: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    description: Optional[str] = None

    @staticmethod
    def normalize_name(name: str) -> str:
        """Return a whitespace-collapsed, lower-cased name for lookups."""
        collapsed = " ".join(part for part in name.split() if part)
        return collapsed.lower()

    def validate_entry(self) -> None:
        self._validate_guild()
        self._validate_name()
        self._validate_url()
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.updated_at and self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")

    def touch_updated(self, user_id: int, *, at: Optional[datetime] = None) -> None:
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            raise ValueError("touch_updated requires a timezone-aware datetime")
        self.updated_by = user_id
        self.updated_at = moment

    def _validate_guild(self) -> None:
        if self.guild_id <= 0:
            raise ValueError("guild_id must be a positive integer")

    def _validate_name(self) -> None:
        trimmed = self.name.strip()
        if not trimmed:
            raise ValueError("name cannot be empty")
        if len(trimmed) > 80:
            raise ValueError("name must be 80 characters or fewer")
        if any(ord(ch) < 32 for ch in self.name):
            raise ValueError("name cannot contain control characters")

    def _validate_url(self) -> None:
        parsed = urlparse(self.url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must start with http:// or https:// and include a host")
