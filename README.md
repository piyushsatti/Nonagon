# Big Brother

- Designed and deployed an end-to-end community platform for D&D players—combining a modular Discord bot, a Flask web dashboard, and REST APIs to automate quest scheduling and analytics.
- Implemented quest lifecycle tracking, character XP/GP calculators, and real-time churn alerts; persisted data in MongoDB and served analytics through FastAPI endpoints.
- Containerised the bot and API with Docker, automated CI/CD via GitHub Actions, and achieved 80% pytest coverage.

## Tools Used

- [Discord.py](https://discordpy.readthedocs.io/en/stable/)
- [Redis](https://redis.io/)
- [MongoDB](https://www.mongodb.com/docs/mongodb-shell/)

## Configuration

Set the following environment variables before starting the bot:

- `DISCORD_TOKEN` – bot token from the Discord developer portal.
- `QUEST_CHANNEL_ID` – channel ID for quest announcements to ingest.
- `SUMMARY_CHANNEL_ID` – channel ID where adventure summaries are posted.
- `PLAYER_ROLE_ID` – Discord role ID granted to players allowed to join quests and create characters.
- `REFEREE_ROLE_ID` – Discord role ID used to identify referees/DMs.
- `MONGODB_URI` – connection string for the MongoDB deployment.

### Discord bot features

- **Startup user sync**: when the bot comes online it provisions a domain `User` record for every non-bot guild member automatically.
- **Role management (admin only)**
  - `/player-grant @member` / `/player-revoke @member` – keep player access aligned between Discord roles and the domain model.
  - `/referee-grant @member` / `/referee-revoke @member` – manage referee privileges and ensure the Discord roles reflect the change.
- **Character creation (players)**
  - `/character-create` – lets any member with the player role register a new character (no naming restrictions). The command replies with an embed summarising the new record and useful resource links.

All commands return rich embeds with success/error details so moderators can audit changes directly in Discord.

## Discord Bot Development Milestones

### Milestone 0 — Setup & Scaffolding (1–2 days)

- [x] Register bot in Discord Developer Portal
- [x] Invite bot to test server with correct perms
- [x] Stack: **Python + discord.py**
- [ ] Create base bot project (command prefix, cogs / modular folders)
- [ ] Connect to lightweight DB (SQLite / JSON)

> **Success:** `!ping` and `!help` respond; bot logs in without errors.

---

### Milestone 1 — Quest Lifecycle Tracking (3–5 days)

- [ ] `!createquest <name> <datetime> <dm>` → save quest
- [ ] `!joinquest <quest_id> <character>` → log participation
- [ ] `!startquest <quest_id>` → confirm attendees
- [ ] `!endquest <quest_id> <xp> <gp>` → store rewards
- [ ] Persist character-quest linkage

> **Success:** Quests + attendance correctly stored.

---

### Milestone 2 — Character & Player Profiles (3–4 days)

- [ ] `!character add/view/delete` commands
- [ ] Auto-update XP / level on quest end
- [ ] `!myprofile` → show quests, characters, XP, last played
- [ ] Log historical level-up events

> **Success:** Any player’s progression can be queried.

---

### Milestone 3 — Engagement & Messaging Stats (3–4 days)

- [ ] Count messages per user by channel category
- [ ] Track reactions (given & received)
- [ ] Update **last-active** date on any event
- [ ] Log quests-per-DM metric

> **Success:** `!stats` returns engagement summary.

---

### Milestone 4 — Admin Tools & Dashboards (4–6 days)

- [ ] `!leaderboard quests|messages`
- [ ] `!churncheck` → list users inactive >30 days
- [ ] `!dmstats` → quests run, unique players
- [ ] `!questhistory @player` timeline

> **Success:** Moderators can view health metrics in-chat.

---

### Milestone 5 — Automation & Feedback Loops (5–7 days)

- [ ] Auto post **level-up** announcements
- [ ] DM inactivity nudges (3-week threshold)
- [ ] `!milestonecheck` → next achievements
- [ ] Post-session reminder for adventure summary bonus

> **Success:** Bot drives engagement with automated nudges.

---

### Milestone 6 — Web Sync / Export (Optional 7–10 days)

- [ ] `!exportstats` → JSON / CSV dump
- [ ] REST endpoint or simple Flask dashboard
- [ ] Optional OAuth login for player self-stats

> **Success:** Data visible outside Discord.

---

## Database

The project uses MongoDB. Each user, player, referee, and character is stored as a document; collections are scoped per guild.

## To-Do

- [ ] Redo documentation
- [ ] Make soft architecture for project
  - [ ] Redis vs local cache
- [ ] *(add more items as needed)*
