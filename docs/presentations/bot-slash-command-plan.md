# Discord Bot Slash Command Troubleshooting Plan

## Scenario Overview

- **Date**: October 3, 2025 (post-remediation)
- **Reported Issues**:
  - `/bot-setup` failed to respond when invoked.
  - Only legacy hybrid commands (`/character-create`, `/player-*`, `/referee-*`) were visible; newer slash commands were missing.
- **Impact**: Admins could not reconfigure quest/summary channels or roles via slash commands, blocking onboarding for new guilds.

## Current Status

- Admin commands (`/bot-setup`, `/bot-settings`, `/bot-dm-player`) and the new `quest-info` command group register in each configured guild.
- Bootstrap hydrates guild IDs from Mongo (`BotSettingsRepository.list_guild_ids()`), falling back to `DISCORD_DEFAULT_TEST_GUILD_ID=1372610481860120638`.
- Command sync emits structured logs including guild counts and command names, raising on drift and surfacing quickly in `logs/bot.log`.
- Regression test coverage (`tests/discord_bot/test_general_cog.py`) and manual smoke checks on the test guild validate embeds and responses.

## Observed Symptoms

1. Slash command palette excluded `bot-setup`, `bot-settings`, and `bot-dm-player`.
2. Invoking `/bot-setup` silently failed with no ephemeral confirmation.
3. Docker logs lacked clear command-sync telemetry, making it difficult to confirm registration.
4. The `quest-info` command group never appeared, so quest lookups could not be initiated via slash commands.

## Root Cause Hypothesis

- Application command sync occurred before `BotSetupCog` and the general cog finished registering commands, leading to a stale command tree.
- Lack of explicit permission defaults allowed Discord’s command permission cache to disable admin commands for some guilds.
- Bootstrap relied solely on `DISCORD_GUILD_ID`, so guild membership drifted from the persisted `bot_settings` collection.
- Minimal instrumentation meant failures during configuration updates (Mongo writes, service application) went unreported.

## Remediation Steps Implemented

1. **Command Reliability**
   - Added ephemeral deferral, structured logging, and error handling across all admin slash commands.
   - Declared explicit default permissions (`administrator` / `manage_messages`) to surface commands to the correct roles.
   - Registered the `quest-info` command group during cog setup to close startup race windows.
2. **Registration Visibility**
   - Updated bot bootstrap to sync both guild and global command scopes and log the resulting command list.
   - Published command sync summaries (guild IDs, command totals) at INFO level for quick drift detection.
3. **Bootstrap Resilience**
   - Hydrate guild IDs via Mongo `BotSettingsRepository.list_guild_ids()`; fall back to `DISCORD_DEFAULT_TEST_GUILD_ID` when none are configured.
   - Recorded the default test guild (`1372610481860120638`) in docker compose defaults and onboarding docs.
4. **Operational Feedback**
   - Injected structured context (guild IDs, channel/role IDs) into log records for faster triage.
   - Added failure counters and alert-worthy error logging around Mongo configuration writes.
5. **Documentation**
   - Captured this troubleshooting plan for presentation and runbook purposes.
   - Updated API and bot guides with quest lookup flows, guild bootstrap logic, and troubleshooting tips.

## Demo Flow (5–7 minutes)

1. **Setup** (60s)
   - Show exported env vars (`DISCORD_TOKEN`, `MONGO_URI`) plus optional overrides (`DISCORD_DEFAULT_TEST_GUILD_ID`).
   - Start bot container (`docker compose up bot`).
2. **Symptom Reproduction** (60s)
   - Open Discord slash menu before fix—highlight missing `bot-setup` and `quest-info` entries.
   - Run `/bot-setup` to demonstrate lack of response (recorded screenshot).
3. **Fix Walkthrough** (3 min)
   - Showcase updated `BotSetupCog` deferrals/logging and general cog registration of `quest-info` commands.
   - Highlight `_sync_app_commands()` logging output (guild + global command names) and Mongo guild discovery fallback sequence.
   - Point to admin default permissions annotations and structured logging payloads.
4. **Verification** (1–2 min)
   - Redeploy bot, show log snippet confirming command sync counts and guild list.
   - Execute `/bot-settings`, `/bot-setup`, and `/quest-info summary`; display ephemeral embeds.
5. **Next Steps & Q&A** (1–2 min)
   - Mention optional `/bot-sync` enhancement, expanded automated tests, Discord permission audits, and quest lookup telemetry.

## Follow-Up Actions

- Add integration tests that mock `app_commands.CommandTree` to verify registration order and Mongo-backed guild discovery.
- Create a runbook entry for performing a forced sync, validating permissions defaults, and inspecting Discord server settings.
- Monitor logs over the next week to ensure no further silent failures and capture quest-info usage telemetry.
- Add smoke tests for quest lookup success/failure paths (missing quest ID, unpublished summary).
