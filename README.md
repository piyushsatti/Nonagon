# Big Brother
- Designed and deployed an end-to-end community platform for D&D players—combining a modular Discord bot, a Flask web dashboard, and REST APIs to automate quest scheduling, and player analytics. 
- Implemented quest lifecycle tracking, character XP/GP calculators, and real-time churn alerts; persisted data in MongoDB (player, character, quest, and engagement collections) and served analytics through FastAPI endpoints.
- Containerised the bot & API with Docker and automated CI/CD via GitHub Actions, delivering 200 ms end-to-end latency for typical Discord commands. Achieve 80% pytest coverage

# Tools Used
- [Discord.py](https://discordpy.readthedocs.io/en/stable/)
- [Redis](https://redis.io/)
- [MongoDB](https://www.mongodb.com/docs/mongodb-shell/)

# Environment Configuration
- `BOT_TOKEN` – Discord bot token.
- `BOT_CLIENT_ID` – Discord application client ID (used by `/invite`).
- `MONGO_URI` – MongoDB connection string (defaults to `mongodb://localhost:27017`).
- `DEMO_RESET_ENABLED` – set to `true` to allow `/demo_reset` and CLI resets.
- `DEMO_LOG_CHANNEL_ID` – optional channel id for posting demo activity logs.

# Testing
- Domain: `PYTHONPATH=src .venv/bin/pytest tests/domain -q`
- API sanity: `PYTHONPATH=src .venv/bin/pytest tests/api -q`
- Bot helpers: `PYTHONPATH=src .venv/bin/pytest tests/bot -q`

# Discord Bot Development Milestones

## Milestone 0 — Setup & Scaffolding (1–2 days)
- [x] Register bot in Discord Developer Portal  
- [x] Invite bot to test server with correct perms  
- [x] Stack: **Python + discord.py**
- [ ] Create base bot project (command prefix, cogs / modular folders)  
- [ ] Connect to lightweight DB (SQLite / JSON)  
> **Success:** `!ping` and `!help` respond; bot logs in without errors.

---

## Milestone 1 — Quest Lifecycle Tracking (3–5 days)
- [ ] `!createquest <name> <datetime> <dm>` → save quest  
- [ ] `!joinquest <quest_id> <character>` → log participation  
- [ ] `!startquest <quest_id>` → confirm attendees  
- [ ] `!endquest <quest_id> <xp> <gp>` → store rewards  
- [ ] Persist character-quest linkage  
> **Success:** Quests + attendance correctly stored.

### Slash Commands (beta)
- `/createquest` – announce a new quest with start time, duration, and image.
- `/joinquest` / `/leavequest` – manage quest signups using registered characters.
- `/startquest` / `/endquest` – transition quests through their lifecycle.
- `/character_add` / `/character_list` – create and review character profiles.
- `/stats` – view personal engagement metrics.
- `/leaderboard` – show top users by messages, reactions, or voice time.
- Quest announcements ship with persistent **Join**/**Leave** buttons; players can submit their character IDs via a modal without memorising command syntax.
- Ending a quest automatically DM’s signed-up players with a reminder to file their summaries.
- `/nudges enable|disable` – opt into or out of DM reminders (respects personal preference).

### Demo Ops Toolkit
- `/demo_about` (ephemeral) – share a quick tour of the demo capabilities.
- `/demo_reset` (admins) – wipe and rehydrate demo data via MongoDB cache bootstrap.
- **Web Dashboard**: `GET /demo` (served by FastAPI) to view live leaderboards and upcoming quests.
- **API Endpoints**:
  - `GET /demo/leaderboard?metric=messages` – JSON leaderboard across guilds.
  - `GET /demo/quests` – upcoming quest feed.
- `scripts/reset_demo.py --guild-id <id>` – CLI helper mirroring `/demo_reset`.

---

## Milestone 2 — Character & Player Profiles (3–4 days)
- [ ] `!character add/view/delete` commands  
- [ ] Auto-update XP / level on quest end  
- [ ] `!myprofile` → show quests, characters, XP, last played  
- [ ] Log historical level-up events  
> **Success:** Any player’s progression can be queried.

---

## Milestone 3 — Engagement & Messaging Stats (3–4 days)
- [ ] Count messages per user by channel category  
- [ ] Track reactions (given & received)  
- [ ] Update **last-active** date on any event  
- [ ] Log quests-per-DM metric  
> **Success:** `!stats` returns engagement summary.

---

## Milestone 4 — Admin Tools & Dashboards (4–6 days)
- [ ] `!leaderboard quests|messages`  
- [ ] `!churncheck` → list users inactive >30 days  
- [ ] `!dmstats` → quests run, unique players  
- [ ] `!questhistory @player` timeline  
> **Success:** Moderators can view health metrics in-chat.

---

## Milestone 5 — Automation & Feedback Loops (5–7 days)
- [ ] Auto post **level-up** announcements  
- [ ] DM inactivity nudges (3-week threshold)  
- [ ] `!milestonecheck` → next achievements  
- [ ] Post-session reminder for adventure summary bonus  
> **Success:** Bot drives engagement with automated nudges.

---

## Milestone 6 — Web Sync / Export (Optional 7–10 days)
- [ ] `!exportstats` → JSON / CSV dump  
- [ ] REST endpoint or simple Flask dashboard  
- [ ] Optional OAuth login for player self-stats  
> **Success:** Data visible outside Discord.

---


# Database
Use MongoDB Atlas for persistence.

- Set `ATLAS_URI` in your `.env` to the Atlas connection string (e.g. `mongodb+srv://...`).
- API reads `MONGODB_URI` (wired from `ATLAS_URI` in docker-compose) and uses Motor/PyMongo default TLS.
- Bot reads `MONGO_URI` (wired from `ATLAS_URI`). No local Mongo container is used.

Data model (per guild database):
- Each guild maps to a database named by its guild ID.
- Collections: `users`, `characters`, `quests`, `summaries`, and `counters` for ID sequences.




# To-Do
- [ ] Redo documentation
- [ ] Make soft architecture for porject
  - [ ] Redis vs local cache
- [ ] 
