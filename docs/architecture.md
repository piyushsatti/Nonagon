# Nonagon Architecture

> Discord-based quest automation, summaries, and participation tracking.

## 1. Purpose & Scope

Nonagon automates quest workflows (announce >> sign‑ups >> roster selection >> run >> summaries) and captures participation telemetry for insights. This document describes the architecture: runtime components, layering, data model, workflows, observability, deployment, and testing.

---

## 2. Architecture Overview

**Style:** Hexagonal (Ports & Adapters) with thin delivery edges (Discord + FastAPI).

* **Delivery (Controllers/Views):**
  * Discord Cogs handle commands & events. UI is built with `discord.ui.View` (buttons/selects/modals) and presenters that render embeds.
  * FastAPI routers expose the same use cases over HTTP for automation and external tooling.
* **Application Layer (Use Cases):** Stateless orchestrators (e.g., `CreateQuest`, `ListSummaries`, `SelectRoster`, `SubmitSummary`) that coordinate domain models and repositories.
* **Domain Layer (Models):** Pure Python dataclasses modeling `User` (+ roles & profiles), `Quest`, and `QuestSummary`. Contains invariants and state transitions.
* **Adapters (Infra):** MongoDB repositories (async via Motor), configuration, and integrations (Discord message IDs linkage). Optional background jobs for projections/analytics.

```text
[ Discord (slash cmds, buttons) ]      [ FastAPI HTTP API ]
            |                             |
      Controllers (Cogs)           Async Routers (FastAPI)
            \___________________________/
                    |
           Application (Use Cases)  ←→  Ports (Repo interfaces)
                    |
              Domain (Entities/Value Objects)
                    |
            Adapters (MongoDB repos, schedulers, config)
```

### Why this shape

* Domain rules remain framework‑agnostic.
* UI/Discord specifics live at the edge and can change without touching core logic.
* Repositories can be swapped (e.g., MongoDB → Postgres) with minimal surface changes.

---

## 3. Runtime Components

### 3.1 Discord Edge

* **Cogs (Controllers):** Register slash commands/listeners, validate permissions, **defer** within 3s, call use cases, then send/edit messages.
* **Views (UI):** `discord.ui.View` classes own component callbacks; presenters build embeds.
* **Rate limiting:** centralized wrapper handles retries/backoff when editing messages.

### 3.2 Application (Use Cases)

* One file per action; no framework imports. Examples:

  * `create_quest`, `announce_quest`, `apply_for_quest`, `select_roster`, `mark_completed`
  * `submit_summary` (DM or player), `list_summaries`
  * `record_message_activity`, `record_event_attendance`

### 3.3 Domain (Models)

* **User** with `roles[]` and optional `player`/`referee` profiles.
* **Quest** with lifecycle (`DRAFT → SIGNUP_OPEN → ROSTER_SELECTED → RUNNING → COMPLETED/CANCELLED`), sign‑ups, roster, waitlist, Discord linkage, telemetry.
* **QuestSummary** unified with discriminator `kind = player|dm`, visibility policy, and indexed `players[]`/`characters[]` collections for filter-based queries.

### 3.4 HTTP API Gateway

* FastAPI hosts `/v1/**` endpoints that wrap the same use cases consumed by Discord controllers.
* Dependency wiring (`app/api/deps.py`) shares singleton Mongo repositories and ID services across requests.
* Routers are fully async, returning Pydantic response models (`Quest`, `Summary`, etc.) and surfacing domain errors as HTTP 4xx.
* Summary endpoints now include a dedicated `ListSummaries` use case that supports author/character/player filters with consistent pagination semantics.

### 3.5 Adapters (Infra)

* **MongoDB repositories:** implement ports for `UsersRepo`, `QuestsRepo`, `SummariesRepo`.
* **Config:** environment‑driven (`.env` in dev); no secrets in code.
* **Background jobs (optional):** projectors to compute analytics/materialized views.

---

## 4. Key Workflows

### 4.1 Quest Announcement & Sign‑ups

1. `/quest_create` defers, calls `create_quest()` → returns `Quest` in `DRAFT`.
2. Controller posts announcement with `SignupView` and stores `guild_id/channel_id/message_id/thread_id` on the quest.
3. Calls `announce_quest()` → status becomes `SIGNUP_OPEN`.
4. Players click **Sign up** → `apply_for_quest()` adds `Signup` entries; presenter updates counts.

### 4.2 Roster Selection

1. DM triggers **Select Roster** (modal/select) → `select_roster()` validates ownership & capacity, promotes selected to `roster`, others to `waitlist`.
2. Controller edits the sign‑up message embed and optionally DMs selected players.

### 4.3 Run & Complete

1. When session starts, controller calls `quest.mark_running()` via use case, later `mark_completed()` which sets `summary_needed=True`.
2. Players/DM submit summaries via buttons/modals → `submit_summary(kind=player|dm)` links to quest and updates stats.

---

## 5. Data Model (High‑level)

### 5.1 Core Entities

* **User**

  * `roles: [member|player|referee|admin]`
  * `player?: PlayerProfile` (active/retired characters, counters)
  * `referee?: RefereeProfile` (quests DMed, regions, collaborations)
  * Engagement telemetry (messages, voice, events).

* **Quest**

  * Identity, meta (`name`, `description`, `tags`, `category`, `region`)
  * Scheduling (`scheduled_at`, `duration_hours`, `timezone`)
  * Capacity (`max_players`, `min_players`, optional level range)
  * Discord linkage (`guild_id`, `channel_id`, `signup_message_id`, `thread_id`)
  * Lifecycle timestamps; `signups`, `roster`, `waitlist`
  * Rewards (`xp_reward`, `gp_reward`), `summary_ids`, `attendees`

* **QuestSummary** (unified)

  * `summary_id`, `quest_id`, `author_user_id`, `kind`, `summary_text`, `posted_at`
  * Visibility (`is_private`, `audience_roles`)

### 5.2 Modeling Notes

* Prefer **IDs** over object references in maps to avoid cycles; easy serialization.
* Embed small, tightly‑coupled subdocs (profiles, sign‑ups). Split to collections when they grow or need independent indexing/lifecycle.
* Persist entity IDs as `{prefix, number}` pairs so Mongo can index both the human-readable form and the sortable numeric component (used by summary listing filters).

---

## 6. Security & Permissions

* **RBAC:** roles derive from `User.roles`. Controllers enforce: only `REFEREE` may create/select, only `PLAYER` may apply, `ADMIN/REFEREE` may read DM summaries.
* **Visibility:** DM summaries default private; player summaries public unless overridden.
* **Audit:** record `created_by`, `last_updated_by` on quests; append‑only events for sensitive changes (optional).

---

## 7. Reliability & Performance

* **Interaction timing:** always reply or **defer** within 3 seconds; then edit/follow‑up.
* **Rate limits:** centralize message edits with automatic retry/backoff; deduplicate identical edits; prefer bulk updates.
* **Idempotency:** use deterministic keys (e.g., signup composite `(quest_id, user_id, character_id)`) to prevent double‑apply.
* **Pagination & caching:** paginate lists (quests, summaries); cache stable lookups (e.g., user profiles) in memory with TTL.
* **HTTP throughput:** FastAPI handlers are fully async and share a single Motor client; keep responses bounded with `limit`/`offset` and stream long-running work to background tasks when needed.

---

## 8. Observability

* **Structured logging** with request/interaction IDs.
* **Metrics** (per command latency, error rate, rate‑limit hits, sign‑up conversions).
* **Tracing**: optional OpenTelemetry (spans around use cases and Discord/DB adapters). Export to console in dev; OTLP in prod.

---

## 9. Deployment & Config

* **Packaging:** `src/` layout; every package has `__init__.py`.
* **Configuration:** env vars (e.g., `MONGODB_URI`, `BOT_TOKEN`, `LOG_LEVEL`). Commit only `.env.example`.
* **Container:** Dockerfile at repo root; `.dockerignore` excludes venv, tests, docs, git.
* **CI:** GitHub Actions runs `ruff`/`pytest` and optional image build.

---

## 10. Testing Strategy

* **Unit:** domain models (state transitions), use cases (with in‑memory repos/UoW).
* **Component:** adapters against a real MongoDB (or Testcontainers/mongomock for fast checks).
* **E2E (bot):** spin up a test guild or use a stub transport; verify commands and views.

---

## 11. Extensibility

* Add **analytics projections** (e.g., “quests per referee”, “time‑to‑fill”).
* New integrations (web dashboard, notifications) arrive as new adapters/ports.
* Feature flags for experimental flows.

---

## 12. Assumptions

* MongoDB Atlas is the primary store; scale via indexes and capped document sizes.
* Single bot shard initially; can shard later if guild count grows.
* Delivery edges are Discord UI and the FastAPI HTTP service; both exercise the same use cases.

---

## 13. Appendix: Example Ports

```python
class UsersRepo(Protocol):
    async def get(self, user_id: str) -> User: ...
    async def upsert(self, user: User) -> None: ...

class QuestsRepo(Protocol):
    async def get(self, quest_id: str) -> Quest: ...
    async def upsert(self, quest: Quest) -> None: ...

class SummariesRepo(Protocol):
    async def get(self, summary_id: str) -> QuestSummary: ...
    async def upsert(self, summary: QuestSummary) -> None: ...
  async def delete(self, summary_id: str) -> None: ...
  async def list(self, *, limit: int, offset: int) -> list[QuestSummary]: ...
  async def list_by_author(self, author_id: str, *, limit: int, offset: int) -> list[QuestSummary]: ...
  async def list_by_character(self, character_id: str, *, limit: int, offset: int) -> list[QuestSummary]: ...
  async def list_by_player(self, player_id: str, *, limit: int, offset: int) -> list[QuestSummary]: ...
```

---

## 14. Verification Checklist

* [ ] All commands **defer** within 3s when work > 3s
* [ ] UI actions live in `discord.ui.View`; controllers are thin
* [ ] Use cases free of framework imports
* [ ] MongoDB: embed small/tight data; reference when large/independent
* [ ] DM summaries private by default; RBAC enforced at controller
* [ ] Centralized rate‑limit handling for edits
* [ ] Logs/metrics enabled; traces optional via OpenTelemetry
* [ ] CI runs lint + tests; Docker ignores dev files
