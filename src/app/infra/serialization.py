# app/infra/mongo/serialization.py
from __future__ import annotations

from dataclasses import is_dataclass, fields
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, get_origin, get_args, Union

# ---------- Encoding (Python -> BSON-friendly) ----------

def to_bson(x: Any) -> Any:
    # Enums -> their .value (str/int) so PyMongo can encode them
    if isinstance(x, Enum):
        return x.value

    # timedelta -> seconds (float)
    if isinstance(x, timedelta):
        return x.total_seconds()

    # datetime -> naive UTC (what PyMongo stores)
    if isinstance(x, datetime):
        if x.tzinfo is not None:
            x = x.astimezone(timezone.utc).replace(tzinfo=None)
        return x

    # dataclasses -> dict (recurse)
    if is_dataclass(x):
        return {f.name: to_bson(getattr(x, f.name)) for f in fields(x)}

    # dicts / sequences -> recurse
    if isinstance(x, dict):
        return {k: to_bson(v) for k, v in x.items()}

    if isinstance(x, (list, tuple, set)):
        return [to_bson(v) for v in x]

    # everything else: pass through (int, str, bool, None, etc.)
    return x


# ---------- Decoding (BSON -> Python/dataclasses) ----------

def from_bson(cls: type, doc: Any) -> Any:
    """
    Reconstruct a dataclass instance of type `cls` from a plain dict `doc`.
    Ignores extra fields like Mongo's internal `_id`.
    """
    if doc is None:
        return None

    if is_dataclass(cls):
        kwargs = {}
        for f in fields(cls):
            if f.name not in doc:
                continue
            kwargs[f.name] = _from_bson_value(f.type, doc[f.name])
        return cls(**kwargs)

    # Fallback: if a bare type was passed (not a dataclass), just coerce value
    return _from_bson_value(cls, doc)


def _from_bson_value(expected_type: Any, value: Any) -> Any:
    if value is None:
        return None

    # Handle typing.Optional[...] / Union[..., None]
    origin = get_origin(expected_type)
    args = get_args(expected_type)
    if origin is Union:
        # pick the first non-None type
        inner = next((a for a in args if a is not type(None)), Any)
        return _from_bson_value(inner, value)

    # Handle collections like List[T], Set[T], Tuple[T]
    if origin in (list, set, tuple):
        inner = args[0] if args else Any
        seq = [_from_bson_value(inner, v) for v in (value or [])]
        if origin is list:
            return list(seq)
        if origin is set:
            return set(seq)
        return tuple(seq)

    # Recurse into nested dataclasses
    if isinstance(expected_type, type) and is_dataclass(expected_type):
        return from_bson(expected_type, value)

    # Enums: reconstruct from their value
    if isinstance(expected_type, type) and issubclass_safe(expected_type, Enum):
        return expected_type(value)

    # Timedelta: we stored seconds
    if expected_type is timedelta:
        return timedelta(seconds=value)

    # Datetime: assume stored as naive UTC; return UTC-aware
    if expected_type is datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None \
                   else value.astimezone(timezone.utc)
        # If somehow stored as numeric (shouldn't be), try seconds since epoch:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)

    # Primitive or already-correct type
    return value


def issubclass_safe(t: Any, base: type) -> bool:
    try:
        return issubclass(t, base)
    except Exception:
        return False
