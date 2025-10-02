from datetime import datetime

from fastapi import APIRouter, HTTPException

import app.api.deps as deps
from app.api.mappers import summary_to_api
from app.api.schemas import Summary, SummaryCreate, SummaryUpdate
from app.domain.usecase import summaries as summary_usecases

router = APIRouter(prefix="/v1/summaries", tags=["Summaries"])

summaries_repo = deps.summaries_repo
users_repo = deps.user_repo
characters_repo = deps.chars_repo
quests_repo = deps.quests_repo


@router.post(
    "",
    response_model=Summary,
    status_code=201,
    response_model_exclude_none=True,
)
async def create_summary(body: SummaryCreate) -> Summary:
    try:
        usecase = summary_usecases.CreateSummary(
            summaries_repo=summaries_repo,
            users_repo=users_repo,
            characters_repo=characters_repo,
            quests_repo=quests_repo,
        )
        summary = await usecase.execute(
            kind=body.kind,
            author_id=body.author_id,
            character_id=body.character_id,
            quest_id=body.quest_id,
            raw=body.raw,
            title=body.title,
            description=body.description,
            created_on=body.created_on,
            players=body.players,
            characters=body.characters,
            linked_quests=body.linked_quests,
            linked_summaries=body.linked_summaries,
        )
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get(
    "/{summary_id}",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def get_summary(summary_id: str) -> Summary:
    try:
        usecase = summary_usecases.GetSummary(summaries_repo=summaries_repo)
        summary = await usecase.execute(summary_id)
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.patch(
    "/{summary_id}",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def patch_summary(summary_id: str, body: SummaryUpdate | None = None) -> Summary:
    payload = body.model_dump(exclude_unset=True) if body else {}

    try:
        usecase = summary_usecases.UpdateSummaryContent(
            summaries_repo=summaries_repo,
        )
        summary = await usecase.execute(
            summary_id,
            raw=payload.get("raw"),
            title=payload.get("title"),
            description=payload.get("description"),
            last_edited_at=payload.get("last_edited_at"),
            players=payload.get("players"),
            characters=payload.get("characters"),
            linked_quests=payload.get("linked_quests"),
            linked_summaries=payload.get("linked_summaries"),
        )
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete("/{summary_id}", status_code=204)
async def delete_summary(summary_id: str) -> None:
    try:
        usecase = summary_usecases.DeleteSummary(summaries_repo=summaries_repo)
        await usecase.execute(summary_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post(
    "/{summary_id}:updateLastEdited",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def update_last_edited(
    summary_id: str, edited_at: datetime | None = None
) -> Summary:
    try:
        usecase = summary_usecases.TouchSummary(summaries_repo=summaries_repo)
        summary = await usecase.execute(summary_id, edited_at=edited_at)
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{summary_id}/players/{user_id}",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def add_player(summary_id: str, user_id: str) -> Summary:
    try:
        usecase = summary_usecases.AddPlayerToSummary(
            summaries_repo=summaries_repo,
            users_repo=users_repo,
        )
        summary = await usecase.execute(summary_id, user_id)
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete(
    "/{summary_id}/players/{user_id}",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def remove_player(summary_id: str, user_id: str) -> Summary:
    try:
        usecase = summary_usecases.RemovePlayerFromSummary(
            summaries_repo=summaries_repo,
            users_repo=users_repo,
        )
        summary = await usecase.execute(summary_id, user_id)
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{summary_id}/characters/{character_id}",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def add_character(summary_id: str, character_id: str) -> Summary:
    try:
        usecase = summary_usecases.AddCharacterToSummary(
            summaries_repo=summaries_repo,
            characters_repo=characters_repo,
        )
        summary = await usecase.execute(summary_id, character_id)
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete(
    "/{summary_id}/characters/{character_id}",
    response_model=Summary,
    response_model_exclude_none=True,
)
async def remove_character(summary_id: str, character_id: str) -> Summary:
    try:
        usecase = summary_usecases.RemoveCharacterFromSummary(
            summaries_repo=summaries_repo,
            characters_repo=characters_repo,
        )
        summary = await usecase.execute(summary_id, character_id)
        return summary_to_api(summary)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get(
    "",
    response_model=list[Summary],
    response_model_exclude_none=True,
)
async def list_summaries(
    author_id: str | None = None,
    character_id: str | None = None,
    player_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Summary]:
    try:
        usecase = summary_usecases.ListSummaries(summaries_repo=summaries_repo)
        summaries = await usecase.execute(
            author_id=author_id,
            character_id=character_id,
            player_id=player_id,
            limit=limit,
            offset=offset,
        )
        return [summary_to_api(summary) for summary in summaries]
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
