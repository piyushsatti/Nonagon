import re
from dataclasses import dataclass
from typing import ClassVar

DRAFT_PREFIX = "DRAFT"


@dataclass(frozen=True, slots=True)
class EntityID:
    prefix: ClassVar[str] = "BASE"
    number: int

    def __post_init__(self):

        if self.number < 1:
            raise ValueError("ID number must be >= 1")

    def __str__(self) -> str:
        return f"{self.prefix}{self.number:04d}"

    @classmethod
    def parse(cls, raw: str):
        m = re.match(r"^([A-Z]{4,})(\d{4,})$", raw)

        if not m:
            raise ValueError(f"Invalid ID: {raw}")
        pref, num = m.groups()

        if pref != cls.prefix:
            raise ValueError(f"Expected {cls.prefix}, got {pref}")

        return cls(number=int(num))


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


@dataclass(frozen=True, slots=True)
class DraftID(EntityID):
    prefix: ClassVar[str] = DRAFT_PREFIX


def is_valid_id(value: str, prefix: str) -> bool:
    return bool(re.match(rf"^{prefix}[0-9]{{4,}}$", value))


def ensure_prefix(value: str, prefix: str) -> str:
    if value.startswith(prefix):
        return value
    match = re.search(r"(\d{4,})$", value)
    if not match:
        raise ValueError(f"Value {value} does not contain a numeric suffix")
    return f"{prefix}{match.group(1)}"
