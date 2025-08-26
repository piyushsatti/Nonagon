from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from app.domain.usecases.ports import ForbiddenError
from app.domain.models.UserModel import Role, UserId
from app.domain.models.quest.SummaryModel import QuestSummary, SummaryKind

@dataclass
class SubmitSummaryInput:
    quest_id: str
    author_user_id: UserId
    text: str
    kind: SummaryKind
    is_private: Optional[bool] = None

async def submit_summary(
    users_repo,
    quests_repo,
    summaries_repo,
    data: SubmitSummaryInput,
) -> QuestSummary:
    # Load author and quest
    user = await users_repo.get(data.author_user_id)
    quest = await quests_repo.get(data.quest_id)

    # Role checks
    if data.kind == SummaryKind.DM and Role.REFEREE not in user.roles:
        raise ForbiddenError("Only referees can submit DM summaries.")
    if data.kind == SummaryKind.PLAYER and Role.PLAYER not in user.roles:
        raise ForbiddenError("Only players can submit player summaries.")

    # Create and persist summary
    sid = await summaries_repo.next_id()
    summary = QuestSummary(
        summary_id=sid,
        quest_id=data.quest_id,
        author_user_id=data.author_user_id,
        kind=data.kind,
        summary_text=data.text,
        posted_at=datetime.utcnow(),
        is_private=(True if data.kind == SummaryKind.DM else False)
        if data.is_private is None else data.is_private,
        audience_roles=(["admin", "referee"] if data.kind == SummaryKind.DM else []),
    )

    # Link to quest and update author stats
    quest.summary_ids.append(sid)
    if data.kind == SummaryKind.DM and user.referee:
        user.referee.dm_summaries_written.append(sid)
        user.referee.last_dmed_at = datetime.utcnow()
    if data.kind == SummaryKind.PLAYER and user.player:
        user.player.quest_summaries_written.append(sid)
        user.player.last_played_at = datetime.utcnow()

    # Save changes
    await summaries_repo.upsert(summary)
    await quests_repo.upsert(quest)
    await users_repo.upsert(user)
    return summary
