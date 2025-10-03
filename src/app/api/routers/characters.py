"""Routes for creating and maintaining Nonagon characters."""

from fastapi import APIRouter, HTTPException

import app.api.deps as deps
from app.api.mappers import char_to_api
from app.api.schemas import Character, CharacterCreate, CharacterUpdate
from app.domain.usecase import characters as character_usecases

router = APIRouter(prefix="/v1/characters", tags=["Characters"])

chars_repo = deps.chars_repo
users_repo = deps.user_repo


@router.post(
    "",
    response_model=Character,
    status_code=201,
    response_model_exclude_none=True,
)
async def create_character(body: CharacterCreate) -> Character:
    """Create and persist a new character record owned by an existing user."""
    try:
        usecase = character_usecases.CreateCharacter(
            characters_repo=chars_repo,
            users_repo=users_repo,
        )
        character = await usecase.execute(
            owner_id=body.owner_id,
            name=body.name,
            ddb_link=body.ddb_link,
            character_thread_link=body.character_thread_link,
            token_link=body.token_link,
            art_link=body.art_link,
            description=body.description,
            notes=body.notes,
            tags=body.tags,
            created_at=body.created_at,
        )
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get(
    "/{character_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def get_character(character_id: str) -> Character:
    """Retrieve a character by its unique identifier."""
    try:
        usecase = character_usecases.GetCharacter(characters_repo=chars_repo)
        character = await usecase.execute(character_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.patch(
    "/{character_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def patch_character(
    character_id: str, body: CharacterUpdate | None = None
) -> Character:
    """Partially update character metadata such as links or descriptive text."""
    payload = body.model_dump(exclude_unset=True) if body else {}

    try:
        usecase = character_usecases.UpdateCharacterDetails(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(
            character_id,
            name=payload.get("name"),
            ddb_link=payload.get("ddb_link"),
            character_thread_link=payload.get("character_thread_link"),
            token_link=payload.get("token_link"),
            art_link=payload.get("art_link"),
            description=payload.get("description"),
            notes=payload.get("notes"),
            status=payload.get("status"),
            tags=payload.get("tags"),
            created_at=payload.get("created_at"),
            last_played_at=payload.get("last_played_at"),
        )
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete("/{character_id}", status_code=204)
async def delete_character(character_id: str) -> None:
    """Remove an existing character when it should no longer appear in the roster."""
    try:
        usecase = character_usecases.DeleteCharacter(characters_repo=chars_repo)
        await usecase.execute(character_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


# --- Telemetry ---
@router.post(
    "/{character_id}:incrementQuestsPlayed",
    response_model=Character,
    response_model_exclude_none=True,
)
async def inc_quests_played(character_id: str) -> Character:
    """Increment the number of quests a character has played in."""
    try:
        usecase = character_usecases.IncrementCharacterQuestsPlayed(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{character_id}:incrementSummariesWritten",
    response_model=Character,
    response_model_exclude_none=True,
)
async def inc_summaries_written(character_id: str) -> Character:
    """Increment the number of summaries authored by the character."""
    try:
        usecase = character_usecases.IncrementCharacterSummariesWritten(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{character_id}:updateLastPlayed",
    response_model=Character,
    response_model_exclude_none=True,
)
async def update_last_played(character_id: str) -> Character:
    """Record the last session date for a given character."""
    try:
        usecase = character_usecases.UpdateCharacterLastPlayed(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# --- Links ---
@router.post(
    "/{character_id}/playedWith/{other_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def add_played_with(character_id: str, other_id: str) -> Character:
    """Link two characters indicating they have played together."""
    try:
        usecase = character_usecases.AddCharacterPlayedWith(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id, other_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete(
    "/{character_id}/playedWith/{other_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def remove_played_with(character_id: str, other_id: str) -> Character:
    """Remove a played-with relationship between characters."""
    try:
        usecase = character_usecases.RemoveCharacterPlayedWith(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id, other_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{character_id}/playedIn/{quest_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def add_played_in(character_id: str, quest_id: str) -> Character:
    """Associate a quest the character participated in."""
    try:
        usecase = character_usecases.AddCharacterPlayedIn(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id, quest_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete(
    "/{character_id}/playedIn/{quest_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def remove_played_in(character_id: str, quest_id: str) -> Character:
    """Remove an association between a character and a quest."""
    try:
        usecase = character_usecases.RemoveCharacterPlayedIn(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id, quest_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{character_id}/mentionedIn/{summary_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def add_mentioned_in(character_id: str, summary_id: str) -> Character:
    """Mark that a character appears in a quest summary."""
    try:
        usecase = character_usecases.AddCharacterMentionedIn(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id, summary_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete(
    "/{character_id}/mentionedIn/{summary_id}",
    response_model=Character,
    response_model_exclude_none=True,
)
async def remove_mentioned_in(character_id: str, summary_id: str) -> Character:
    """Remove a summary mention from the character's record."""
    try:
        usecase = character_usecases.RemoveCharacterMentionedIn(
            characters_repo=chars_repo,
        )
        character = await usecase.execute(character_id, summary_id)
        return char_to_api(character)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
