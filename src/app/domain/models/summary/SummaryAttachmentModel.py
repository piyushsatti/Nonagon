from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

__all__ = ["SummaryAttachment"]


@dataclass(slots=True)
class SummaryAttachment:
    kind: Literal["image", "video", "file", "embed", "link"]
    url: str
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
