from app.domain.usecase.characters.create_character import CreateCharacter
from app.domain.usecase.characters.delete_character import DeleteCharacter
from app.domain.usecase.characters.get_character import GetCharacter
from app.domain.usecase.characters.record_character_activity import (
    AddCharacterMentionedIn,
    AddCharacterPlayedIn,
    AddCharacterPlayedWith,
    IncrementCharacterQuestsPlayed,
    IncrementCharacterSummariesWritten,
    RemoveCharacterMentionedIn,
    RemoveCharacterPlayedIn,
    RemoveCharacterPlayedWith,
    UpdateCharacterLastPlayed,
)
from app.domain.usecase.characters.update_character import UpdateCharacterDetails

__all__ = [
    "CreateCharacter",
    "DeleteCharacter",
    "GetCharacter",
    "UpdateCharacterDetails",
    "IncrementCharacterQuestsPlayed",
    "IncrementCharacterSummariesWritten",
    "UpdateCharacterLastPlayed",
    "AddCharacterPlayedWith",
    "RemoveCharacterPlayedWith",
    "AddCharacterPlayedIn",
    "RemoveCharacterPlayedIn",
    "AddCharacterMentionedIn",
    "RemoveCharacterMentionedIn",
]
