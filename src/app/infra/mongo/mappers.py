# app/infra/mongo/mappers.py
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from enum import Enum
from typing import Any, Dict, Tuple, Type, TypeVar, cast

from app.domain.models.EntityIDModel import EntityID


def id_to_str(v: EntityID | None) -> str | None:
    return str(v) if v is not None else None


def id_from_str(cls: Type[EntityID], raw: str | None) -> EntityID | None:
    return cls.parse(raw) if raw is not None else None


T = TypeVar("T")


def _transform(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        items: Iterable[Tuple[Any, Any]] = cast(
            Iterable[Tuple[Any, Any]], value.items()
        )
        return {str(k): _transform(v) for k, v in items}
    if isinstance(value, (list, tuple)):
        iterable = cast(Iterable[Any], value)
        return [_transform(v) for v in iterable]
    if isinstance(value, (set, frozenset)):
        iterable = cast(Iterable[Any], value)
        return [_transform(v) for v in iterable]
    return value


def dataclass_to_mongo(model: Any) -> Dict[str, Any]:
    # naive: uses asdict; customize if you want compact storage
    raw = asdict(model)
    return _transform(raw)


def mongo_to_dataclass(cls: Type[T], data: Dict[str, Any]) -> T:
    # naive: pass-through; your models validate themselves
    return cls(**data)
