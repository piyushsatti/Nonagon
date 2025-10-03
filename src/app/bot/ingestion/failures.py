from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Sequence


@dataclass(slots=True)
class IngestFailureRecord:
    """Represents a failed ingestion attempt that still needs to preserve input."""

    kind: str
    guild_id: str
    channel_id: str
    message_id: str
    author_id: str
    raw_content: str
    reason: str
    errors: Sequence[str] | None = None
    metadata: Mapping[str, str | None] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_document(self) -> dict[str, object]:
        metadata: dict[str, str | None] | None = None
        if self.metadata is not None:
            metadata = {key: (value or "") for key, value in self.metadata.items()}
        return {
            "kind": self.kind,
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "author_id": self.author_id,
            "raw_content": self.raw_content,
            "reason": self.reason,
            "errors": list(self.errors) if self.errors else [],
            "metadata": metadata,
            "created_at": self.created_at,
        }
