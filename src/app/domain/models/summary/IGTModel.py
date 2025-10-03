from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

__all__ = ["InGameTime", "parse_in_game_time"]


@dataclass(slots=True)
class InGameTime:
    raw: str
    season: Optional[str] = None
    week: Optional[int] = None


def parse_in_game_time(raw: str) -> InGameTime:
    """Best-effort parser for inputs such as "Planting W2" or "Planting week 2"."""
    season: Optional[str] = None
    week: Optional[int] = None

    if raw:
        tokens = raw.strip().split()
        if tokens:
            season = tokens[0].title()
            for token in tokens[1:]:
                token_clean = token.rstrip(",.").lower()
                if token_clean.startswith("w") and token_clean[1:].isdigit():
                    week = int(token_clean[1:])
                    break
                if token_clean.isdigit():
                    week = int(token_clean)
                    break

    return InGameTime(raw=raw, season=season, week=week)
