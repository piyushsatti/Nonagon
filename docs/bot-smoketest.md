# Bot Smoke Test (Test Discord Server)

## Prerequisites
- Bot is invited to your test server with scopes `bot applications.commands` and permissions: Send Messages, Read Message History, Use Slash Commands.
- MongoDB reachable per `.env`: set `MONGO_URI` and `DB_NAME`.
- `BOT_TOKEN` is set in `.env` and not a placeholder.
- Docker and Docker Compose installed.

## Build and Run (bot only)
- `docker compose build bot`
- `docker compose up -d bot`
- Tail logs and wait for startup:
  - `docker compose logs -f bot`
  - Expect lines like:
    - `Logged in as ... (ID: ...)`
    - `Loaded cogs: ...`
    - `Slash commands: ...`

## First-Time Command Sync
- Slash commands can take up to 1–3 minutes to appear the first time.
- If they don’t appear, restart once: `docker compose restart bot`.

## Basic Smoke Checks (in Discord)
- Use `/help` — expect quickstart/links response (HelpCommandsCog).
- Use `/extensions` — should list loaded extensions (ExtensionManagerCog).
- Try a simple flow to touch DB + logic:
  - Create something minimal (e.g., `/quest_create` with valid inputs).
  - Verify via `/quest_list` that it persists.
- Listener sanity (optional): send a normal message in a channel the bot can access and watch logs for ListnerCog events.

## Fast Dev Loop
- Compose mounts your code: `./src:/app/src:ro`.
- Edit code under `src/` and restart the bot to pick up changes:
  - `docker compose restart bot`
- Rebuild only if dependencies or `pyproject.toml` changed:
  - `docker compose build bot`

## Troubleshooting
- Bot offline or commands missing:
  - Confirm the bot is in the server and online.
  - Ensure invite used `applications.commands` scope.
  - Wait up to a few minutes; then `docker compose restart bot`.
- Auth failures:
  - Check `BOT_TOKEN` in `.env` is correct and non-empty.
  - Logs: `docker compose logs --tail=200 bot`.
- Mongo errors:
  - Verify `MONGO_URI` is correct and reachable from the container.
- Cog load failures:
  - Logs will include `Error loading extension ...` with a traceback; fix and restart.

## Cleanup
- Stop services: `docker compose down`
- Clear logs: `rm -f logs/bot.log`
