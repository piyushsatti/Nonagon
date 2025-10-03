# Nonagon API Reference (v1)

The Nonagon API powers quest ingestion, roster management, and summary publication for the Nonagon Discord community. Every resource is exposed with explicit command-style endpoints to mirror domain use-cases and keep side effects clear.

---

## Base information

- **Local base URL:** `http://127.0.0.1:8000`
- **API versioning:** all production endpoints are rooted at `/v1/**`
- **Interactive docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Core health checks:**
  - `GET /healthz` — process & Mongo connectivity probe
  - `GET /v1/users/healthz` — user service health probe (used by admin tooling)

### Conventions

- **Identifiers** use domain prefixes (`USER`, `CHAR`, `QUES`, `SUMM`).
- **Timestamps** are RFC3339/UTC strings (e.g. `"2025-09-05T23:00:00Z"`).
- **Durations** in requests are expressed as integer hours (`duration_hours`).
- **Pagination** uses `limit` (default 50) and `offset` query params on list endpoints.
- **Errors** follow an RFC 7807/"problem+json" document shape:

```json
{
  "type": "https://api.nonagon.dev/errors/validation",
  "title": "Validation failed",
  "detail": "Starting time must be in the future",
  "fields": {"starting_at": "must be future"}
}
```

Unless otherwise noted, endpoints respond with 400 for domain validation problems, 404 for missing resources, and 422 for JSON schema violations.

---

## Schemas & payloads

All schemas live in `app/api/schemas.py`. The snippets below highlight the most important request and response bodies.

### Enumerations

- **`UserRole`** – `MEMBER`, `PLAYER`, `REFEREE`
- **`CharacterStatus`** – `ACTIVE`, `INACTIVE`
- **`QuestStatus`** – `ANNOUNCED`, `SIGNUP_CLOSED`, `COMPLETED`, `CANCELLED`
- **`SummaryKind`** – `PLAYER`, `REFEREE`

### Users payloads

#### UserCreate

```json
{
  "discord_id": "123456789012345678",
  "dm_channel_id": "987654321098765432",
  "roles": ["MEMBER", "PLAYER"],
  "joined_at": "2025-08-31T12:00:00Z"
}
```

All fields are optional; missing roles default to an empty list.

#### User

```json
{
  "user_id": "USER0001",
  "discord_id": "123456789012345678",
  "dm_channel_id": "987654321098765432",
  "roles": ["MEMBER", "PLAYER"],
  "joined_at": "2025-08-31T12:00:00Z",
  "last_active_at": "2025-09-02T17:45:00Z",
  "is_member": true,
  "is_player": true,
  "is_referee": false,
  "messages_count_total": 42,
  "reactions_given": 8,
  "reactions_received": 5,
  "voice_total_hours": 3.5,
  "player": {
    "characters": ["CHAR0007"],
    "quests_applied": ["QUES0012"],
    "quests_played": ["QUES0004"],
    "summaries_written": ["SUMM0008"],
    "joined_on": "2025-01-15T00:00:00Z",
    "last_played_on": "2025-08-29T21:00:00Z"
  },
  "referee": null
}
```

#### ActivityPing

```json
{
  "active_at": "2025-09-02T17:45:00Z"
}
```

### Characters payloads

#### CharacterCreate

```json
{
  "owner_id": "USER0001",
  "name": "Ser Rook",
  "ddb_link": "https://ddb.ac/characters/rook",
  "character_thread_link": "https://discord.com/channels/...",
  "token_link": "https://cdn.example.com/tokens/rook.png",
  "art_link": "https://cdn.example.com/art/rook.png",
  "description": "Battle-scarred fighter",
  "notes": "Prefers shield wall tactics",
  "tags": ["fighter", "soldier"],
  "created_at": "2025-08-25T12:00:00Z"
}
```

#### Character

```json
{
  "character_id": "CHAR0007",
  "owner_id": "USER0001",
  "name": "Ser Rook",
  "ddb_link": "https://ddb.ac/characters/rook",
  "character_thread_link": "https://discord.com/channels/...",
  "token_link": "https://cdn.example.com/tokens/rook.png",
  "art_link": "https://cdn.example.com/art/rook.png",
  "description": "Battle-scarred fighter",
  "notes": "Prefers shield wall tactics",
  "tags": ["fighter", "soldier"],
  "status": "ACTIVE",
  "created_at": "2025-08-25T12:00:00Z",
  "last_played_at": "2025-09-01T03:30:00Z",
  "quests_played": 5,
  "summaries_written": 1,
  "played_with": ["CHAR0008"],
  "played_in": ["QUES0012"],
  "mentioned_in": ["SUMM0008"]
}
```

### Quests payloads

#### QuestCreate

```json
{
  "referee_id": "USER0002",
  "channel_id": "123456789012345678",
  "message_id": "987654321098765432",
  "raw": "Quest announcement markdown",
  "title": "Into the Barrowmaze",
  "description": "Delve beneath the ruins...",
  "starting_at": "2025-09-05T23:00:00Z",
  "duration_hours": 3,
  "image_url": "https://cdn.example.com/quests/barrowmaze.png"
}
```

#### Quest

```json
{
  "quest_id": "QUES0012",
  "referee_id": "USER0002",
  "channel_id": "123456789012345678",
  "message_id": "987654321098765432",
  "raw": "Quest announcement markdown",
  "title": "Into the Barrowmaze",
  "description": "Delve beneath the ruins...",
  "starting_at": "2025-09-05T23:00:00Z",
  "duration_hours": 3,
  "image_url": "https://cdn.example.com/quests/barrowmaze.png",
  "status": "ANNOUNCED",
  "started_at": null,
  "ended_at": null,
  "signups_open": true,
  "signups": [
    {"user_id": "USER0001", "character_id": "CHAR0007", "selected": false}
  ],
  "linked_quests": [],
  "linked_summaries": []
}
```

#### QuestSignup

```json
{
  "user_id": "USER0001",
  "character_id": "CHAR0007",
  "selected": false
}
```

### Summaries payloads

#### SummaryCreate

```json
{
  "kind": "PLAYER",
  "author_id": "USER0001",
  "character_id": "CHAR0007",
  "quest_id": "QUES0012",
  "raw": "markdown body",
  "title": "Skulls and Silt",
  "description": "The party descended...",
  "created_on": "2025-09-06T03:10:00Z",
  "players": ["USER0001"],
  "characters": ["CHAR0007"],
  "linked_quests": ["QUES0012"],
  "linked_summaries": []
}
```

#### Summary

```json
{
  "summary_id": "SUMM0005",
  "kind": "PLAYER",
  "author_id": "USER0001",
  "character_id": "CHAR0007",
  "quest_id": "QUES0012",
  "raw": "markdown body",
  "title": "Skulls and Silt",
  "description": "The party descended...",
  "created_on": "2025-09-06T03:10:00Z",
  "last_edited_at": null,
  "players": ["USER0001"],
  "characters": ["CHAR0007"],
  "linked_quests": ["QUES0012"],
  "linked_summaries": []
}
```

### Admin sync payloads

#### GuildSyncRequest

```json
{
  "guild_id": "1372610481860120638",
  "members": [
    {
      "discord_id": "123456789012345678",
      "joined_at": "2024-01-01T00:00:00Z",
      "is_bot": false
    }
  ]
}
```

The response is a `SyncStats` object with `processed` and `created` counts.

---

## Endpoint catalogue

Each table lists the method, path, description, and notable request/response details. Unless noted, bodies reference the schema sections above.

### Users endpoints

| Method | Path | Description | Body | Notes |
| --- | --- | --- | --- | --- |
| GET | `/v1/users/healthz` | Lightweight probe for external monitors | – | Returns `{ "ok": true }` |
| POST | `/v1/users` | Create or ensure a user | `UserCreate` (optional) | Missing body defaults to an empty payload |
| GET | `/v1/users/{user_id}` | Retrieve a user by Nonagon ID | – | 404 if unknown |
| GET | `/v1/users/by-discord/{discord_id}` | Retrieve a user by Discord snowflake | – | Normalizes numeric string IDs |
| PATCH | `/v1/users/{user_id}` | Update contact details / join metadata | `UserUpdate` (partial) | Only supplied fields change |
| DELETE | `/v1/users/{user_id}` | Remove a user | – | Returns 204 |
| POST | `/v1/users/{user_id}:enablePlayer` | Promote to player | – | Toggles `roles` & player profile |
| POST | `/v1/users/{user_id}:disablePlayer` | Demote to member | – | Removes player profile data |
| POST | `/v1/users/{user_id}:enableReferee` | Promote player to referee | – | Requires user already be a player |
| POST | `/v1/users/{user_id}:disableReferee` | Revoke referee role | – | Returns updated `User` |
| POST | `/v1/users/{user_id}/characters/{character_id}:link` | Attach character | – | Fails if either ID is unknown |
| POST | `/v1/users/{user_id}/characters/{character_id}:unlink` | Detach character | – | Character remains but no longer linked |
| POST | `/v1/users/{user_id}:updateLastActive` | Record general activity | `ActivityPing` (optional) | Defaults to `now()` if omitted |
| POST | `/v1/users/{user_id}:updatePlayerLastActive` | Record player activity | `ActivityPing` (optional) | Requires player profile |
| POST | `/v1/users/{user_id}:updateRefereeLastActive` | Record referee activity | `ActivityPing` (optional) | Requires referee profile |

### Characters endpoints

| Method | Path | Description | Body | Notes |
| --- | --- | --- | --- | --- |
| POST | `/v1/characters` | Create a character | `CharacterCreate` | Owner must exist |
| GET | `/v1/characters/{character_id}` | Fetch a character | – | 404 if unknown |
| PATCH | `/v1/characters/{character_id}` | Update core metadata | `CharacterUpdate` | Partial updates supported |
| DELETE | `/v1/characters/{character_id}` | Delete a character | – | Returns 204 |
| POST | `/v1/characters/{id}:incrementQuestsPlayed` | Telemetry increment | – | Increments counter, returns `Character` |
| POST | `/v1/characters/{id}:incrementSummariesWritten` | Telemetry increment | – | |
| POST | `/v1/characters/{id}:updateLastPlayed` | Touch `last_played_at` | – | Sets timestamp to `now()` |
| POST | `/v1/characters/{id}/playedWith/{other_id}` | Record co-played link | – | Adds `other_id` to `played_with` |
| DELETE | `/v1/characters/{id}/playedWith/{other_id}` | Remove co-played link | – | |
| POST | `/v1/characters/{id}/playedIn/{quest_id}` | Record quest participation | – | |
| DELETE | `/v1/characters/{id}/playedIn/{quest_id}` | Remove quest participation | – | |
| POST | `/v1/characters/{id}/mentionedIn/{summary_id}` | Record summary mention | – | |
| DELETE | `/v1/characters/{id}/mentionedIn/{summary_id}` | Remove summary mention | – | |

### Quests endpoints

| Method | Path | Description | Body | Notes |
| --- | --- | --- | --- | --- |
| POST | `/v1/quests` | Create a quest | `QuestCreate` | `duration_hours` converted to `timedelta` |
| GET | `/v1/quests/{quest_id}` | Fetch a quest | – | 404 if unknown |
| PATCH | `/v1/quests/{quest_id}` | Update quest metadata | `QuestUpdate` | Duration hours optional |
| DELETE | `/v1/quests/{quest_id}` | Delete a quest | – | Returns 204 |
| POST | `/v1/quests/{quest_id}/signups` | Add signup | `QuestSignup` | Validates user & character IDs |
| DELETE | `/v1/quests/{quest_id}/signups/{user_id}` | Remove signup | – | |
| POST | `/v1/quests/{quest_id}/signups/{user_id}:select` | Mark signup as selected | – | |
| POST | `/v1/quests/{quest_id}:closeSignups` | Close signups | – | Sets `signups_open = false` |
| POST | `/v1/quests/{quest_id}:setCompleted` | Mark completed | – | Sets status & timestamps |
| POST | `/v1/quests/{quest_id}:setCancelled` | Mark cancelled | – | |
| POST | `/v1/quests/{quest_id}:setAnnounced` | Reset to announced | – | |

> _Note:_ There is currently no `/v1/quests` list endpoint; quests are consumed via Discord ingestion and direct ID lookups.

### Summaries endpoints

| Method | Path | Description | Body | Notes |
| --- | --- | --- | --- | --- |
| POST | `/v1/summaries` | Create a summary | `SummaryCreate` | Player/character IDs validated |
| GET | `/v1/summaries/{summary_id}` | Fetch a summary | – | 404 if unknown |
| PATCH | `/v1/summaries/{summary_id}` | Update summary content | `SummaryUpdate` | Optional fields only |
| DELETE | `/v1/summaries/{summary_id}` | Delete summary | – | Returns 204 |
| POST | `/v1/summaries/{summary_id}:updateLastEdited` | Touch `last_edited_at` | `datetime` query/body optional | Passing no value uses server `now()` |
| POST | `/v1/summaries/{summary_id}/players/{user_id}` | Add player link | – | |
| DELETE | `/v1/summaries/{summary_id}/players/{user_id}` | Remove player link | – | |
| POST | `/v1/summaries/{summary_id}/characters/{character_id}` | Add character link | – | |
| DELETE | `/v1/summaries/{summary_id}/characters/{character_id}` | Remove character link | – | |
| GET | `/v1/summaries` | List summaries | – | Query params: `author_id`, `character_id`, `player_id`, `limit`, `offset` (only one filter at a time) |

### Admin

| Method | Path | Description | Body | Notes |
| --- | --- | --- | --- | --- |
| POST | `/v1/admin/users/sync` | Bulk reconcile Discord guild members into the domain store | `GuildSyncRequest` | Requires `X-Admin-Token` via `deps.require_admin` (see deployment secrets) |

The admin endpoint reports how many members were processed and how many new domain users were created.

---

## Validation highlights & domain rules

- **User promotion** endpoints guard against illegal role transitions (e.g., promoting to referee without being a player).
- **Quest creation** requires existing referee and Discord message metadata; durations are converted to timedeltas and must be positive if supplied.
- **Summary creation** enforces non-empty `raw`, `title`, and `description` plus at least one player & character reference.
- **Character linkage** endpoints ensure both ends exist before mutating associations.
- **Guild sync** rejects payloads that do not match the configured admin token or contain malformed member data.

---

## Tips for working with the API

- Use the generated Swagger UI for quick contract checks—the request/response models map 1:1 to the schemas above.
- For automation, include idempotency by reusing Nonagon IDs; most mutation endpoints return the updated resource immediately.
- Domain services emit structured audit logs; inspect `/var/log/nonagon/api.log` when running via Docker compose for traceability.
