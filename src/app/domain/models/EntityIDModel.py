from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from app.domain.id_utils import generate_postal_id, validate_postal_id

POSTAL_BODY_PATTERN = re.compile(r"^[A-Z]\d[A-Z]\d[A-Z]\d$")
LEGACY_BODY_PATTERN = re.compile(r"^\d+$")


@dataclass(frozen=True, slots=True)
class EntityID:
	prefix: ClassVar[str] = "BASE"
	value: str | None = None

	def __post_init__(self) -> None:
		raw = self.value if self.value is not None else self._generate_default()
		normalized = self._normalize(raw)
		object.__setattr__(self, "value", normalized)

	@classmethod
	def _normalize(cls, raw: Any) -> str:
		if isinstance(raw, EntityID):
			raw = raw.value

		if raw is None:
			raise ValueError("ID value cannot be empty")

		raw_str = str(raw).strip()
		if not raw_str:
			raise ValueError("ID value cannot be empty")

		cleaned = raw_str.upper()
		if cleaned.startswith(cls.prefix):
			candidate = cleaned
			body = cleaned[len(cls.prefix) :]
		else:
			body = cleaned
			candidate = f"{cls.prefix}{cleaned}"

		if validate_postal_id(candidate, prefix=cls.prefix):
			return candidate

		if LEGACY_BODY_PATTERN.fullmatch(body):
			return candidate

		raise ValueError(
			"Invalid ID body. Expected postal pattern (e.g., H3X1T7) or a legacy numeric string."
		)

	@classmethod
	def _generate_default(cls) -> str:
		raise ValueError("Subclasses must supply a value or override _generate_default().")

	@property
	def body(self) -> str:
		return self.value[len(self.prefix) :]

	@property
	def number(self) -> int | None:
		body = self.body
		return int(body) if LEGACY_BODY_PATTERN.fullmatch(body) else None

	def __str__(self) -> str:
		return self.value

	@classmethod
	def parse(cls, raw: str) -> "EntityID":
		return cls(raw)

	@classmethod
	def from_body(cls, body: str) -> "EntityID":
		return cls(body)

	@classmethod
	def generate(cls) -> "EntityID":
		return cls()


@dataclass(frozen=True, slots=True)
class UserID(EntityID):
	prefix: ClassVar[str] = "USER"

	@classmethod
	def _generate_default(cls) -> str:
		return generate_postal_id(cls.prefix)


@dataclass(frozen=True, slots=True)
class QuestID(EntityID):
	prefix: ClassVar[str] = "QUES"

	@classmethod
	def _generate_default(cls) -> str:
		return generate_postal_id(cls.prefix)


@dataclass(frozen=True, slots=True)
class CharacterID(EntityID):
	prefix: ClassVar[str] = "CHAR"

	@classmethod
	def _generate_default(cls) -> str:
		return generate_postal_id(cls.prefix)


@dataclass(frozen=True, slots=True)
class SummaryID(EntityID):
	prefix: ClassVar[str] = "SUMM"

	@classmethod
	def _generate_default(cls) -> str:
		return generate_postal_id(cls.prefix)
