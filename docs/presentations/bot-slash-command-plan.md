# Discord Bot Slash Command Troubleshooting Plan

## Scenario Overview

- **Date**: October 2, 2025
- **Reported Issues**:
  - `/bot-setup` failed to respond when invoked.
  - Only legacy hybrid commands (`/character-create`, `/player-*`, `/referee-*`) were visible; newer slash commands were missing.
- **Impact**: Admins could not reconfigure quest/summary channels or roles via slash commands, blocking onboarding for new guilds.

## Observed Symptoms

1. Slash command palette excluded `bot-setup`, `bot-settings`, and `bot-dm-player`.
2. Invoking `/bot-setup` silently failed with no ephemeral confirmation.
3. Docker logs lacked clear command-sync telemetry, making it difficult to confirm registration.

## Root Cause Hypothesis

- Application command sync occurred before `BotSetupCog` completed registration, leading to a stale command tree.
- Lack of explicit permission defaults allowed Discord’s command permission cache to disable admin commands for some guilds.
- Minimal instrumentation meant failures during configuration updates (Mongo writes, service application) went unreported.

## Remediation Steps Implemented

1. **Command Reliability**
   - Added ephemeral deferral, structured logging, and error handling across all admin slash commands.
   - Declared explicit default permissions (`administrator` / `manage_messages`) to surface commands to the correct roles.
2. **Registration Visibility**
   - Updated bot bootstrap to sync both guild and global command scopes and log the resulting command list.
3. **Operational Feedback**
   - Injected structured context (guild IDs, channel/role IDs) into log records for faster triage.
4. **Documentation**
   - Captured this troubleshooting plan for presentation and runbook purposes.

## Demo Flow (5–7 minutes)

1. **Setup** (60s)
   - Show `.env` keys (`DISCORD_GUILD_ID`, `DISCORD_TOKEN`).
   - Start bot container (`docker compose up bot`).
2. **Symptom Reproduction** (60s)
   - Open Discord slash menu before fix—highlight missing `bot-setup`.
   - Run `/bot-setup` to demonstrate lack of response (recorded screenshot).
3. **Fix Walkthrough** (3 min)
   - Showcase updated `BotSetupCog` deferrals/logging.
   - Highlight `_sync_app_commands()` logging output (guild + global command names).
   - Point to admin default permissions annotations.
4. **Verification** (1 min)
   - Redeploy bot, show log snippet confirming command sync.
   - Execute `/bot-settings` and `/bot-setup`; display ephemeral embeds.
5. **Next Steps & Q&A** (1–2 min)
   - Mention optional `/bot-sync` enhancement, automated tests, and Discord permission audits.

## Follow-Up Actions

- Add integration tests that mock `app_commands.CommandTree` to verify registration order.
- Create a runbook entry for performing a forced sync and inspecting permissions in Discord server settings.
- Monitor logs over the next week to ensure no further silent failures.
