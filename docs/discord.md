# Discord Slash Commands

This page documents the bot’s slash commands, their inputs, permission requirements, expected outputs, and logging behavior.

## Extension Manager
- `load`
  - Inputs: `extension: str`
  - Permissions: none enforced
  - Output: ephemeral confirmation or error
  - Logging: exceptions logged; demo log posted in-guild
- `unload`
  - Inputs: `extension: str`
  - Permissions: none enforced
  - Output: ephemeral confirmation or error
  - Logging: exceptions logged; demo log posted in-guild
- `reload`
  - Inputs: `extension: str`
  - Permissions: none enforced
  - Output: ephemeral confirmation or error
  - Logging: exceptions logged; demo log posted in-guild
- `extensions`
  - Inputs: none
  - Permissions: none enforced
  - Output: ephemeral list of loaded extensions
  - Logging: info log lists extensions

## Quest Lifecycle

> **ID format:** All quest, character, and summary identifiers use postal-style values such as `QUESH3X1T7` or `CHARB2F4D9`. Slash commands expect the full ID string (including prefix).
> Demo logs for quest actions surface these postal IDs directly so moderators can cross-check announcements.

- `/quest create`
  - Flow: DM wizard prompts for title, description, start time, duration, and optional cover image. Preview embed updates after each step.
  - Permissions: must run in a guild; caller must be REFEREE or allowed staff.
  - Output: quest stored as `DRAFT`, DM summary with preview and `/quest announce` reminder, ephemeral confirmation.
  - Logging: demo log once the quest is announced.
- `/quest edit`
  - Flow: DM wizard updates existing quest fields with live preview after each change.
  - Permissions: referee or allowed staff.
  - Output: quest updated; existing announcement embed refreshed if present; DM summary sent.
  - Logging: warnings on failures; demo log for downstream actions (accept/decline, etc.).
- `/quest announce`
  - Inputs: `quest: str` (Quest ID), `time?: str` (ISO string, `<t:epoch>`, or `YYYY-MM-DD HH:MM` in UTC)
  - Permissions: referee or allowed staff.
  - Output: immediate announcement (pings configured quest role) or scheduled via `announce_at`.
  - Logging: demo log; warnings on configuration errors.
- `/quest nudge`
  - Inputs: `quest: str`
  - Permissions: quest referee; enforces 48h cooldown.
  - Output: posts “Quest Nudge” embed in announcement channel, optionally mentions quest ping role.
  - Logging: demo log; cooldown guidance returned ephemerally.
- `/quest cancel`
  - Inputs: `quest: str`
  - Permissions: referee or allowed staff.
  - Output: quest marked `CANCELLED`, signup view removed, announcement embed updated.
  - Logging: demo log; errors logged.
- `/quest players`
  - Inputs: `quest: str`
  - Permissions: referee or allowed staff.
  - Output: ephemeral embed listing selected and pending players with mentions + character IDs (quest must be `COMPLETED`).
- `/joinquest`
  - Inputs: `quest_id: str` (autocomplete), `character_id: str` (autocomplete)
  - Permissions: must run in a guild; user must be PLAYER and own the character
  - Output: ephemeral confirmation; channel message notes the join
  - Logging: demo log; debug logs on fetch failures
- `/leavequest`
  - Inputs: `quest_id: str`
  - Permissions: must run in a guild; user must be signed up
  - Output: ephemeral confirmation; channel message notes the leave
  - Logging: demo log; debug logs on fetch failures
- `startquest`
  - Inputs: `quest_id: str` (e.g., `QUESH3X1T7`)
  - Permissions: must run in a guild; only the quest referee may start
  - Output: ephemeral confirmation; signup view removed; channel notice
  - Logging: info log; demo log
- `endquest`
  - Inputs: `quest_id: str` (e.g., `QUESH3X1T7`)
  - Permissions: must run in a guild; only the quest referee may end
  - Output: ephemeral confirmation; channel notice encouraging summaries
  - Logging: info log; demo log

## Quest Signup Buttons

- `Request to Join`
  - Visible to players; opens the character selector or quick-create modal.
  - Persists an APPLIED signup and responds ephemerally.
- `Review Requests`
  - Visible to referees; launches the approvals panel with Accept/Decline controls.
- `Nudge`
  - Visible to the owning referee only; enforces a 48h cooldown using quest `last_nudged_at`.
  - Posts a gold “Quest Nudge” embed linking back to the announcement message.
  - Triggers demo logging so moderators can audit outreach.

## Characters

- `/character create`
  - Guided DM wizard (modals) collecting name, links, description, notes, tags
  - Permissions: must run in a guild; member only
  - Output: posts announcement in configured channel, creates a private onboarding thread, DM confirmation with announcement link
- `/character list`
  - Inputs: none
  - Permissions: must run in a guild; member only
  - Output: ephemeral embed listing the caller’s characters and sheet links
- `/character edit`
  - Inputs: `character` (ID autocomplete)
  - Permissions: owner or staff roles
  - Output: DM wizard to edit fields, updates announcement embed/thread
- `/character state`
  - Inputs: `character` (ID autocomplete), `state` (active/retired)
  - Permissions: owner or staff roles
  - Output: toggles status and refreshes the public embed
- `/character show`
  - Inputs: `character` (ID autocomplete)
  - Permissions: owner or staff roles
  - Output: ephemeral embed with announcement link button

## Stats

- `stats`
  - Inputs: none
  - Permissions: must run in a guild; member only
  - Output: ephemeral embed of user stats (messages, reactions, voice time)
  - Logging: exceptions logged on failure
- `leaderboard`
  - Inputs: `metric: messages|reactions_given|reactions_received|voice`
  - Permissions: must run in a guild
  - Output: ephemeral embed with top users by metric (guild-scoped)
  - Logging: none
- `nudges`
  - Inputs: `state: enable|disable`
  - Permissions: must run in a guild; member only
  - Output: ephemeral confirmation of DM opt-in state
  - Logging: none

## Help

- `help`
  - Inputs: none
  - Permissions: none enforced
  - Output: ephemeral embed with quickstart and links
  - Logging: none

## Direct Messages

- `register` (DM only)
  - Inputs: none
  - Permissions: must be used in DM; user must share a guild with the bot
  - Output: ephemeral DM with setup confirmation and tips
  - Logging: exceptions logged on DM edge cases

## Demo Utilities

- `demo_about`
  - Inputs: none
  - Permissions: none enforced
  - Output: ephemeral embed describing the demo
  - Logging: none
- `demo_reset`
  - Inputs: none
  - Permissions: guild owner only
  - Output: ephemeral confirmation after DB reset and reseed
  - Logging: info log; demo log

## Guild Setup
- `setup`
  - Inputs: `force?: bool`
  - Permissions: manage_guild or administrator
  - Output: Ensures Quest Manager role, sign-up channel, and log channel exist; stores configuration per guild
  - Logging: info logs when resources are created
- `setup_status`
  - Inputs: none
  - Permissions: none (read-only)
  - Output: Displays the stored configuration for the current guild
  - Logging: none
- `setup_reset`
  - Inputs: none
  - Permissions: manage_guild or administrator
  - Output: Removes stored configuration references without deleting Discord resources
  - Logging: none
