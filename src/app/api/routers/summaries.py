from datetime import datetime
from fastapi import APIRouter, HTTPException, Request

from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID
from app.domain.usecase.unit import summary_unit
from app.domain.models.summary.SummaryModel import SummaryKind as DSummaryKind
from app.api.schemas import Summary as APISumm, SummaryIn as APISummIn
from app.api.mappers import summary_to_api  # keep existing mapper name

router = APIRouter(prefix="/v1/summaries", tags=["Summaries"])

def _repos(req: Request):
    # exposes: users_repo, chars_repo, quests_repo, summaries_repo
    return req.app.state

# Create
@router.post(
    "",
    response_model=APISumm,
    status_code=201,
    response_model_exclude_none=True,
)
def create_summary(
    request: Request,
    body: APISummIn,
    kind: str | None = None,             # not in SummaryIn, accept via query
    author_id: str | None = None,        # not in SummaryIn, accept via query
    created_on: datetime | None = None,  # optional; domain can default if None
):
    # domain requires kind and author_id (based on your previous usecase)
    if not (kind and author_id):
        raise HTTPException(status_code=400, detail="kind and author_id are required")

    try:
        s = summary_unit.create_summary(
            summaries_repo=_repos(request).summaries_repo,
            users_repo=_repos(request).users_repo,
            char_repo=_repos(request).chars_repo,
            quest_repo=_repos(request).quests_repo,
            kind=DSummaryKind(kind),
            author_id=UserID.parse(author_id),
            character_id=CharacterID.parse(body.character_id) if body.character_id else None,
            quest_id=QuestID.parse(body.quest_id) if body.quest_id else None,
            raw=body.raw,
            title=body.title,
            description=getattr(body, "descroption", None),  # schema uses 'descroption'
            created_on=created_on,  # let domain set default if None
            players=tuple(UserID.parse(x) for x in (body.players or [])),
            characters=tuple(CharacterID.parse(x) for x in (body.characters or [])),
            linked_quests=tuple((body.linked_quests or [])),
            linked_summaries=tuple((body.linked_summaries or [])),
        )
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Read
@router.get(
    "/{summary_id}",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def get_summary(request: Request, summary_id: str):
    try:
        s = summary_unit.get_summary(_repos(request).summaries_repo, SummaryID.parse(summary_id))
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Patch (accepts SummaryIn and maps 'descroption' -> domain 'description')
@router.patch(
    "/{summary_id}",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def patch_summary(request: Request, summary_id: str, body: APISummIn):
    try:
        s = summary_unit.get_summary(_repos(request).summaries_repo, SummaryID.parse(summary_id))
        patch = body.model_dump(exclude_unset=True)

        # apply scalar fields if present
        if "title" in patch:
            s.title = patch["title"]
        if "raw" in patch:
            s.raw = patch["raw"]
        # schema uses 'descroption'
        if "descroption" in patch:
            s.description = patch["descroption"]

        # apply collection fields if present
        if "players" in patch:
            s.players = [UserID.parse(x) for x in (patch["players"] or [])]
        if "characters" in patch:
            s.characters = [CharacterID.parse(x) for x in (patch["characters"] or [])]

        s = summary_unit.update_summary(_repos(request).summaries_repo, s)
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Delete
@router.delete("/{summary_id}", status_code=204)
def delete_summary(request: Request, summary_id: str):
    try:
        summary_unit.delete_summary(_repos(request).summaries_repo, SummaryID.parse(summary_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Command: update last edited
@router.post(
    "/{summary_id}:updateLastEdited",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def update_last_edited(request: Request, summary_id: str):
    try:
        s = summary_unit.update_last_edited(_repos(request).summaries_repo, SummaryID.parse(summary_id))
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Links: players
@router.post(
    "/{summary_id}/players/{user_id}",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def add_player(request: Request, summary_id: str, user_id: str):
    try:
        s = summary_unit.add_player_to_summary(
            _repos(request).users_repo,
            _repos(request).summaries_repo,
            SummaryID.parse(summary_id),
            UserID.parse(user_id),
        )
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{summary_id}/players/{user_id}",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def remove_player(request: Request, summary_id: str, user_id: str):
    try:
        s = summary_unit.remove_player_from_summary(
            _repos(request).users_repo,
            _repos(request).summaries_repo,
            SummaryID.parse(summary_id),
            UserID.parse(user_id),
        )
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Links: characters
@router.post(
    "/{summary_id}/characters/{character_id}",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def add_character(request: Request, summary_id: str, character_id: str):
    try:
        s = summary_unit.add_character_to_summary(
            _repos(request).chars_repo,
            _repos(request).summaries_repo,
            SummaryID.parse(summary_id),
            CharacterID.parse(character_id),
        )
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{summary_id}/characters/{character_id}",
    response_model=APISumm,
    response_model_exclude_none=True,
)
def remove_character(request: Request, summary_id: str, character_id: str):
    try:
        s = summary_unit.remove_character_from_summary(
            _repos(request).chars_repo,
            _repos(request).summaries_repo,
            SummaryID.parse(summary_id),
            CharacterID.parse(character_id),
        )
        return summ_to_api(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# List / filter
@router.get(
    "",
    response_model=list[APISumm],
    response_model_exclude_none=True,
)
def list_summaries(
    request: Request,
    author_id: str | None = None,
    character_id: str | None = None,
    player_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    try:
        if author_id:
            res = summary_unit.list_summaries_by_author(
                _repos(request).summaries_repo, UserID.parse(author_id), limit=limit, offset=offset
            )
        elif character_id:
            res = summary_unit.list_summaries_by_character(
                _repos(request).summaries_repo, CharacterID.parse(character_id), limit=limit, offset=offset
            )
        elif player_id:
            res = summary_unit.list_summaries_by_player(
                _repos(request).summaries_repo, UserID.parse(player_id), limit=limit, offset=offset
            )
        else:
            res = summary_unit.list_summaries(_repos(request).summaries_repo, limit=limit, offset=offset)

        return [summ_to_api(x) for x in res]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
