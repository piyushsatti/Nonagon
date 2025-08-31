# app/infra/mongo/mappers.py
from dataclasses import asdict
from typing import Any, Dict, Type, TypeVar
from app.domain.models.EntityIDModel import EntityID

def id_to_str(v: EntityID | None) -> str | None:
    return str(v) if v is not None else None

def id_from_str(cls: Type[EntityID], raw: str | None) -> EntityID | None:
    return cls.parse(raw) if raw is not None else None

T = TypeVar("T")

def dataclass_to_mongo(model: Any) -> Dict[str, Any]:
    # naive: uses asdict; customize if you want compact storage
    return asdict(model)

def mongo_to_dataclass(cls: Type[T], data: Dict[str, Any]) -> T:
    # naive: pass-through; your models validate themselves
    return cls(**data)