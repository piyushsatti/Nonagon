# Nonagon API — v1

This API provides structured access to the **Nonagon domain**: Users, Characters, Quests, and Summaries.
It is designed with **explicit command endpoints** for state changes, mirroring domain use-cases.

---

## Base Information

* **Base URL (local dev):** `http://127.0.0.1:8000`
* **Versioning:** All endpoints are under `/v1/**`
* **Guild scoping (experimental):** Users routes are per-guild under `/v1/guilds/{guild_id}/users/**`.
* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health check:** `GET /healthz`

**Conventions**:

* **IDs:** Server-generated with prefixes: `USER`, `CHAR`, `QUES`, `SUMM` (e.g., `USER0001`).
* **Time:** RFC3339 UTC strings, e.g. `"2025-09-05T23:00:00Z"`.
* **Durations:** Expressed in minutes (`duration_min`).
* **Pagination:** Offset style, `?limit=50&offset=0`.
* **Errors:** Structured JSON Problem format:

```json
{
  "type": "https://api.nonagon.dev/errors/validation",
  "title": "Validation failed",
  "detail": "Starting time must be in the future",
  "fields": {"starting_at": "must be future"}
}
```

---

## Schemas

### User

**UserIn** (create/update body)

```json
{
  "discord_id": "12345",
  "dm_channel_id": "67890",
  "dm_opt_in": true,
  "roles": ["MEMBER", "PLAYER"]
}
```

**User** (response)

```json
{
  "user_id": "USER0001",
  "guild_id": 123,
  "discord_id": "12345",
  "roles": ["MEMBER","PLAYER"],
  "joined_at": "2025-08-31T12:00:00Z",
  "last_active_at": "2025-08-31T15:10:00Z",
  "messages_count_total": 5,
  "reactions_given": 1,
  "reactions_received": 2,
  "voice_total_time_spent": 0.5,
  "player": {"characters": ["CHAR0007"]},
  "referee": null
}
```

### Character

**CharacterIn** (create/update body)

```json
{
  "owner_id": "USER0001",
  "name": "Rook",
  "ddb_link": "https://ddb/...",
  "character_thread_link": "https://discord/...",
  "token_link": "https://cdn/...",
  "art_link": "https://img/...",
  "tags": ["fighter"]
}
```

**Character** (response)

```json
{
  "character_id": "CHAR0007",
  "owner_id": "USER0001",
  "name": "Rook",
  "status": "ACTIVE",
  "created_at": "2025-08-30T20:00:00Z",
  "quests_played": 0,
  "summaries_written": 0,
  "played_with": [],
  "played_in": [],
  "mentioned_in": []
}
```

### Quest

**QuestIn** (create/update body)

```json
{
  "referee_id": "USER0002",
  "title": "Into the Barrowmaze",
  "description": "Delve ...",
  "starting_at": "2025-09-05T23:00:00Z",
  "duration_min": 180,
  "image_url": "https://img/cover.png"
}
```

**Quest** (response)

```json
{
  "quest_id": "QUES0012",
  "referee_id": "USER0002",
  "title": "Into the Barrowmaze",
  "status": "ANNOUNCED",
  "signups_open": true,
  "signups": [
    {"user_id":"USER0001","character_id":"CHAR0007","selected":false}
  ],
  "linked_quests": [],
  "linked_summaries": []
}
```

### Summary

**SummaryIn** (create/update body)

```json
{
  "kind": "PLAYER",
  "author_id": "USER0001",
  "character_id": "CHAR0007",
  "quest_id": "QUES0012",
  "title": "Skulls and Silt",
  "description": "The party descended...",
  "raw": "markdown text ...",
  "created_on": "2025-09-06T03:10:00Z",
  "players": ["USER0001"],
  "characters": ["CHAR0007"]
}
```

**Summary** (response)

```json
{
  "summary_id": "SUMM0005",
  "kind": "PLAYER",
  "title": "Skulls and Silt",
  "created_on": "2025-09-06T03:10:00Z",
  "last_edited_at": null,
  "players": ["USER0001"],
  "characters": ["CHAR0007"],
  "linked_quests": [],
  "linked_summaries": []
}
```

---

## Endpoints

### Users (guild-scoped)

All Users endpoints require a path parameter `guild_id` and operate only on records for that guild.

* `POST /v1/guilds/{guild_id}/users` — Create a user
* `GET /v1/guilds/{guild_id}/users/{userId}` — Fetch user
* `PATCH /v1/guilds/{guild_id}/users/{userId}` — Update user
* `DELETE /v1/guilds/{guild_id}/users/{userId}` — Delete user
* `GET /v1/guilds/{guild_id}/users/by-discord/{discordId}` — Fetch by Discord snowflake
* `POST /v1/guilds/{guild_id}/users/{userId}:enablePlayer` — Add PLAYER role
* `POST /v1/guilds/{guild_id}/users/{userId}:disablePlayer` — Remove PLAYER role
* `POST /v1/guilds/{guild_id}/users/{userId}:enableReferee` — Add REFEREE role
* `POST /v1/guilds/{guild_id}/users/{userId}:disableReferee` — Remove REFEREE role
* `POST /v1/guilds/{guild_id}/users/{userId}/characters/{characterId}:link` — Link character to user
* `POST /v1/guilds/{guild_id}/users/{userId}/characters/{characterId}:unlink` — Unlink character
* `POST /v1/guilds/{guild_id}/users/{userId}:updateLastActive` — Update last active

### Characters

* `POST /v1/characters` — Create character
* `GET /v1/characters/{characterId}` — Fetch character
* `GET /v1/characters?owner_id=USER0001` — List/filter characters
* `PATCH /v1/characters/{characterId}` — Update character
* `DELETE /v1/characters/{characterId}` — Delete character
* `POST /v1/characters/{characterId}:incrementQuestsPlayed` — ++quests\_played
* `POST /v1/characters/{characterId}:incrementSummariesWritten` — ++summaries\_written
* `POST /v1/characters/{characterId}:updateLastPlayed` — Update last\_played
* `POST /v1/characters/{characterId}/playedWith/{otherCharId}` — Add played\_with
* `DELETE /v1/characters/{characterId}/playedWith/{otherCharId}` — Remove played\_with
* `POST /v1/characters/{characterId}/playedIn/{questId}` — Add played\_in
* `DELETE /v1/characters/{characterId}/playedIn/{questId}` — Remove played\_in
* `POST /v1/characters/{characterId}/mentionedIn/{summaryId}` — Add mentioned\_in
* `DELETE /v1/characters/{characterId}/mentionedIn/{summaryId}` — Remove mentioned\_in

### Quests

* `POST /v1/quests` — Create quest
* `GET /v1/quests/{questId}` — Fetch quest
* `GET /v1/quests?status=ANNOUNCED` — List/filter quests
* `PATCH /v1/quests/{questId}` — Update quest
* `DELETE /v1/quests/{questId}` — Delete quest
* `POST /v1/quests/{questId}/signups` — Add signup
* `DELETE /v1/quests/{questId}/signups/{userId}` — Remove signup
* `POST /v1/quests/{questId}/signups/{userId}:select` — Select signup
* `POST /v1/quests/{questId}:closeSignups` — Close signups
* `POST /v1/quests/{questId}:setCompleted` — Complete quest
* `POST /v1/quests/{questId}:setCancelled` — Cancel quest
* `POST /v1/quests/{questId}:setAnnounced` — Re-announce quest

### Summaries

* `POST /v1/summaries` — Create summary
* `GET /v1/summaries/{summaryId}` — Fetch summary
* `GET /v1/summaries?author_id=USER0001` — List by author
* `GET /v1/summaries?character_id=CHAR0007` — List by character
* `GET /v1/summaries?player_id=USER0001` — List by player
* `PATCH /v1/summaries/{summaryId}` — Update summary
* `DELETE /v1/summaries/{summaryId}` — Delete summary
* `POST /v1/summaries/{summaryId}:updateLastEdited` — Update last\_edited
* `POST /v1/summaries/{summaryId}/players/{userId}` — Add player
* `DELETE /v1/summaries/{summaryId}/players/{userId}` — Remove player
* `POST /v1/summaries/{summaryId}/characters/{characterId}` — Add character
* `DELETE /v1/summaries/{summaryId}/characters/{characterId}` — Remove character

---

## Validation Highlights

* **QuestIn**: `starting_at` must be in the future; `duration_min` ≥ 15 (recommend ≥ 60).
* **SummaryIn**: Requires non-empty `title`, `description`, `raw`; at least one `player` and one `character`.
* **CharacterIn**: Requires `owner_id` and valid links.
* **User**: Must respect role/profile consistency; operations are scoped to the provided `guild_id`.

---

## Notes

* All command endpoints (like `:closeSignups`) are **explicit verbs** for clarity and authorization.
* Use PATCH for incremental updates.
* Repos and use-cases enforce domain invariants.
