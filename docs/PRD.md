# Nonagon Product Requirements Document

## 1. Document Control
| Field | Details |
| --- | --- |
| Project Name | Nonagon |
| Project Description | Discord bot for tracking member interactions, automating quest announcements, and managing player sign-ups and summaries. |
| Product Owner | Piyush Satti |
| Contributors | Piyush Satti |
| Contact | piyushsatti@gmail.com |
| Repository | https://github.com/piyushsatti/nonagon |
| Date Created | 17 Aug 2025 |
| Last Updated | 22 Oct 2025 (EP7 postal IDs telemetry + docs sweep) |
| Version | 1.0 |
| Document Status | Draft |

## 2. Product Overview
### 2.1 Vision
Deliver a guild-friendly Discord companion that streamlines the full quest lifecycle while preserving moderator control and auditability.

### 2.2 Objectives
- Automate quest drafting, publishing, and roster management inside Discord.
- Maintain clean signup data through duplicate protections and role-based access.
- Provide staff tooling for quick lookups and guild-aware reporting.

### 2.3 Primary Users
- Dungeon Masters (DMs)
- Players
- Moderators and staff
- Developers and maintainers

## 3. Delivery Snapshot
- [x] EP2-S1 - Request-to-Join flow stores APPLIED signups and confirms ephemerally.
- [x] EP2-S2 - DM-only requests panel with Accept and Decline controls.
- [x] EP2-S3 - Accept action updates SELECTED players, rerenders embeds, and notifies players.
- [x] EP2-S4 - Decline action removes applicants, updates embeds, and logs the outcome.
- [x] EP2-S5 - Duplicate guard enforced with localized messaging and regression tests.
- [x] EP3-S1 - DM-visible Nudge button added to quest embeds.
- [x] EP3-S2 - Nudge cooldown enforced with quest bump messaging.
- [x] EP3-S3 - Nudge activity recorded in telemetry and audit logs.
- [x] EP5-S1 - Quest embeds display emoji section headers via centralized builder.
- [x] EP5-S2 - Quest interactions respond ephemerally unless broadcast is required.
- [x] EP5-S3 - Quest footers communicate state cues with standardized templates.
- [x] EP6-S1 - `/lookup add` stores guild-scoped references with audit logging.
- [x] EP6-S2 - `/lookup get` returns ranked matches with friendly misses.
- [x] EP6-S3 - `/lookup list` paginates entries (<= 25 per page) with alphabetical ordering.
- [x] EP6-S4 - `/lookup remove` deletes entries or returns not-found warnings.
- [x] EP7-S1 - Postal-style ID generation shipped across repositories and demos.
- [ ] EP1 Quest Forge Flow - Preview, approval, and discard tooling pending.
- [ ] EP4 Friendly Player Registration Flow - Deferred until EP5 completion.
- [ ] EP5-S4 - Quest previews should move to threads and clean up automatically.
- [x] EP7-S1 follow-up - Sweep remaining `.number` usage and document migration guidance.
- [x] EP7-S2 - Postal IDs surface in logging and demo documentation.

## 4. Non-Functional Requirements
- Performance: Data collection should not lag Discord interactions.
- Scalability: Support multiple concurrent quests and players.
- Security: Enforce role-based access; only admins or creators modify stored data.
- Reliability: Automated flows require minimal manual intervention.

## 5. Jira Configuration
- Issue types: Epic, Story, Task, Bug.
- Workflow: To Do -> In Progress -> In Review -> Done.

## 6. Roadmap and Priority
- [x] P1 - EP1 Quest DM Workflow (complete): Slash commands now drive DM-based drafting, editing, announcements, and live scheduling.
- [x] P1 - EP2 Controlled Sign-Up Management (complete): Full review and decision flow live.
- [x] P1 - EP3 Nudge Button (complete): Cooldown-respected quest bumping delivered.
- [x] P1 - EP7 External Quest IDs (complete): Postal IDs flow through repositories, logging, and demos.
- [x] P2 - EP6 `/lookup` Command (complete): Guild-scoped lookup management with auditing delivered.
- [ ] P3 - EP5 Simple UI Improvements (partially complete): Previews still need thread cleanup and fallbacks.
- [ ] Deferred - EP4 Friendly Player Registration Flow (paused): Resume after EP5-S4 to avoid conflicting UX.

## 7. Epics and Stories
### EP1 - Quest DM Workflow (Priority P1, Status: Complete)
**Goal**: Provide a DM-first quest lifecycle with optional scheduling and ongoing moderation tools.
**Scope**: `/quest create`, `/quest edit`, `/quest announce` (immediate or scheduled), `/quest nudge`, `/quest cancel`, `/quest players`, and the background scheduler loop.
**Out of Scope**: Automated waitlists, multi-guild broadcast tooling.
**Dependencies**: Quest embed builder, Mongo quest persistence, guild settings store.
**Milestones**: DM wizard -> Announcement & scheduler -> Maintenance commands -> Demo logging.
**Non-Functional Notes**: Ensure idempotent persistence, guard cooldowns, surface friendly error copy in DMs.

#### Story EP1-S1 - Quest Draft Wizard
- **Status**: Complete
- **User Story**: As a referee, I want a guided DM flow so I can draft a quest without juggling parameters.
- **Acceptance Criteria**
  1. `/quest create` starts a DM wizard that collects title, description, start time, duration, and optional image URL with live embed previews.
- **Definition of Done**
  - [x] Live preview updates after each step.
  - [x] DRAFT quests are persisted once validation succeeds.
  - [x] DM follow-up includes instructions for announcing.
- **Implementation Tasks**
  - [x] Add `QuestCreationSession` with preview handling.
  - [x] Persist drafts via `_persist_quest`.
  - [x] Update demo docs and onboarding messages.

#### Story EP1-S2 - Announcement & Scheduler
- **Status**: Complete
- **User Story**: As a referee, I want to announce immediately or schedule a quest so players see it at the right time.
- **Acceptance Criteria**
  1. `/quest announce` posts immediately when no time is provided and schedules when a future timestamp is supplied.
  2. Background scheduler promotes quests when `announce_at <= now` and they lack channel/message IDs.
- **Definition of Done**
  - [x] Announcement embed includes signup view and quest metadata.
  - [x] Scheduler loop logs failures and retries safely.
  - [x] Guild configuration validates announcement channel and permissions.
- **Implementation Tasks**
  - [x] Implement `_quest_schedule_loop` polling every 60 seconds.
  - [x] Add `_announce_quest_now` with ping-role support.
  - [x] Extend `/setup quest` to configure announcement channel + optional ping role.
  - Note: `/setup sync` was removed from the slash command surface. Syncing is now owner-only:
    - Prefix owner commands: `n!sync` (current guild) and `n!syncall` (all guilds).
    - Extension manager `/sync` (guild-scoped) is available to owners.
  - `/setup server_tag` was renamed to `/setup servertag`. When enabling, you must supply both a role and a pattern (case-insensitive substring match against member nick/display/name). Stored keys remain `server_tag_*` for backwards compatibility.
    - Example: `/setup servertag enabled:true role:@ServerTag pattern:"[GuildTag]"`
  - `/setup boosters` now requires a role when enabling (no interactive ask flow).
    - Example: `/setup boosters enabled:true role:@Boosters`


#### Story EP1-S3 - Quest Maintenance Commands
- **Status**: Complete
- **User Story**: As a referee, I want quick commands to maintain quest state after announcement.
- **Acceptance Criteria**
  1. `/quest nudge` respects a 48h cooldown and optionally pings the configured role.
  2. `/quest cancel` updates the embed, removes signup view, and logs the action.
  3. `/quest players` lists selected and pending players for completed quests.
- **Definition of Done**
  - [x] Nudge embeds link back to the announcement and record timestamps.
  - [x] Cancelled quests persist status and disable further signups.
  - [x] Player listing shows postal IDs with user mentions where available.
- **Implementation Tasks**
  - [x] Rework `_execute_nudge` to reuse guild settings and cooldown logic.
  - [x] Add roster formatting helpers for `/quest players`.
  - [x] Ensure audit logging (demo log) exists for each action.

#### Story EP1-S4 - Summary Threads
- **Status**: Complete
- **User Story**: As a player, I want to share a summary that posts an announcement and opens a thread for the full write-up.
- **Acceptance Criteria**
  1. `/summary create` runs a DM wizard that captures metadata (title, linked quests, characters, TL;DR) and immediately posts an embed plus a discussion thread in the configured summary channel.
  2. `/summary edit` refreshes the announcement embed while preserving thread content.
- **Definition of Done**
  - [x] Summary embeds display author, character IDs, linked quests, and TL;DR.
  - [x] Threads include a prompt encouraging long-form content.
  - [x] Summaries persist channel/message/thread IDs for future updates.
- **Implementation Tasks**
  - [x] Introduce `SummaryCommandsCog` with creation and update sessions.
  - [x] Expand `QuestSummary` model with announcement metadata and validation.
  - [x] Document the summary flow in user-facing help materials.

### EP2 - Controlled Sign-Up Management (Priority P1, Status: Complete)
**Goal**: Let DMs approve or decline players before they join quests.
**Scope**: Request button, review panel, Accept and Decline updates, embed refresh.
**Out of Scope**: Automated waitlisting, capacity caps.
**Dependencies**: Mongo signups, FastAPI signup endpoints.
**Milestones**: Request flow -> Review UI -> Accept and Decline actions -> Embed synchronization.
**Non-Functional Notes**: Maintain duplicate prevention, role checks, and comprehensive logging.

#### Story EP2-S1 - Request to Join
- **Status**: Complete
- **User Story**: As a player, I want to request to join so the DM can review me.
- **Acceptance Criteria**
  1. When Request to Join is clicked, a signup with status APPLIED is stored and the player receives an ephemeral confirmation.
- **Definition of Done**
  - [x] `POST /v1/quests/{id}/signups` invoked.
  - [x] Duplicate attempts rejected politely.
  - [x] Interaction logged for auditing.
- **Implementation Tasks**
  - [x] Rename Join button to Request to Join.
  - [x] Map the interaction to FastAPI or cache persistence.
  - [x] Handle duplicate errors via embed follow-up.

#### Story EP2-S2 - Pending Requests Panel
- **Status**: Complete
- **User Story**: As a DM, I want to view pending requests so I can decide who joins.
- **Acceptance Criteria**
  1. When APPLIED signups exist and the requests panel opens, each applicant appears with Accept and Decline controls.
- **Definition of Done**
  - [x] DM-only view generated.
  - [x] Pagination available for more than 25 requests.
  - [x] Errors surface ephemerally.
- **Implementation Tasks**
  - [x] Implement `/quest requests` as a slash command or panel.
  - [x] Render embed listing APPLIED players with metadata.
  - [x] Provide custom IDs linking actions to players.

#### Story EP2-S3 - Accept Applicants
- **Status**: Complete
- **User Story**: As a DM, I want to accept a player so the roster updates automatically.
- **Acceptance Criteria**
  1. When Accept is clicked, the signup status becomes SELECTED, the quest embed updates, and the player is notified.
- **Definition of Done**
  - [x] `POST /v1/quests/{id}/signups/{user_id}:select` invoked.
  - [x] Embed re-renders with the SELECTED section.
  - [x] Notification sent ephemerally or via DM.
- **Implementation Tasks**
  - [x] Implement Accept button callback.
  - [x] Update embed builder to highlight SELECTED players.
  - [x] Send friendly confirmation to the player.

#### Story EP2-S4 - Decline Applicants
- **Status**: Complete
- **User Story**: As a DM, I want to decline applicants so I manage capacity.
- **Acceptance Criteria**
  1. When Decline is clicked, the signup is removed and the player receives a decline notification.
- **Definition of Done**
  - [x] `DELETE /v1/quests/{id}/signups/{user_id}` invoked.
  - [x] Embed re-renders without the applicant.
  - [x] Decline action logged.
- **Implementation Tasks**
  - [x] Add Decline button callback.
  - [x] Handle missing signup gracefully.
  - [x] Send an ephemeral decline message.

#### Story EP2-S5 - Duplicate Protection
- **Status**: Complete
- **User Story**: As a developer, I want duplicate protections respected so the data stays clean.
- **Acceptance Criteria**
  1. When a player who already applied requests again, an error returns and no new entry is created.
- **Definition of Done**
  - [x] Domain guard remains intact.
  - [x] API tests cover the duplicate branch.
  - [x] Messaging localized for Discord surfaces.
- **Implementation Tasks**
  - [x] Confirm duplicate guard in `Quest.add_signup`.
  - [x] Add regression tests in `tests/api/test_quests.py`.
  - [x] Improve error string for Discord responses.
- **Backlog Note**
  - [ ] Admin and staff need `/lookup` updates and refreshed demo docs for onboarding.

### EP3 - Nudge Button (Priority P1, Status: Complete)
**Goal**: Give DMs a cooldown-respecting quest bump.
**Scope**: DM-only button, bump message, cooldown tracking.
**Out of Scope**: Automated player reminders.
**Dependencies**: Quest embed builder, Mongo quest fields.
**Milestones**: Button visibility -> Cooldown enforcement -> Logging.
**Non-Functional Notes**: Enforce 48-hour cooldown and maintain idempotent telemetry.

#### Story EP3-S1 - DM-Only Nudge Button
- **Status**: Complete
- **Definition of Done**
  - [x] Role gate ensures DM visibility.
  - [x] Button renders near Request controls.
  - [x] UI interactions logged.
- **Implementation Tasks**
  - [x] Add Nudge button to `QuestSignupView`.
  - [x] Filter visibility per interaction user.
  - [x] Document button behavior in demo materials.

#### Story EP3-S2 - Cooldown Enforcement
- **Status**: Complete
- **Definition of Done**
  - [x] `last_nudged_at` stored per quest.
  - [x] Cooldown feedback returned to the DM.
  - [x] Bump message links the original quest post.
- **Implementation Tasks**
  - [x] Add `last_nudged_at` field to the quest model and repository.
  - [x] Implement `POST /v1/quests/{id}:nudge`.
  - [x] Render bump embed referencing the quest.

#### Story EP3-S3 - Nudge Telemetry
- **Status**: Complete
- **Definition of Done**
  - [x] `send_demo_log` invoked on success.
  - [x] Errors captured with context.
  - [x] Tests validate the logging path.
- **Implementation Tasks**
  - [x] Tie logging into the nudge success path.
  - [x] Add unit tests using logging doubles.
  - [x] Update moderation SOP documentation.

### EP4 - Friendly Player Registration Flow (Deferred)
**Goal**: Onboard first-time players without friction.
**Scope**: Character detection, quick-create modal, auto-continue signup.
**Out of Scope**: Full character profile capture in the quick flow.
**Dependencies**: Characters repository, quest signup interactions.
**Milestones**: Detection -> Modal -> Persist -> Continue signup.
**Non-Functional Notes**: Require minimal fields, ensure owner scoping, handle errors gracefully.

#### Story EP4-S1 - Detect Missing Characters
- **Status**: Deferred
- **Definition of Done**
  - [ ] Character lookup by `owner_id`.
  - [ ] Modal displayed once per interaction.
  - [ ] Logging includes quest and player context.
- **Implementation Tasks**
  - [ ] Extend `QuestSignupView` to query the guild cache.
  - [ ] Present quick-register modal.
  - [ ] Handle parallel requests safely.

#### Story EP4-S2 - Quick-Create Character
- **Status**: Deferred
- **Definition of Done**
  - [ ] Character persisted with minimal fields.
  - [ ] `created_at` timestamp set.
  - [ ] Errors surface ephemerally.
- **Implementation Tasks**
  - [ ] Add quick-create helper (API or direct Mongo write).
  - [ ] Relax validation or provide placeholder links.
  - [ ] Store `guild_id` and `owner_id` correctly.

#### Story EP4-S3 - Resume Signup After Registration
- **Status**: Deferred
- **Definition of Done**
  - [ ] Signup triggered after character creation.
  - [ ] Failure recovery informs the user.
  - [ ] Telemetry recorded for adoption metrics.
- **Implementation Tasks**
  - [ ] Chain modal completion to signup logic.
  - [ ] Provide fallback instructions on failure.
  - [ ] Track adoption metrics.

#### Story EP4-S4 - Character Dropdown
- **Status**: Deferred
- **Definition of Done**
  - [ ] Dropdown options generated from guild cache.
  - [ ] Fallback to modal when no characters exist.
  - [ ] Tests cover select population.
- **Implementation Tasks**
  - [ ] Reuse `CharacterSelect` with improved labels.
  - [ ] Add tests ensuring fallback path works.
  - [ ] Update docs describing dropdown behavior.

### EP5 - Simple UI Improvements (Priority P3, Status: Partially Complete)
**Goal**: Polish embeds and interactions without altering business logic.
**Scope**: Emoji headers, state cues, thread previews, ephemeral confirmations.
**Out of Scope**: Discord theming beyond defaults.
**Dependencies**: Embed builder, quest lifecycle handlers.
**Milestones**: Embed polish -> Role gating -> State cues -> Thread previews.
**Non-Functional Notes**: Avoid regressions on existing commands.

#### Story EP5-S1 - Emoji Section Headers
- **Status**: Complete
- **Definition of Done**
  - [x] Embed builder centralized.
  - [x] Legacy commands reuse the builder.
  - [x] Snapshot tests cover section headers.
- **Implementation Tasks**
  - [x] Refactor embed builder into a helper.
  - [x] Update preview and announce flows to reuse the helper.
  - [x] Add tests verifying section headers.

#### Story EP5-S2 - Ephemeral Confirmations
- **Status**: Complete
- **Definition of Done**
  - [x] Quest interactions return ephemeral responses when appropriate.
  - [x] Logging includes interaction outcomes.
  - [x] Regression tests ensure `/joinquest` and `/leavequest` remain ephemeral.
- **Implementation Tasks**
  - [x] Review join, leave, and accept flows.
  - [x] Add `tests/bot/test_quest_commands_ephemeral.py`.
  - [x] Extend coverage to review and decision panels plus logging states.

#### Story EP5-S3 - Quest State Cues
- **Status**: Complete
- **Definition of Done**
  - [x] Footer template standardized.
  - [x] Triggered on Accept, Decline, and Close signups.
  - [x] Tests cover footer output.
- **Implementation Tasks**
  - [x] Implement footer builder.
  - [x] Hook into quest state transitions.
  - [x] Add tests for footer formatting.

#### Story EP5-S4 - Threaded Previews
- **Status**: Planned
- **Definition of Done**
  - [ ] Thread handling includes permission fallback.
  - [ ] Cleanup on finalize or discard.
  - [ ] Errors surface ephemerally.
- **Implementation Tasks**
  - [ ] Use `message.create_thread` for preview hosting.
  - [ ] Track thread IDs for cleanup.
  - [ ] Handle permission failures gracefully.

### EP6 - `/lookup` Command (Priority P2, Status: Complete)
**Goal**: Offer lightweight reference search for staff.
**Scope**: Add, get, list, and remove commands with per-guild storage.
**Out of Scope**: Full-text fuzzy search beyond basic matching.
**Dependencies**: Mongo collection, new bot cog.
**Milestones**: Storage schema -> Command set -> Pagination -> Auditing.
**Non-Functional Notes**: Keep commands role-guarded with reliable responses.

#### Story EP6-S1 - Add Lookup Entries
- [x] `/lookup add name:<text> url:<url>` stores entries per guild and confirms success.
- [x] Upsert on `(guild_id, name)` with staff-only checks.
- [x] Logging and URL validation implemented.

#### Story EP6-S2 - Fetch Lookup Entries
- [x] `/lookup get` returns best matches (exact -> prefix -> contains).
- [x] Responses are ephemeral and misses are logged for analysis.

#### Story EP6-S3 - List Lookup Entries
- [x] `/lookup list` paginates results with alphabetical ordering.
- [x] Pagination UI added with integration tests.

#### Story EP6-S4 - Remove Lookup Entries
- [x] `/lookup remove` deletes entries or surfaces not-found warnings.
- [x] Audit logging records removals.

### EP7 - External Quest IDs (Priority P1, Status: In Progress)
**Goal**: Preserve readable quest IDs while migrating entities to the new postal-style format across API, bot, and demo tooling.
**Scope**: Postal generator, repository filters, logging alignment, demo seeding, regression tests.
**Out of Scope**: Changing entity prefixes or removing legacy numeric parsing.
**Dependencies**: `EntityID` model, Mongo repositories, quest and character cogs, demo commands, telemetry logging.
**Milestones**: Generator and compatibility -> Persistence rewrite -> Logging cleanup -> Regression suite.
**Non-Functional Notes**: Detect collisions, maintain backward compatibility, avoid Mongo `_id` leakage.

#### Story EP7-S1 - Postal IDs End-to-End

- **Status**: Complete
- **Definition of Done**
  - [x] `EntityIDModel` generates postal bodies and normalizes legacy values.
  - [x] Repositories store and query against `.value`.
  - [x] Demo seeding ships postal IDs without counters.
  - [x] Quest and character flows no longer access `.number`.
  - [x] Migration notes documented in `docs/architecture.md`.
- **Implementation Tasks**
  - [x] Replace sequential counters with `EntityID.generate()`.
  - [x] Normalize owner and referee lookups to store `UserID.value`.
  - [x] Sweep quest and character flows for `.number` assumptions.
  - [x] Document guild migration notes.

#### Story EP7-S2 - Postal IDs in Telemetry

- **Status**: Complete
- **Definition of Done**
  - [x] `send_demo_log` payloads include `quest_id` postal values.
  - [x] Logging avoids Mongo `_id`.
  - [x] Audit fixtures updated with postal examples.
- **Implementation Tasks**
  - [x] Update quest lifecycle logging to use `quest.quest_id.value`.
  - [x] Refresh demo log templates and docs with postal-style examples.
  - [x] Add regression notes in `docs/discord.md`.


## 8. Resources and Dependencies

- Framework: discord.py.
- Database: MongoDB Atlas.
- Infrastructure: Docker hosted on DigitalOcean.


## 9. Release Timeline

- [x] Milestone 1 - Bot skeleton and database setup.
- [x] Milestone 2 - Quest announcement plus sign-up automation.
- [ ] Milestone 3 - Summary linking and data tracking MVP.


## 10. Risks and Assumptions

### Risks

- Discord API limitations could block or throttle automation.
- Manual overrides by admins may introduce data inconsistency.

### Assumptions

- Single development team maintains the bot.
- Users are already familiar with Discord workflows.


## Appendix A - Experimental Branch Delta (vs `main`)

This branch introduces multi-guild scoping, guild-aware APIs, and data migration utilities.

- [x] Multi-guild data model and storage updated with `guild_id` on all domain models and Mongo documents.
- [x] Repositories and queries filter by `guild_id` to prevent cross-guild collisions.
- [x] Sync adapters upsert with compound filters including `guild_id`.
- [x] Per-guild compound indexes created for users, quests, and characters.
- [x] Migration script `scripts/migrations/backfill_guild_id.py` populates `guild_id` and ensures indexes.
- [x] `Nonagon.guild_data` cache and background flush loop operate per guild.
- [x] Cache loader prefers documents with `guild_id`, falling back to legacy data for bootstrap.
- [x] Slash commands and cogs scope quest, character, and statistics operations to the interaction guild.
- [x] Diagnostics and demo utilities honor guild scoping.
- [x] Public API introduces guild-scoped user routes under `/v1/guilds/{guild_id}/users`.
- [x] API schemas include `guild_id` with normalized telemetry field names such as `messages_count_total`.
- [x] Documentation adds `docs/discord.md` with slash command details.
- [x] Discord intents checklist merged into `docs/architecture.md`; `docs/discord_intents.md` removed.
- [x] Migration compatibility maintained via provided utilities.
