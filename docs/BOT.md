# Nonagon Discord Bot Guide (2025 refresh)

Nonagon pairs an opinionated Discord experience with a FastAPI backend to automate quest scheduling, player provisioning, post-session storytelling, and now **quest intelligence lookups** directly from Discord. This document focuses on the bot: the cogs, commands, and how they connect to the API.

---

## 1. Capabilities at a Glance

| Flow | Highlights |
|------|------------|
| Quest lifecycle | Slash commands for announce → sign-ups → roster selection → completion, backed by async use cases. |
| Player management | Automatic user provisioning, role assignment, and character summaries. |
| Adventure summaries | Collect player/DM recaps, link them to quests, and surface them through the `/v1/summaries` API. |
| Admin operations | Protected admin sync endpoints (`/v1/admin/**`) with bot-managed tokens for batch updates. |
| Quest intelligence *(new)* | `/quest-info quest` & `/quest-info summary` embed builders resolving Discord message links and surfacing linked records. |

---

## 2. Core Cogs & Slash Commands

| Cog | Purpose | Representative Commands / Interactions |
|-----|---------|-----------------------------------------|
| `UserProvisioningCog` | Onboards Discord members into the domain model. | `/user register`, `/user grant-role`, `/user revoke-role` |
| `RoleManagementCog` | Keeps guild roles in sync with domain roles (PLAYER / REFEREE). | `/role sync`, auto reactions to roster changes |
| `QuestIngestionCog` | Creates quests, opens/closes signups, tracks roster. | `/quest create`, buttons for **Sign up**, **Select roster**, **Set status** |
| `CharacterCommandsCog` | CRUD for characters plus telemetry updates. | `/character create`, `/character update`, `/character stats` |
| `AdventureSummaryIngestionCog` | Collects markdown recaps, validates required players/characters, and writes through the HTTP API. | Modal invoked via **Submit summary** button; `/summary touch` |
| `BotSetupCog` | Administers guild-specific channel and role configuration, plus quick DM helpers. | `/bot-setup`, `/bot-set-main-channel`, `/bot-set-summary-channel`, `/bot-set-player-role`, `/bot-set-referee-role`, `/bot-dm-player`, `/bot-settings` |
| `GeneralCog` | Lightweight health checks plus quest lookup embeds for moderators. | `/ping`, `/pingstatus`, `!ping`, `!pingstatus`, `/quest-info quest`, `/quest-info summary` |

All cogs defer within three seconds, call the relevant use cases (shared with the HTTP edge), and then present embeds/views to Discord users.

### GeneralCog quest lookup group *(new)*

- `/quest-info quest <ID | Discord message link>` — resolves quest announcements, builds an embed with schedule metadata, referee info, linked summaries, and jump-to-message hyperlinks.
- `/quest-info summary <ID | Discord message link>` — fetches a summary, shows sibling recaps, participant highlights, related links, and the parent quest reference.
- Backed by the `QuestLookupService`, which pulls from Mongo repositories, normalizes Discord message links, and gracefully handles missing data.
- Embeds truncate long fields, limit to five related items, and default to "(link unavailable)" when Discord metadata is absent.

---

## 3. Working with the HTTP API

- Every command that mutates state eventually calls an async use case that can also be reached from the FastAPI routers under `/v1`. The bot and external clients therefore share validation and error semantics.
- Summaries collected through the adventure summary cog are persisted via the `POST /v1/summaries` endpoint, and follow-up edits use `PATCH /v1/summaries/{summaryId}` or `POST /v1/summaries/{summaryId}:updateLastEdited`.
- Quest lookup commands use the Mongo-backed repositories directly so moderators can answer roster questions without leaving Discord.
- Listing commands (e.g., `/summary list author:<id>`) are thin wrappers over the `ListSummaries` use case; the bot enforces the “one filter per request” rule that the API expects.
- Admin-only actions (guild sync, bulk refresh) rely on the `X-Admin-Token` header; the bot loads this token from the same `API_ADMIN_TOKEN` env var used by FastAPI.

---

## 4. Data & Telemetry Flow

1. **Questing:** Quest creation pushes data to Mongo via the quests repository, then posts a signup embed with a persistent `SignupView`. Button presses execute the `AddPlayerSignup` / `SelectPlayerSignup` use cases.
2. **Lookup intelligence:** `/quest-info` commands gather quest and summary context straight from Mongo, building Discord embeds with deep links and sibling recaps.
3. **Summaries:** The summary modal validates that at least one player and character are provided. The cog invokes `CreateSummary`, then updates quest/character counters so the API immediately reflects the new recap.
4. **Statistics:** Character telemetry commands call dedicated endpoints such as `POST /v1/characters/{id}:incrementSummariesWritten`, keeping metrics in sync across Discord and HTTP consumers.

---

## 5. Setup Checklist

### Step 1 – Prepare prerequisites

- Python 3.10–3.13, pip, and a Discord application/bot with the Message Content intent enabled.
- MongoDB 6.x running locally or through Docker (the repo ships with `docker-compose.dev.yml`).
- An OAuth2 bot invite URL with the `bot` and `applications.commands` scopes so slash commands register.

### Step 2 – Provide environment variables

Define the runtime configuration through environment variables (export them in your shell, inject them via CI, or supply an env file directly to Docker Compose). Minimum variables:

- `DISCORD_TOKEN` (or `BOT_TOKEN`): Discord bot token.
- `DISCORD_GUILD_ID` (or `GUILD_ID`): Primary guild to bootstrap. If omitted, the bot now checks Mongo `bot_settings` and finally falls back to the bundled test guild `1372610481860120638` for local/dev sessions.
- `MONGODB_URI`, `DB_NAME`: Mongo connection information (`mongodb://localhost:27017` works for local dev).
- `API_ADMIN_TOKEN`: Shared secret used by both the bot and the FastAPI admin routes.
- Optional overrides read at launch: `QUEST_CHANNEL_ID`, `SUMMARY_CHANNEL_ID`, `PLAYER_ROLE_ID`, `REFEREE_ROLE_ID`, `LOG_LEVEL`.

> **Local convenience:** If `DISCORD_TOKEN` isn’t exported, the bot will read it from a `.env` file at the repository root. Other identifiers (guild IDs, channel IDs, role IDs) are not loaded from `.env` to avoid stale configuration—provide them through environment variables or the `/bot-setup` flow instead. The quest lookup stack reuses whatever guild is stored in Mongo when `DISCORD_GUILD_ID` is blank; otherwise it defaults to the test guild noted above.

### Step 3 – Install dependencies

- Inside a virtual environment, install the project with `pip install -e .[dev]` to get the bot, API, and developer tooling.
- Alternatively, run `docker compose -f docker-compose.dev.yml build` to bake the API and bot images with the pinned dependencies.

### Step 4 – Start backing services

- Launch MongoDB locally or via `docker compose up mongo`.
- Run the HTTP API so the bot can call shared use cases: `uvicorn app.api.main:app --reload` (or rely on the `api` service in Docker compose).

### Step 5 – Run the bot worker

- Execute `python -m app.bot.main` from the project root, or start the `bot` service through Docker compose once Mongo and the API report healthy.
- On first launch, Discord may take a few minutes to propagate slash commands; they appear under the integration’s `/` menu once registered.

### Step 6 – Perform in-guild bootstrapping

- Use `/bot-setup` to persist the current quest/summary channels and default player/referee roles in Mongo. The quest lookup service reuses this configuration when scoping slash command registration.
- `/bot-settings` shows the stored configuration. Adjust with `/bot-set-*` commands or by re-running `/bot-setup` after creating new channels/roles.
- Seed initial domain data by either calling the `/v1/admin/**` endpoints with the `X-Admin-Token` header or by using `/user register` inside Discord.

### Step 7 – Verify everything is wired

- Hit `GET /healthz` on the FastAPI app to confirm the API is reachable.
- Trigger `/quest create`, `/quest-info quest`, and `/summary touch` in a test channel to ensure Mongo writes succeed and the lookup embeds populate correctly.
- Watch the bot logs for warnings about missing intents, permissions, or environment variables; address them before inviting players.

---

## 6. Next Steps

- **Analytics dashboards**: extend the bot with embeds that surface aggregated quest/summary stats.
- **Lookup caching**: add short-lived caching for `/quest-info` responses to reduce Mongo load during event nights.
- **Performance tuning**: Continue tightening message edit batching and explore Discord interactions bulk ACKs.
- **Web integration**: Use the same FastAPI endpoints for a lightweight web UI or data exports.
