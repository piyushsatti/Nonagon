from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.api.schemas import (
    Character as APIChar,
)
from app.api.schemas import (
    Quest as APIQuest,
)
from app.api.schemas import (
    Summary as APISummary,
)

# ---- API schemas (your new ones) ----
from app.api.schemas import (
    User as APIUser,
)
from app.domain.models.CharacterModel import Character as DCharacter
from app.domain.models.CharacterModel import CharacterRole
from app.domain.models.QuestModel import (
    PlayerSignUp,
    PlayerStatus,
)
from app.domain.models.QuestModel import (
    Quest as DQuest,
)
from app.domain.models.QuestModel import (
    QuestStatus as DQuestStatus,
)
from app.domain.models.SummaryModel import QuestSummary as DSumm

# ---- Domain models ----
from app.domain.models.UserModel import User as DUser

# ---------- helpers ----------


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Return a timezone-aware UTC datetime or None."""
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _list(xs: Optional[List[Any]]) -> List[Any]:
    """Normalize None → [] for list fields."""
    return xs or []


# ---------- users ----------


def user_to_api(u: DUser) -> APIUser:
    return APIUser(
        user_id=u.user_id,
        roles=[r.value for r in u.roles],
        joined_at=u.joined_at,
        last_active_at=u.last_active_at,
        message_count_total=u.messages_count_total,
        reactions_given=u.reactions_given,
        reactions_received=u.reactions_received,
        voice_time_total_spent=u.voice_total_time_spent,
    )


# ---------- characters ----------


def char_to_api(c: DCharacter) -> APIChar:
    status = (
        "ACTIVE" if getattr(c, "status", None) == CharacterRole.ACTIVE else "RETIRED"
    )
    return APIChar(
        character_id=str(c.character_id),
        owner_id=str(c.owner_id) if getattr(c, "owner_id", None) else None,
        name=c.name,
        ddb_link=c.ddb_link,
        character_thread_link=c.character_thread_link,
        token_link=c.token_link,
        art_link=c.art_link,
        description=c.description,
        notes=c.notes,
        tags=list(getattr(c, "tags", []) or []),
        status=status,
        created_at=_utc(c.created_at),
        last_played_at=_utc(getattr(c, "last_played_at", None)),
        quests_played=int(getattr(c, "quests_played", 0) or 0),
        summaries_written=int(getattr(c, "summaries_written", 0) or 0),
        played_with=[str(x) for x in _list(getattr(c, "played_with", None))],
        played_in=[str(x) for x in _list(getattr(c, "played_in", None))],
        mentioned_in=[str(x) for x in _list(getattr(c, "mentioned_in", None))],
    )


# ---------- quests ----------


def _signup_to_api(s: PlayerSignUp) -> Dict[str, Any]:
    return {
        "user_id": str(s.user_id),
        "character_id": str(s.character_id),
        "selected": (s.status == PlayerStatus.SELECTED),
    }


def _duration_hours_from_timedelta(td: Optional[timedelta]) -> Optional[int]:
    if not td:
        return None
    return int(td.total_seconds() // 3600)


def quest_to_api(q: DQuest) -> APIQuest:
    # API uses boolean signups_open instead of a “SIGNUP_CLOSED” status
    signups_open = getattr(q, "status", None) == DQuestStatus.ANNOUNCED
    return APIQuest(
        quest_id=str(q.quest_id) if getattr(q, "quest_id", None) else None,
        referee_id=str(q.referee_id) if getattr(q, "referee_id", None) else None,
        raw=q.raw,
        title=q.title,
        description=q.description,
        starting_at=_utc(getattr(q, "starting_at", None)),
        duration_hours=_duration_hours_from_timedelta(getattr(q, "duration", None)),
        image_url=q.image_url,
        linked_quests=[str(x) for x in _list(getattr(q, "linked_quests", None))],
        linked_summaries=[str(x) for x in _list(getattr(q, "linked_summaries", None))],
        # Fields present only on the full API Quest
        channel_id=getattr(q, "channel_id", None),
        message_id=getattr(q, "message_id", None),
        status=(
            q.status.value
            if isinstance(getattr(q, "status", None), DQuestStatus)
            else str(getattr(q, "status", "")) or "ANNOUNCED"
        ),
        started_at=_utc(getattr(q, "started_at", None)),
        ended_at=_utc(getattr(q, "ended_at", None)),
        signups_open=bool(signups_open),
        signups=[_signup_to_api(s) for s in _list(getattr(q, "signups", None))],
    )


# ---------- summaries ----------


def summary_to_api(s: DSumm) -> APISummary:
    # NOTE: your schema field is spelled “descroption”; we map domain.description to that name.
    return APISummary(
        summary_id=str(s.summary_id),
        kind=getattr(s, "kind", None).value if getattr(s, "kind", None) else None,
        author_id=str(s.author_id) if getattr(s, "author_id", None) else None,
        character_id=str(s.character_id) if getattr(s, "character_id", None) else None,
        quest_id=str(s.quest_id) if getattr(s, "quest_id", None) else None,
        title=s.title,
        descroption=getattr(s, "description", None),  # <-- schema typo handled here
        raw=s.raw,
        created_on=_utc(getattr(s, "created_on", None)),
        last_edited_at=_utc(getattr(s, "last_edited_at", None)),
        players=[str(x) for x in _list(getattr(s, "players", None))],
        characters=[str(x) for x in _list(getattr(s, "characters", None))],
        linked_quests=[str(x) for x in _list(getattr(s, "linked_quests", None))],
        linked_summaries=[str(x) for x in _list(getattr(s, "linked_summaries", None))],
    )
