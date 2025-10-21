from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass
from typing import ClassVar


POSTAL_BODY_PATTERN = re.compile(r"^[A-Z]\d[A-Z]\d[A-Z]\d$")
LEGACY_BODY_PATTERN = re.compile(r"^\d+$")


@dataclass(frozen=True, slots=True)
class EntityID:
    prefix: ClassVar[str] = "BASE"
    value: str

    def __post_init__(self) -> None:
        normalized = self._normalize(self.value)
        object.__setattr__(self, "value", normalized)

    @classmethod
    def _normalize(cls, raw: str) -> str:
        if raw is None:
            raise ValueError("ID value is required")

        cleaned = raw.strip().upper()
        if not cleaned:
            raise ValueError("ID value cannot be empty")

        if not cleaned.startswith(cls.prefix):
            raise ValueError(
                f"Expected prefix {cls.prefix}, received {cleaned[: len(cls.prefix)]}"
            )

        body = cleaned[len(cls.prefix) :]
        cls._validate_body(body)
        return f"{cls.prefix}{body}"

    @classmethod
    def _validate_body(cls, body: str) -> None:
        if POSTAL_BODY_PATTERN.fullmatch(body):
            return
        if LEGACY_BODY_PATTERN.fullmatch(body):
            return
            raise ValueError(
                "Invalid ID body. Expected pattern letter-digit repeated three times "
                "(e.g., H3X1T7)."
            )

    @property
    def body(self) -> str:
        return self.value[len(self.prefix) :]

    @property
    def number(self) -> str:
        return self.body

    def __str__(self) -> str:
        return self.value

    @classmethod
    def parse(cls, raw: str) -> "EntityID":
        return cls(raw)

    @classmethod
    def from_body(cls, body: str) -> "EntityID":
        cleaned = body.strip().upper()
        cls._validate_body(cleaned)
        return cls(f"{cls.prefix}{cleaned}")

    @classmethod
    def generate(cls) -> "EntityID":
        return cls(f"{cls.prefix}{cls._random_body()}")

    @classmethod
    def _random_body(cls) -> str:
        letters = string.ascii_uppercase
        digits = string.digits
        rng = random.SystemRandom()
        parts = [
            rng.choice(letters) if index % 2 == 0 else rng.choice(digits)
            for index in range(6)
        ]
        return "".join(parts)


@dataclass(frozen=True, slots=True)
class UserID(EntityID):
    prefix: ClassVar[str] = "USER"


@dataclass(frozen=True, slots=True)
class QuestID(EntityID):
    prefix: ClassVar[str] = "QUES"


@dataclass(frozen=True, slots=True)
class CharacterID(EntityID):
    prefix: ClassVar[str] = "CHAR"


@dataclass(frozen=True, slots=True)
class SummaryID(EntityID):
    prefix: ClassVar[str] = "SUMM"
