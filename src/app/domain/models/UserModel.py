from __future__ import annotations
from dataclasses import dataclass, field, fields, asdict, replace
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from datetime import timedelta

from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID

class Role(Enum):
  MEMBER = "MEMBER"
  PLAYER = "PLAYER"
  REFEREE = "REFEREE"


@dataclass
class User:
  # Identity
  user_id: UserID
  discord_id: Optional[str] = None
  dm_channel_id: Optional[str] = None

  # Roles
  roles: List[Role] = field(default_factory=lambda: [Role.MEMBER])

  # Timestamps / activity
  joined_at: Optional[datetime] = None
  last_active_at: Optional[datetime] = None

  # Engagement telemetry
  messages_count_total: int = 0
  reactions_given: int = 0
  reactions_received: int = 0
  voice_total_time_spent: int = 0  # hours

  # Optional role profiles
  player: Optional[Player] = None
  referee: Optional[Referee] = None

  # ---------- User helpers ----------
  def add_role(self, role: Role) -> None:
    if role not in self.roles:
      self.roles.append(role)

  def enable_player(self) -> None:
    self.add_role(Role.PLAYER)
    if self.player is None:
      self.player = Player()
      self.player.from_dict()
  
  def disable_player(self) -> None:
    
    if Role.REFEREE in self.roles:
      raise ValueError("Cannot disable PLAYER role while REFEREE role is active. Disable REFEREE first.")

    if Role.PLAYER in self.roles:
      self.roles.remove(Role.PLAYER)
    
    self.player = None

  def enable_referee(self) -> None:
    if Role.PLAYER not in self.roles:
      self.enable_player(self)
      self.player.from_dict()

    self.add_role(Role.REFEREE)
    if self.referee is None:
      self.referee = Referee()
      self.referee.from_dict()

  def disable_referee(self) -> None:
    
    if Role.REFEREE in self.roles:
      self.roles.remove(Role.REFEREE)
    
    self.referee = None

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
  def is_character_owner(self, char_id: CharacterID) -> bool:

    if not self.is_player:
      raise ValueError("User is not a player")

    if char_id in self.player.characters:
      return True
    
    return False

  # ---------- Getter ----------

  def get_player(self) -> Player:

    if not self.is_player or self.player is None:
      raise ValueError("User is not a player")
    
    return self.player
  
  def get_characters(self) -> List[CharacterID]:

    if not self.is_player or self.player is None:
      raise ValueError("User is not a player")
    
    return self.player.characters

  def get_referee(self) -> Referee:
    
    if not self.is_referee or self.referee is None:
      raise ValueError("User is not a referee")
    
    return self.referee

  # ---------- Updaters ----------
  
  def update_dm_channel(self, dm_channel_id: str) -> None:
    self.dm_channel_id = dm_channel_id

  def update_joined_at(self, joined_at: datetime, override: bool = False) -> None:

    if self.joined_at is not None or not override:
      raise ValueError("joined_at is already set. Use override=True to force change.")
    
    self.joined_at = joined_at

  def update_last_active(self, active_at: datetime) -> None:
    self.last_active_at = active_at
  
  def increment_messages_count(self, count: int = 1) -> None:
    if count < 0:
      raise ValueError("Count must be non-negative")
    
    self.messages_count_total += count
    return None
  
  def increment_reactions_given(self, count: int = 1) -> None:
    if count < 0:
      raise ValueError("Count must be non-negative")
    
    self.reactions_given += count
    return None
  
  def increment_reactions_received(self, count: int = 1) -> None:
    if count < 0:
      raise ValueError("Count must be non-negative")
    
    self.reactions_received += count
    return None

  def add_voice_time_spent(self, seconds: int) -> None:
    
    if seconds < 0:
      raise ValueError("Hours must be non-negative")
    
    self.voice_total_time_spent += seconds / 3600
    
    return None

  # ---------- Helpers ----------

  def from_dict(self, data: Dict[str, Any]) -> User:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)


@dataclass
class Player():

  characters: List[CharacterID] = field(default_factory=list)
  
  # Telemetry
  joined_on: datetime = None
  created_first_character_on: datetime = None
  last_played_on: datetime = None
  quests_applied: List[QuestID] = field(default_factory=list)
  quests_played: List[QuestID] = field(default_factory=list)
  summaries_written: List[SummaryID] = field(default_factory=list)
  played_with_character: Dict[CharacterID, Tuple] = field(default_factory=dict) # {CharID: (Freq, Hours)}


  # ---------- Updaters ----------
  
  def add_character(self, char_id: CharacterID) -> None:
    
    if char_id not in self.characters:
      self.characters.append(char_id)
  
  def remove_character(self, char_id: CharacterID) -> None:
    
    if char_id in self.characters:
      self.characters.remove(char_id)

  def update_joined_on(self, joined_on: datetime, override: bool = False) -> None:
    
    if self.joined_on is not None and not override:
      raise ValueError("joined_on is already set. Use override=True to force change.")
    
    self.joined_on = joined_on

  def update_created_first_character_on(self, created_on: datetime, override: bool = False) -> None:
    
    if self.created_first_character_on is not None and not override:
      raise ValueError("created_first_character_on is already set. Use override=True to force change.")
    
    self.created_first_character_on = created_on

  def update_last_played_on(self, played_on: datetime) -> None:
    self.last_played_on = played_on

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
    
    if char_id in self.played_with_character:
      freq, total_hours = self.played_with_character[char_id]
      self.played_with_character[char_id] = (freq + 1, total_hours + seconds / 3600)
    
    else:
      self.played_with_character[char_id] = (1, seconds / 3600)
    
    return None

  def remove_played_with_character(self, char_id: CharacterID) -> None:
    
    if char_id in self.played_with_character:
      del self.played_with_character[char_id]

  # ---------- helpers ----------
  def from_dict(self, data: Dict[str, Any]) -> Player:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)

@dataclass
class Referee():
  
  quests_hosted: List[QuestID] = field(default_factory=list)
  summaries_written: List[SummaryID] = field(default_factory=list)

  # Telemetry
  first_dmed_on: datetime = None
  last_dmed_on: datetime = None
  collabed_with: Dict[UserID, Tuple] = field(default_factory=dict)  # {user_id: (collab_count, collab_hours)
  hosted_for: Dict[UserID, int] = field(default_factory=dict)    # {user_id: count_sessions}

  # ---------- Updaters ----------
  def add_quest_hosted(self, quest_id: QuestID) -> None:
    
    if quest_id not in self.quests_hosted:
      self.quests_hosted.append(quest_id)

  def increment_summaries_written(self, summary_id: SummaryID) -> None:
    
    if summary_id not in self.summaries_written:
      self.summaries_written.append(summary_id)

  def update_first_dmed_on(self, dmed_on: datetime, override: bool = False) -> None:
    
    if self.first_dmed_on is not None and not override:
      raise ValueError("first_dmed_on is already set. Use override=True to force change.")
    
    self.first_dmed_on = dmed_on

  def update_last_dmed_on(self, dmed_on: datetime) -> None:
    self.last_dmed_on = dmed_on

  def add_collabed_with(self, user_id: UserID, seconds: int = 0) -> None:
    
    if user_id in self.collabed_with:
      count, total_hours = self.collabed_with[user_id]
      self.collabed_with[user_id] = (count + 1, total_hours + seconds / 3600)
    
    else:
      self.collabed_with[user_id] = (1, seconds / 3600)

  def remove_collabed_with(self, user_id: UserID) -> None:
    
    if user_id in self.collabed_with:
      del self.collabed_with[user_id]

  def add_hosted_for(self, user_id: UserID) -> None:
    
    if user_id in self.hosted_for:
      self.hosted_for[user_id] += 1
    
    else:
      self.hosted_for[user_id] = 1

  def remove_hosted_for(self, user_id: UserID) -> None:
    
    if user_id in self.hosted_for:
      del self.hosted_for[user_id]

  # ---------- helpers ----------
  def from_dict(self, data: Dict[str, Any]) -> Referee:
    valid = {f.name for f in fields(self.__dict__)}
    filtered = {k: v for k, v in data.items() if k in valid}
    return replace(self, **filtered)

  def to_dict(self) -> Dict[str, Any]:
    return asdict(self)