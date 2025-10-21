# Nonagon Documentation

Welcome to **Nonagon**. A Discord based platform for quest automation, tracking, and community storytelling.

**What is Nonagon?**
A lightweight system that helps players sign up for quests, referees run sessions, and adventure summaries get tracked - all with rich insights.

---

## Quick Start

| Section | Description |
|--------|-------------|
| [Getting Started](../README.md) | Install, configure, and run the bot locally |
| [Architecture](architecture.md) | Layered structure, design choices, and intents |
| [PRD & Use Cases](PRD.md) | In-depth breakdown of features and user stories |
| [Discord Commands](discord.md) | Slash commands: inputs, permissions, outputs |
| [API Reference](API.md) | REST endpoints and schemas |
| [Moderation SOP](moderation.md) | Logging expectations and review checklist |

---

## Project Status

**Experimental (multi-guild):**

- Per-guild data model and indexes (`guild_id` everywhere)
- Guild-scoped Users API under `/v1/guilds/{guild_id}/users`
- Migration script to backfill `guild_id` on legacy docs
- Diagnostics and demo utilities updated for guild scoping
