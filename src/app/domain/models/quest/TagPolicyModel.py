from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

__all__ = ["TagPolicy"]


@dataclass
class TagPolicy:
    max_tags: int = 12
    normalization: str = "lower_raw"  # "lower_raw" | "kebab" | "keep_raw"
    allow_new: bool = True
    aliases: Dict[str, str] = field(default_factory=lambda: {})

    def normalize(self, tags: List[str]) -> List[str]:
        normalized: List[str] = []
        seen: set[str] = set()

        for raw in tags:
            tag = (raw or "").strip()
            if not tag:
                continue

            key = tag.lower()
            if self.normalization == "lower_raw":
                candidate = key
            elif self.normalization == "kebab":
                candidate = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
            else:
                candidate = tag

            candidate = self.aliases.get(candidate, candidate)

            if not candidate:
                continue

            if not self.allow_new and candidate not in self.aliases.values():
                continue

            if candidate in seen:
                continue

            seen.add(candidate)
            normalized.append(candidate)

            if len(normalized) >= self.max_tags:
                break

        return normalized
