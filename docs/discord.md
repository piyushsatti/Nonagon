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

- `createquest`
  - Inputs: `title: str`, `start_time_epoch: int>=0`, `duration_hours: int[1..48]`, `description?: str`, `image_url?: str`
  - Permissions: must run in a guild; user must be REFEREE
  - Output: quest announcement embed in channel; ephemeral confirmation
  - Logging: info log; demo log entry
- `joinquest`
  - Inputs: `quest_id: str` (autocomplete), `character_id: str` (autocomplete)
  - Permissions: must run in a guild; user must be PLAYER and own the character
  - Output: ephemeral confirmation; channel message notes the join
  - Logging: demo log; debug logs on fetch failures
- `leavequest`
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

- `character_add`
  - Inputs: `name: str`, `ddb_link: str`, `character_thread_link: str`, `token_link: str`, `art_link: str`, `description?: str`, `notes?: str`, `tags?: str`
  - Permissions: must run in a guild; member only
  - Output: ephemeral confirmation with new character ID (e.g., `CHARB2F4D9`)
  - Logging: info log; demo log
- `character_list`
  - Inputs: none
  - Permissions: must run in a guild; member only
  - Output: ephemeral embed of the caller’s characters
  - Logging: none

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
- `invite`
  - Inputs: none
  - Permissions: none enforced
  - Output: ephemeral OAuth2 invite link or config error
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
  - Permissions: administrator only; must run in a guild
  - Output: ephemeral confirmation after DB reset and reseed
  - Logging: info log; demo log

