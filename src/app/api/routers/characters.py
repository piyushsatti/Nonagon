from fastapi import APIRouter, HTTPException, Request
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID
from app.domain.usecase.unit import character_unit
from app.api.schemas import Character as APIChar, CharacterIn as APICharIn
from app.api.mappers import char_to_api

router = APIRouter(prefix="/v1/characters", tags=["Characters"])

def _repos(req: Request):
    return req.app.state  # users_repo, chars_repo, quests_repo, summaries_repo

@router.post(
    "",
    response_model=APIChar,
    status_code=201,
    response_model_exclude_none=True,
)
def create_character(request: Request, body: APICharIn):
    try:
        ch = character_unit.create_character(
            char_repo=_repos(request).chars_repo,
            users_repo=_repos(request).users_repo,
            owner_id=UserID.parse(body.owner_id) if body.owner_id else None,
            name=body.name,
            ddb_link=body.ddb_link or "",
            character_thread_link=body.character_thread_link or "",
            token_link=body.token_link or "",
            art_link=body.art_link or "",
            description=body.description,
            notes=body.notes,
            tags=tuple(body.tags or []),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{character_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def get_character(request: Request, character_id: str):
    try:
        ch = character_unit.get_character(_repos(request).chars_repo, CharacterID.parse(character_id))
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch(
    "/{character_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def patch_character(request: Request, character_id: str, body: APICharIn):
    try:
        repo = _repos(request).chars_repo
        ch = character_unit.get_character(repo, CharacterID.parse(character_id))

        patch = body.model_dump(exclude_unset=True)
        ch.change_attributes(
            name=patch.get("name"),
            ddb_link=patch.get("ddb_link"),
            character_thread_link=patch.get("character_thread_link"),
            token_link=patch.get("token_link"),
            art_link=patch.get("art_link"),
            description=patch.get("description"),
            notes=patch.get("notes"),
        )
        # status change mapping
        if patch.get("status") == "RETIRED":
            ch.deactivate()
        elif patch.get("status") == "ACTIVE":
            ch.activate()

        ch = character_unit.update_character(repo, ch)
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{character_id}", status_code=204)
def delete_character(request: Request, character_id: str):
    try:
        character_unit.delete_character(_repos(request).chars_repo, CharacterID.parse(character_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- Telemetry ---
@router.post(
    "/{character_id}:incrementQuestsPlayed",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def inc_quests_played(request: Request, character_id: str):
    try:
        ch = character_unit.increment_quests_played(_repos(request).chars_repo, CharacterID.parse(character_id))
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{character_id}:incrementSummariesWritten",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def inc_summaries_written(request: Request, character_id: str):
    try:
        ch = character_unit.increment_summaries_written(_repos(request).chars_repo, CharacterID.parse(character_id))
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{character_id}:updateLastPlayed",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def update_last_played(request: Request, character_id: str):
    try:
        ch = character_unit.update_last_played_at(_repos(request).chars_repo, CharacterID.parse(character_id))
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Links ---
@router.post(
    "/{character_id}/playedWith/{other_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def add_played_with(request: Request, character_id: str, other_id: str):
    try:
        ch = character_unit.add_played_with(
            _repos(request).chars_repo,
            CharacterID.parse(character_id),
            CharacterID.parse(other_id),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{character_id}/playedWith/{other_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def remove_played_with(request: Request, character_id: str, other_id: str):
    try:
        ch = character_unit.remove_played_with(
            _repos(request).chars_repo,
            CharacterID.parse(character_id),
            CharacterID.parse(other_id),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{character_id}/playedIn/{quest_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def add_played_in(request: Request, character_id: str, quest_id: str):
    try:
        ch = character_unit.add_played_in(
            _repos(request).chars_repo,
            CharacterID.parse(character_id),
            QuestID.parse(quest_id),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{character_id}/playedIn/{quest_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def remove_played_in(request: Request, character_id: str, quest_id: str):
    try:
        ch = character_unit.remove_played_in(
            _repos(request).chars_repo,
            CharacterID.parse(character_id),
            QuestID.parse(quest_id),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{character_id}/mentionedIn/{summary_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def add_mentioned_in(request: Request, character_id: str, summary_id: str):
    try:
        ch = character_unit.add_mentioned_in(
            _repos(request).chars_repo,
            CharacterID.parse(character_id),
            SummaryID.parse(summary_id),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{character_id}/mentionedIn/{summary_id}",
    response_model=APIChar,
    response_model_exclude_none=True,
)
def remove_mentioned_in(request: Request, character_id: str, summary_id: str):
    try:
        ch = character_unit.remove_mentioned_in(
            _repos(request).chars_repo,
            CharacterID.parse(character_id),
            SummaryID.parse(summary_id),
        )
        return char_to_api(ch)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
