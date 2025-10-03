# Nonagon

> Discord-native quest automation, analytics, and storytelling for tabletop communities.

Nonagon is a full-stack platform that keeps a living tabletop RPG community humming. It pairs a battle-tested Discord bot with a FastAPI service and Mongo-backed data layer to automate quest lifecycles, orchestrate player sign-ups, capture adventure summaries, and surface participation insights. The project demonstrates end-to-end product thinking—from UX in slash commands to resilient infrastructure and documentation—and is actively shipping features for a live server.

---

## 🔍 TL;DR / Why it matters

- **Automates the hard parts of community ops** so referees can focus on storytelling: quest announcements, roster selection, adventure recap tracking, and role management.
- **Backed by a hexagonal architecture** that keeps domain rules independent of Discord or HTTP frameworks, enabling rapid iteration and future integrations (web, analytics dashboards).
- **Production-ready craftsmanship**: structured logging, CI/CD via Docker + GitHub Actions, deterministic ID services, environment-driven configuration, and a growing test suite.

---

## ✨ Feature Highlights

| Pillar | What it delivers |
| --- | --- |
| **Quest Automation** | Discord ingestion parses quest announcements, normalizes metadata, persists records, and exposes `/quest-info quest` lookups with rich embeds. |
| **Summary Intelligence** | Adventure summary ingestion maps Markdown posts (player + DM) into structured documents, links them to quests, and exposes `/quest-info summary` retrieval. |
| **Admin & Operations Toolkit** | Slash commands manage player/referee roles, bootstrap guild configuration from Mongo, and log every action with contextual telemetry. |
| **FastAPI Gateway** | REST `/v1/**` endpoints wrap the same use cases for external tooling—perfect for dashboards, Postman collections, or web front-ends. |
| **Reliable Startup & Sync** | Bot bootstrap discovers guild IDs from Mongo (with a default test guild `1372610481860120638`), ensures command sync completes, and logs results for auditability. |
| **Documentation-first Delivery** | Architecture, API, bot operations, and PRDs live in `docs/`, making knowledge transfer painless for collaborators or recruiters. |

> See `docs/BOT.md` and `docs/API.md` for deep-dives into command UX, payloads, and contract details.

---

## 🏗 Architecture at a Glance

```text
[ Discord Slash Commands ]     [ FastAPI /v1 REST ]
            |                             |
       Cogs & Views (UI)           Routers & Schemas
            \____________________________/
                        |
                Application Use Cases
                        |
                  Domain Models/IDs
                        |
             MongoDB Repositories & Services
                        |
             Motor (Async Mongo) + Infrastructure
```

- **Style**: Hexagonal (Ports & Adapters) with thin delivery edges for Discord and HTTP.
- **Key Services**: `QuestIngestionService`, `AdventureSummaryIngestionService`, `QuestLookupService`, and use cases like `CreateQuest`, `AddPlayerSignup`, `ListSummaries`.
- **Observability**: Structured logging via `GuildLoggingService`, Mongo startup health checks, and failure repositories for ingestion triage.

📄 Detailed write-up: `docs/architecture.md`

---

## 🧰 Tech Stack & Tooling

- **Language & Runtime**: Python 3.13, asyncio-first.
- **Discord Bot Framework**: [`discord.py`](https://discordpy.readthedocs.io/)
- **API Framework**: [FastAPI](https://fastapi.tiangolo.com/) + Pydantic models.
- **Database**: MongoDB Atlas via async Motor client; sequential ID service for deterministic identifiers.
- **Build & Packaging**: `pyproject.toml` (setuptools), editable installs for dev, Dockerfiles for API and bot workloads.
- **CI/CD**: GitHub Actions (lint + pytest), Docker Compose for reproducible local stacks.
- **Testing**: Pytest suites under `tests/` covering API endpoints, bot cogs, ingestion pipelines, and domain models.
- **Documentation**: Markdown knowledge base under `docs/` (PRD, architecture, API, bot runbooks, presentations).

---

## 📂 Repository Tour

```text
src/
  app/
    bot/        # Discord client, cogs, ingestion & services
    api/        # FastAPI routers, schemas, dependency wiring
    domain/     # Entities, value objects, and use-case orchestrators
    infra/      # Mongo adapters, settings, lifecycle hooks, ID service
  ...
docs/
  architecture.md
  API.md
  BOT.md
  PRD.md
Dockerfile.api / Dockerfile.bot
pytest.ini
pyproject.toml
```

---

## 🚀 Getting Started

### 1. Clone & install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2. Configure environment

Create a `.env` (or export directly) with the essentials:

```ini
DISCORD_TOKEN=xxxx
MONGODB_URI=mongodb+srv://...
API_ADMIN_TOKEN=supersecret
DISCORD_DEFAULT_TEST_GUILD_ID=1372610481860120638
QUEST_CHANNEL_ID=123456789012345678
SUMMARY_CHANNEL_ID=123456789012345679
REFEREE_ROLE_ID=123456789012345680
PLAYER_ROLE_ID=123456789012345681
```

Additional knobs like `DB_NAME`, `LOG_LEVEL`, or TLS overrides live in `app/infra/settings.py`.

### 3. Run everything with Docker Compose

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Spins up the FastAPI service and Discord bot containers.
- Performs MongoDB health checks on startup—misconfiguration fails fast with clear logs.

### 4. Run locally without Docker

```bash
chmod +x scripts/run-local.sh
./scripts/run-local.sh          # boots API (background) + bot (foreground)
./scripts/run-local.sh api      # FastAPI only
./scripts/run-local.sh bot      # Discord bot only
```

The helper script auto-loads `.env.local` or `.env` unless overridden with `ENV_FILE=/path/to/file`.

---

## ✅ Quality Gates & Testing

```bash
python -m pytest
```

- Bot cog tests: `tests/discord_bot/**`
- API contract tests: `tests/api/**`
- Domain model tests: `tests/domain/**`

CI mirrors the pytest suite and can be extended with linters or type checking (e.g., Ruff, mypy) as needed.

---

## 📈 Observability & Ops Notes

- Command execution logs include guild/channel/actor context via `GuildLoggingService`.
- Ingestion failures (parse/validation) are persisted to Mongo so moderators can remediate data issues quickly.
- Slash command registration is scoped per guild with fallback to `DISCORD_DEFAULT_TEST_GUILD_ID` to avoid Discord-wide sync delays.
- API endpoints require an `X-Admin-Token` header, enforcing lightweight RBAC for administrative flows.

---

## 🗺 Roadmap & Future Epics

Tracked in `docs/PRD.md`:

- 🟡 **Epic 1 – Data Tracking**: message and quest participation analytics for admins.
- 🔵 **Epic 4 – Frontend for Quests**: public website leveraging the `/v1` API.
- 🆕 Future seeds: analytics dashboards, player portal UX refresh, live ops tooling (forced sync, incident recovery).

---

## 📚 Further Reading & Decks

- **Architecture**: `docs/architecture.md`
- **API Contracts**: `docs/API.md` (summaries, quests, users, admin routes)
- **Discord Bot Runbook**: `docs/BOT.md` (command catalogue, troubleshooting)
- **Slash Command Troubleshooting Plan**: `docs/presentations/bot-slash-command-plan.md`
- **Product Requirements**: `docs/PRD.md`

Screenshots & demo assets live under `docs/media/`.

---

## 👋 About the Author

Crafted by **Piyush Satti** — building tools that keep creative communities thriving. I lead projects end-to-end: product discovery, architecture, gameplay UX, and reliable deployments. Reach me at [piyushsatti@gmail.com](mailto:piyushsatti@gmail.com) or on GitHub [@piyushsatti](https://github.com/piyushsatti) for collaboration or opportunities.
