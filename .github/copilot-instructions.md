## Orientation
- Multi-service Python project: FastAPI API plus discord.py bot sharing domain code under `src/app`.
- Domain layer uses dataclasses (e.g. `src/app/domain/models/QuestModel.py`, `UserModel.py`) with explicit `validate_*` helpers; call them before persist/edit flows.
- IDs follow `EntityIDModel` prefixes (`USER`, `QUES`, `CHAR`, `SUMM`); parse via `.parse` and format with `str(id)` to stay human-readable.
- Guild scope is mandatory: most models carry `guild_id` and Mongo filters key off it, so set/propagate guild IDs on every persistence path.

## Runtime & Persistence
- API entrypoint is `src/app/api/main.py`; routers live in `src/app/api/routers/`; add startup/shutdown logic via `infra/lifecycle.py`.
- Async data access uses `infra/db.py` (Motor) and repositories like `infra/mongo/quests_repo.py`; sync bot flushes go through `infra/mongo/guild_adapter.py`.
- Serialization helpers `infra/serialization.py` convert dataclasses ↔ BSON (handling enums, datetimes, timedeltas); reuse them for any new persistence code.
- Sequential IDs come from `infra/db.next_id`, which stores counters in the `counters` collection per guild.

## Discord Bot Patterns
- Bot core (`src/app/bot/main.py`) maintains per-guild caches (`bot.guild_data`) and a `dirty_data` queue flushed by `_auto_persist_loop`; enqueue `(guild_id, user_id)` whenever you mutate cached users/quests.
- `ListnerCog` seeds caches from Discord events; reuse `_ensure_cached_user` / `_resolve_cached_user` instead of duplicating member-fetch logic.
- UI flows in cogs (`QuestCommandsCog`, `CharacterCommandsCog`) rely on `discord.ui.View` components and should defer responses within 3 seconds; default to ephemeral confirmations.
- Persistence from cogs respects `BOT_FLUSH_VIA_ADAPTER` to choose between sync adapters and direct collection writes—update both branches when schemas change.
- `QuestSignupView` reads quest IDs from embed footers (`Quest ID: …`); keep that footer format when adjusting embed builders.
- Add new feature cogs under `src/app/bot/cogs`; `Nonagon.setup_hook` auto-loads every non-underscored module there and logs load failures.
- Significant user actions should call `bot/utils/log_stream.send_demo_log` so demo telemetry stays accurate.

## Environment & Tooling
- Key env vars: `MONGO_URI`/`MONGODB_URI`/`ATLAS_URI`, `DB_NAME`, `BOT_TOKEN`, `BOT_CLIENT_ID`, optional `PRIMARY_GUILD_ID`; keep compose and code references aligned.
- Local run: `docker compose up --build` (containers mount `./src` and emit logs to `./logs`); ensure `.env` satisfies the compose variable chain.
- Developer install: `python -m pip install -e .[dev]`; run suites with `python -m pytest` (asyncio auto-mode configured in `pyproject.toml`).
- Tests are grouped by layer (`tests/domain`, `tests/infra`, `tests/bot`); async tests use `pytest.mark.asyncio` and can monkeypatch adapters like `quests_repo.COLL` for isolation.
- Bot/APIs log to `/app/logs`; add defensive log setup for Windows paths if you introduce new handlers.

## API Usage
- Health check lives at `/healthz`; `/v1` routers currently expose demo + users flows—extend routers in `api/routers` and reuse dependency helpers in `api/deps.py` for DB access.
- When adding endpoints, keep guild-aware filters consistent with repository interfaces and surface Discord-facing errors as JSON payloads with context.
