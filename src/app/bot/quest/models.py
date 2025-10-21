from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
