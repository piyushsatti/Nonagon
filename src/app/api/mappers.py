from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from app.api.schemas import (
    Character as APIChar,
)
from app.api.schemas import (
    CharacterStatus as APICharacterStatus,
)
from app.api.schemas import (
    InteractionMetrics,
    PlayerProfile,
    RefereeProfile,
    SummaryKind,
    UserRole,
)
from app.api.schemas import (
    Quest as APIQuest,
)
from app.api.schemas import (
    QuestSignup as APIQuestSignup,
)
from app.api.schemas import (
    QuestStatus as APIQuestStatus,
)
from app.api.schemas import (
    Summary as APISummary,
)
from app.api.schemas import (
    User as APIUser,
)
from app.domain.models.character.CharacterModel import Character as DCharacter
from app.domain.models.character.CharacterModel import CharacterRole
from app.domain.models.quest.QuestModel import PlayerSignUp, PlayerStatus
from app.domain.models.quest.QuestModel import Quest as DQuest
from app.domain.models.quest.QuestModel import QuestStatus as DQuestStatus
from app.domain.models.summary.SummaryModel import QuestSummary as DSumm
from app.domain.models.user.UserModel import InteractionStats
from app.domain.models.user.UserModel import Player as DPlayer
from app.domain.models.user.UserModel import Referee as DReferee
from app.domain.models.user.UserModel import User as DUser

# ---------- helpers ----------


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return a timezone-aware UTC datetime or None."""
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _list(xs: Optional[list[Any]]) -> list[Any]:
    """Normalize None → [] for list fields."""
    return list(xs) if xs else []


# ---------- users ----------


def _stats_map_to_api(
    data: Dict[Any, InteractionStats],
) -> Dict[str, InteractionMetrics]:
    return {
        str(key): InteractionMetrics(
            occurrences=stats.occurrences,
            total_seconds=stats.total_seconds,
            total_hours=stats.total_hours,
        )
        for key, stats in data.items()
    }


def _player_to_api(player: DPlayer | None) -> Optional[PlayerProfile]:
    if player is None:
        return None

    payload = PlayerProfile(
        characters=[str(char_id) for char_id in player.characters],
        quests_applied=[str(qid) for qid in player.quests_applied],
        quests_played=[str(qid) for qid in player.quests_played],
        summaries_written=[str(sid) for sid in player.summaries_written],
        joined_on=_utc(player.joined_on),
        created_first_character_on=_utc(player.created_first_character_on),
        last_played_on=_utc(player.last_played_on),
    )

    if player.played_with_character:
        payload.played_with_character = _stats_map_to_api(player.played_with_character)

    return payload


def _referee_to_api(referee: DReferee | None) -> Optional[RefereeProfile]:
    if referee is None:
        return None

    payload = RefereeProfile(
        quests_hosted=[str(qid) for qid in referee.quests_hosted],
        summaries_written=[str(sid) for sid in referee.summaries_written],
        first_dmed_on=_utc(referee.first_dmed_on),
        last_dmed_on=_utc(referee.last_dmed_on),
    )

    if referee.collabed_with:
        payload.collabed_with = _stats_map_to_api(referee.collabed_with)

    if referee.hosted_for:
        payload.hosted_for = {
            str(user_id): count for user_id, count in referee.hosted_for.items()
        }

    return payload


def user_to_api(u: DUser) -> APIUser:
    roles = [UserRole(role.value) for role in u.roles] if u.roles else []
    return APIUser(
        user_id=str(u.user_id),
        discord_id=u.discord_id,
        dm_channel_id=u.dm_channel_id,
        roles=roles,
        joined_at=_utc(u.joined_at),
        last_active_at=_utc(u.last_active_at),
        is_member=u.is_member,
        is_player=u.is_player,
        is_referee=u.is_referee,
        messages_count_total=u.messages_count_total,
        reactions_given=u.reactions_given,
        reactions_received=u.reactions_received,
        voice_total_hours=u.voice_total_hours,
        player=_player_to_api(u.player),
        referee=_referee_to_api(u.referee),
    )


# ---------- characters ----------


def char_to_api(c: DCharacter) -> APIChar:
    raw_status = getattr(c, "status", CharacterRole.ACTIVE)
    if isinstance(raw_status, CharacterRole):
        status = APICharacterStatus(raw_status.value)
    else:
        status = APICharacterStatus(str(raw_status))
    created_at_utc = _utc(c.created_at)
    if created_at_utc is None:  # pragma: no cover - defensive guard
        raise ValueError("Character missing creation timestamp")

    return APIChar(
        character_id=str(c.character_id),
        owner_id=str(c.owner_id),
        name=c.name,
        ddb_link=c.ddb_link,
        character_thread_link=c.character_thread_link,
        token_link=c.token_link,
        art_link=c.art_link,
        description=c.description,
        notes=c.notes,
        tags=list(getattr(c, "tags", []) or []),
        status=status,
        created_at=created_at_utc,
        last_played_at=_utc(getattr(c, "last_played_at", None)),
        quests_played=int(getattr(c, "quests_played", 0) or 0),
        summaries_written=int(getattr(c, "summaries_written", 0) or 0),
        played_with=[str(x) for x in _list(getattr(c, "played_with", None))],
        played_in=[str(x) for x in _list(getattr(c, "played_in", None))],
        mentioned_in=[str(x) for x in _list(getattr(c, "mentioned_in", None))],
    )


# ---------- quests ----------


def _signup_to_api(s: PlayerSignUp) -> APIQuestSignup:
    return APIQuestSignup(
        user_id=str(s.user_id),
        character_id=str(s.character_id),
        selected=s.status == PlayerStatus.SELECTED,
    )


def _duration_hours_from_timedelta(td: Optional[timedelta]) -> Optional[int]:
    if not td:
        return None
    return int(td.total_seconds() // 3600)


def quest_to_api(q: DQuest) -> APIQuest:
    # API uses boolean signups_open instead of a “SIGNUP_CLOSED” status
    signups_open = getattr(q, "status", None) == DQuestStatus.ANNOUNCED
    status_raw = getattr(q, "status", None)
    if isinstance(status_raw, DQuestStatus):
        status_value: APIQuestStatus = cast(APIQuestStatus, status_raw.value)
    elif isinstance(status_raw, str) and status_raw:
        status_value = cast(APIQuestStatus, status_raw)
    else:
        status_value = cast(APIQuestStatus, "ANNOUNCED")
    return APIQuest(
        quest_id=str(q.quest_id),
        referee_id=str(q.referee_id),
        raw=q.raw,
        title=q.title or "",
        description=q.description,
        starting_at=_utc(getattr(q, "starting_at", None)),
        duration_hours=_duration_hours_from_timedelta(getattr(q, "duration", None)),
        image_url=q.image_url,
        linked_quests=[str(x) for x in _list(getattr(q, "linked_quests", None))],
        linked_summaries=[str(x) for x in _list(getattr(q, "linked_summaries", None))],
        # Fields present only on the full API Quest
        channel_id=str(q.channel_id),
        message_id=str(q.message_id),
        status=status_value,
        started_at=_utc(getattr(q, "started_at", None)),
        ended_at=_utc(getattr(q, "ended_at", None)),
        signups_open=bool(signups_open),
        signups=[_signup_to_api(s) for s in _list(getattr(q, "signups", None))],
    )


# ---------- summaries ----------


def summary_to_api(s: DSumm) -> APISummary:
    kind = getattr(s, "kind", None)
    if kind is None:
        raise ValueError("Summary missing kind")
    created_on = _utc(getattr(s, "created_on", None))
    if created_on is None:
        raise ValueError("Summary missing created_on timestamp")
    return APISummary(
        summary_id=str(s.summary_id),
        kind=SummaryKind(kind.value),
        author_id=str(s.author_id),
        character_id=str(s.character_id),
        quest_id=str(s.quest_id),
        title=s.title,
        description=getattr(s, "description", ""),
        raw=s.raw,
        created_on=created_on,
        last_edited_at=_utc(getattr(s, "last_edited_at", None)),
        players=[str(x) for x in _list(getattr(s, "players", None))],
        characters=[str(x) for x in _list(getattr(s, "characters", None))],
        linked_quests=[str(x) for x in _list(getattr(s, "linked_quests", None))],
        linked_summaries=[str(x) for x in _list(getattr(s, "linked_summaries", None))],
    )
