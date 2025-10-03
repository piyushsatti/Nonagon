from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple, cast

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID

__all__ = ["Role", "InteractionStats", "User", "Player", "Referee"]


class Role(str, Enum):
    MEMBER = "MEMBER"
    PLAYER = "PLAYER"
    REFEREE = "REFEREE"


UTC = timezone.utc


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _coerce_utc(dt: datetime) -> datetime:
    converted = _ensure_utc(dt)
    assert converted is not None
    return converted


def _default_roles() -> list[Role]:
    return [Role.MEMBER]


def _new_character_list() -> list[CharacterID]:
    return []


def _new_quest_list() -> list[QuestID]:
    return []


def _new_summary_list() -> list[SummaryID]:
    return []


def _new_character_map() -> dict[CharacterID, "InteractionStats"]:
    return {}


def _new_user_map() -> dict[UserID, "InteractionStats"]:
    return {}


def _new_hosted_for_map() -> dict[UserID, int]:
    return {}


@dataclass(slots=True)
class InteractionStats:
    """Tracks frequency and total duration in seconds for a given relationship."""

    occurrences: int = 0
    total_seconds: int = 0

    def add(self, seconds: int = 0) -> None:
        if seconds < 0:
            raise ValueError("Duration seconds must be non-negative")
        self.occurrences += 1
        self.total_seconds += seconds

    def merge_legacy(self, legacy: Tuple[int, float]) -> None:
        frequency, hours = legacy
        if frequency < 0 or hours < 0:
            raise ValueError("Legacy interaction metrics must be non-negative")
        self.occurrences = int(frequency)
        if isinstance(hours, float):
            self.total_seconds = int(hours * 3600)
        else:
            self.total_seconds = int(hours)

    @property
    def total_hours(self) -> float:
        return self.total_seconds / 3600 if self.total_seconds else 0.0


@dataclass(slots=True)
class User:
    """Guild user enriched with activity and role telemetry."""

    user_id: UserID
    discord_id: Optional[str] = None
    dm_channel_id: Optional[str] = None
    roles: list[Role] = field(default_factory=_default_roles)

    joined_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None

    messages_count_total: int = 0
    reactions_given: int = 0
    reactions_received: int = 0
    voice_total_time_spent: float = 0.0  # hours

    player: Optional["Player"] = None
    referee: Optional["Referee"] = None

    def __post_init__(self) -> None:
        normalised_roles = [Role(role) for role in self.roles]
        self.roles = list(dict.fromkeys(normalised_roles)) or _default_roles()

        self.joined_at = _ensure_utc(self.joined_at)
        self.last_active_at = _ensure_utc(self.last_active_at)

        self._normalise_telemetry()

        if self.player is not None:
            self.player.ensure_sanity()

        if self.referee is not None:
            self.referee.ensure_sanity()

    # ---------- Role helpers ----------

    def add_role(self, role: Role) -> None:
        if role not in self.roles:
            self.roles.append(role)

    def enable_player(self) -> None:
        self.add_role(Role.PLAYER)
        if self.player is None:
            self.player = Player()

    def disable_player(self) -> None:
        if Role.REFEREE in self.roles:
            raise ValueError(
                "Cannot disable PLAYER role while REFEREE role is active. Disable REFEREE first."
            )
        if Role.PLAYER in self.roles:
            self.roles.remove(Role.PLAYER)
        self.player = None

    def enable_referee(self) -> None:
        if Role.PLAYER not in self.roles:
            self.enable_player()
        self.add_role(Role.REFEREE)
        if self.referee is None:
            self.referee = Referee()

    def disable_referee(self) -> None:
        if Role.REFEREE in self.roles:
            self.roles.remove(Role.REFEREE)
        self.referee = None

    def is_character_owner(self, char_id: CharacterID) -> bool:
        return bool(self.player and char_id in self.player.characters)

    # ---------- Properties ----------

    @property
    def is_player(self) -> bool:
        return Role.PLAYER in self.roles

    @property
    def is_referee(self) -> bool:
        return Role.REFEREE in self.roles

    @property
    def is_member(self) -> bool:
        return Role.MEMBER in self.roles

    @property
    def voice_total_hours(self) -> float:
        return self.voice_total_time_spent if self.voice_total_time_spent else 0.0

    # ---------- Getters ----------

    def get_player(self) -> "Player":
        if not self.is_player or self.player is None:
            raise ValueError("User is not a player")
        return self.player

    def get_characters(self) -> list[CharacterID]:
        return self.get_player().characters

    def get_referee(self) -> "Referee":
        if not self.is_referee or self.referee is None:
            raise ValueError("User is not a referee")
        return self.referee

    # ---------- Activity updaters ----------

    def update_dm_channel(self, dm_channel_id: str) -> None:
        self.dm_channel_id = dm_channel_id

    def update_joined_at(self, joined_at: datetime, override: bool = False) -> None:
        joined_at = _coerce_utc(joined_at)
        if self.joined_at is not None and not override:
            raise ValueError(
                "joined_at is already set. Use override=True to force change."
            )
        self.joined_at = joined_at

    def update_last_active(self, active_at: Optional[datetime] = None) -> None:
        active_time = active_at or datetime.now(tz=UTC)
        self.last_active_at = _coerce_utc(active_time)

    def increment_messages_count(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("Count must be non-negative")
        self.messages_count_total += count
        self.update_last_active()

    def increment_reactions_given(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("Count must be non-negative")
        self.reactions_given += count
        self.update_last_active()

    def increment_reactions_received(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("Count must be non-negative")
        self.reactions_received += count

    def add_voice_time_spent(self, seconds: int) -> None:
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")
        self.voice_total_time_spent += seconds / 3600

    def record_interaction(
        self,
        *,
        messages: int = 0,
        reactions_given: int = 0,
        reactions_received: int = 0,
        voice_seconds: int = 0,
        at: Optional[datetime] = None,
    ) -> None:
        if messages:
            self.increment_messages_count(messages)
        if reactions_given:
            self.increment_reactions_given(reactions_given)
        if reactions_received:
            self.increment_reactions_received(reactions_received)
        if voice_seconds:
            self.add_voice_time_spent(voice_seconds)
        if at is not None:
            self.update_last_active(at)

    # ---------- Validation ----------

    def validate_user(self) -> None:
        if self.messages_count_total < 0:
            raise ValueError("messages_count_total must be non-negative")
        if self.reactions_given < 0:
            raise ValueError("reactions_given must be non-negative")
        if self.reactions_received < 0:
            raise ValueError("reactions_received must be non-negative")
        if self.voice_total_time_spent < 0:
            raise ValueError("voice_total_time_spent must be non-negative")

        if (
            self.joined_at
            and self.last_active_at
            and self.last_active_at < self.joined_at
        ):
            raise ValueError("last_active_at cannot be before joined_at")

        if self.is_player and self.player is None:
            raise ValueError("Player profile must be set if user has PLAYER role")
        if self.is_referee and self.referee is None:
            raise ValueError("Referee profile must be set if user has REFEREE role")

        if self.player is not None:
            self.player.ensure_sanity()
        if self.referee is not None:
            self.referee.ensure_sanity()

    # ---------- Serialization ----------

    def from_dict(self, data: Dict[str, Any]) -> "User":
        valid = {f.name for f in fields(self)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def _normalise_telemetry(self) -> None:
        self.messages_count_total = int(self.messages_count_total)
        self.reactions_given = int(self.reactions_given)
        self.reactions_received = int(self.reactions_received)

        voice_raw = cast(Any, self.voice_total_time_spent)
        if isinstance(voice_raw, str):
            try:
                voice_value = float(voice_raw)
            except ValueError as exc:  # pragma: no cover - defensive guard
                raise ValueError("voice_total_time_spent must be numeric") from exc
        elif isinstance(voice_raw, (int, float)):
            voice_value = float(voice_raw)
            if isinstance(voice_raw, int) and voice_raw >= 3600:
                voice_value = voice_raw / 3600
        else:
            raise ValueError("voice_total_time_spent must be numeric")

        if voice_value < 0:
            raise ValueError("voice_total_time_spent must be non-negative")
        self.voice_total_time_spent = voice_value


@dataclass(slots=True)
class Player:
    characters: list[CharacterID] = field(default_factory=_new_character_list)

    joined_on: Optional[datetime] = None
    created_first_character_on: Optional[datetime] = None
    last_played_on: Optional[datetime] = None

    quests_applied: list[QuestID] = field(default_factory=_new_quest_list)
    quests_played: list[QuestID] = field(default_factory=_new_quest_list)
    summaries_written: list[SummaryID] = field(default_factory=_new_summary_list)
    played_with_character: dict[CharacterID, InteractionStats] = field(
        default_factory=_new_character_map
    )

    def __post_init__(self) -> None:
        self.ensure_sanity()

    # ---------- Updaters ----------

    def add_character(self, char_id: CharacterID) -> None:
        if char_id not in self.characters:
            self.characters.append(char_id)

    def remove_character(self, char_id: CharacterID) -> None:
        if char_id in self.characters:
            self.characters.remove(char_id)

    def update_joined_on(self, joined_on: datetime, override: bool = False) -> None:
        joined_on = _coerce_utc(joined_on)
        if self.joined_on is not None and not override:
            raise ValueError(
                "joined_on is already set. Use override=True to force change."
            )
        self.joined_on = joined_on

    def update_created_first_character_on(
        self, created_on: datetime, override: bool = False
    ) -> None:
        created_on = _coerce_utc(created_on)
        if self.created_first_character_on is not None and not override:
            raise ValueError(
                "created_first_character_on is already set. Use override=True to force change."
            )
        self.created_first_character_on = created_on

    def update_last_played_on(self, played_on: datetime) -> None:
        self.last_played_on = _coerce_utc(played_on)

    def add_quest_applied(self, quest_id: QuestID) -> None:
        if quest_id not in self.quests_applied:
            self.quests_applied.append(quest_id)

    def add_quest_played(self, quest_id: QuestID) -> None:
        if quest_id not in self.quests_played:
            self.quests_played.append(quest_id)

    def increment_summaries_written(self, summary_id: SummaryID) -> None:
        if summary_id not in self.summaries_written:
            self.summaries_written.append(summary_id)

    def add_played_with_character(self, char_id: CharacterID, seconds: int = 0) -> None:
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")
        stats = self.played_with_character.setdefault(char_id, InteractionStats())
        stats.add(seconds)

    def remove_played_with_character(self, char_id: CharacterID) -> None:
        self.played_with_character.pop(char_id, None)

    # ---------- Validation & serialization ----------

    def ensure_sanity(self) -> None:
        self.joined_on = _ensure_utc(self.joined_on)
        self.created_first_character_on = _ensure_utc(self.created_first_character_on)
        self.last_played_on = _ensure_utc(self.last_played_on)

        self.characters = list(dict.fromkeys(self.characters))
        self.quests_applied = list(dict.fromkeys(self.quests_applied))
        self.quests_played = list(dict.fromkeys(self.quests_played))
        self.summaries_written = list(dict.fromkeys(self.summaries_written))

        raw_map: Dict[CharacterID, Any] = dict(self.played_with_character)
        sanitized: dict[CharacterID, InteractionStats] = {}
        for key, value in raw_map.items():
            if isinstance(value, InteractionStats):
                sanitized[key] = value
            else:
                try:
                    freq, hours = value  # type: ignore[misc]
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "played_with_character must map to InteractionStats or (int, float) tuples"
                    ) from exc
                if not isinstance(freq, (int, float)) or not isinstance(
                    hours, (int, float)
                ):
                    raise ValueError(
                        "played_with_character must map to InteractionStats or (int, float) tuples"
                    )
                stats = InteractionStats()
                stats.merge_legacy((int(freq), float(hours)))
                sanitized[key] = stats
        self.played_with_character = sanitized

    def validate_player(self) -> None:
        self.ensure_sanity()

    def from_dict(self, data: Dict[str, Any]) -> "Player":
        valid = {f.name for f in fields(self)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Referee:
    quests_hosted: list[QuestID] = field(default_factory=_new_quest_list)
    summaries_written: list[SummaryID] = field(default_factory=_new_summary_list)

    first_dmed_on: Optional[datetime] = None
    last_dmed_on: Optional[datetime] = None
    collabed_with: dict[UserID, InteractionStats] = field(default_factory=_new_user_map)
    hosted_for: dict[UserID, int] = field(default_factory=_new_hosted_for_map)

    def __post_init__(self) -> None:
        self.ensure_sanity()

    # ---------- Updaters ----------

    def add_quest_hosted(self, quest_id: QuestID) -> None:
        if quest_id not in self.quests_hosted:
            self.quests_hosted.append(quest_id)

    def increment_summaries_written(self, summary_id: SummaryID) -> None:
        if summary_id not in self.summaries_written:
            self.summaries_written.append(summary_id)

    def update_first_dmed_on(self, dmed_on: datetime, override: bool = False) -> None:
        dmed_on = _coerce_utc(dmed_on)
        if self.first_dmed_on is not None and not override:
            raise ValueError(
                "first_dmed_on is already set. Use override=True to force change."
            )
        self.first_dmed_on = dmed_on

    def update_last_dmed_on(self, dmed_on: datetime) -> None:
        self.last_dmed_on = _coerce_utc(dmed_on)

    def add_collabed_with(self, user_id: UserID, seconds: int = 0) -> None:
        if seconds < 0:
            raise ValueError("Seconds must be non-negative")
        stats = self.collabed_with.setdefault(user_id, InteractionStats())
        stats.add(seconds)

    def remove_collabed_with(self, user_id: UserID) -> None:
        self.collabed_with.pop(user_id, None)

    def add_hosted_for(self, user_id: UserID) -> None:
        self.hosted_for[user_id] = self.hosted_for.get(user_id, 0) + 1

    def remove_hosted_for(self, user_id: UserID) -> None:
        self.hosted_for.pop(user_id, None)

    # ---------- Validation & serialization ----------

    def ensure_sanity(self) -> None:
        self.first_dmed_on = _ensure_utc(self.first_dmed_on)
        self.last_dmed_on = _ensure_utc(self.last_dmed_on)

        self.quests_hosted = list(dict.fromkeys(self.quests_hosted))
        self.summaries_written = list(dict.fromkeys(self.summaries_written))

        raw_map: Dict[UserID, Any] = dict(self.collabed_with)
        sanitized: dict[UserID, InteractionStats] = {}
        for key, value in raw_map.items():
            if isinstance(value, InteractionStats):
                sanitized[key] = value
            else:
                try:
                    freq, hours = value  # type: ignore[misc]
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "collabed_with must map to InteractionStats or (int, float) tuples"
                    ) from exc
                if not isinstance(freq, (int, float)) or not isinstance(
                    hours, (int, float)
                ):
                    raise ValueError(
                        "collabed_with must map to InteractionStats or (int, float) tuples"
                    )
                stats = InteractionStats()
                stats.merge_legacy((int(freq), float(hours)))
                sanitized[key] = stats
        self.collabed_with = sanitized

        for key, count in list(self.hosted_for.items()):
            if count < 0:
                raise ValueError("hosted_for counts must be non-negative")
            self.hosted_for[key] = int(count)

    def validate_referee(self) -> None:
        self.ensure_sanity()

    def from_dict(self, data: Dict[str, Any]) -> "Referee":
        valid = {f.name for f in fields(self)}
        filtered = {k: v for k, v in data.items() if k in valid}
        return replace(self, **filtered)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
