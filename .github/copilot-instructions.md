## Architecture Snapshot
- Multi-service Python 3.11 project: FastAPI API (`src/app/api`) and discord.py bot (`src/app/bot`) share domain models under `src/app/domain`.
- Domain entities are dataclasses (e.g. `domain/models/QuestModel.py`, `UserModel.py`) with explicit `validate_*` methods; run them before persisting or mutating caches.
- All persistent models require `guild_id`; repositories and bot caches rely on it, so set/propagate the guild on every write path.
- IDs use `EntityIDModel` subclasses (`UserID`, `QuestID`, `CharacterID`, `SummaryID`); parse with `.parse(...)` and serialize via `str(id)` to preserve readable prefixes.

## Persistence & Repos
- Async Mongo access lives in `infra/db.py` + `infra/mongo/*_repo.py`; reuse `get_guild_db` and `infra/serialization.to_bson/from_bson` when adding adapters.
- `infra/db.next_id` issues sequential IDs per guild (stored in the `counters` collection); always pass the guild id when requesting a new ID.
- Bot-side sync writes use `infra/mongo/guild_adapter.py` when `BOT_FLUSH_VIA_ADAPTER` is true; keep both adapter and direct Motor paths aligned with schema changes.
- Tests monkeypatch module-level singletons (e.g. `api/routers/quests.py`’s `quests_repo`) to isolate datastore behavior; follow that approach for new routers.

## Discord Bot Workflow
- `bot/main.py` bootstraps cogs, manages per-guild caches in `bot.guild_data`, and flushes dirty users via `_auto_persist_loop`; enqueue `(guild_id, user_id)` whenever cached users change.
- `ListnerCog` helpers like `_ensure_cached_user` / `_resolve_cached_user` seed cache entries from gateway events—reuse them instead of duplicating Discord member lookups.
- Quest flows in `bot/cogs/QuestCommandsCog.py` respect `FORGE_CHANNEL_IDS`, call APIs via `QUEST_API_BASE_URL`, and `QuestSignupView` infers IDs from embed footers formatted as `Quest ID: …`.
- Embed rendering is centralized in `bot/utils/quest_embeds.py`; extend `QuestEmbedData` / `QuestEmbedRoster` so footers stay parseable by signup views.

## API Patterns
- FastAPI entrypoint is `api/main.py`; routers under `api/routers` transform domain instances via `api/mappers.py` before returning Pydantic schemas.
- `_persist_quest` in `api/routers/quests.py` runs `Quest.validate_quest()` prior to `quests_repo.upsert`; mirror that guardrail for new quest operations.
- All API routes are guild-scoped (`/v1/guilds/{guild_id}/…`) and raise `HTTPException` with 4xx codes when invariants fail—match that pattern for consistency.
- When adding repo fields, update `infra/serialization` to handle new enums/datetimes/timedeltas so Motor encoding remains lossless.

## Dev Workflow & Tooling
- Docker compose (`docker-compose.yml`) builds `api` and `bot`; env resolution prefers `MONGO_URI` → `MONGODB_URI` → `ATLAS_URI`, so keep `.env` aligned with that chain.
- Local install: `python -m pip install -e .[dev]`; run tests with `python -m pytest` (`pytest.ini` sets `asyncio_mode=auto` and session-scoped loops).
- Start the API with `uvicorn app.api.main:app --reload`; the bot in `bot/main.py` requires valid `BOT_TOKEN` / `BOT_CLIENT_ID` and configured Discord intents.
- Logs land under `./logs` for both services; startup code already guards against missing directories—maintain that convention on new handlers.
- Quest interactions emit telemetry through `bot/utils/log_stream.send_demo_log`; keep those calls when refactoring to preserve demo analytics.
