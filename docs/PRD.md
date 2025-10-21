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
| Last Updated | 21 Oct 2025 (EP7 postal-style IDs + demo alignment) |
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
- Moderators / Staff
- Developers / Maintainers

## 3. Delivery Snapshot
- [x] EP2-S1 — Request-to-Join flow stores APPLIED signups and confirms ephemerally.
- [x] EP2-S2 — DM-only requests panel with Accept/Decline controls.
- [x] EP2-S3 — Accept action updates SELECTED players, rerenders embeds, and notifies players.
- [x] EP2-S4 — Decline action removes applicants, updates embeds, and logs the outcome.
- [x] EP2-S5 — Duplicate guard enforced with localized messaging and regression tests.
- [x] EP3-S1 — DM-visible Nudge button added to quest embeds.
- [x] EP3-S2 — Nudge cooldown enforced with quest bump messaging.
- [x] EP3-S3 — Nudge activity recorded in telemetry and audit logs.
- [x] EP5-S1 — Quest embeds display emoji section headers via centralized builder.
- [x] EP5-S2 — Quest interactions respond ephemerally unless broadcast is required.
- [x] EP5-S3 — Quest footers communicate state cues with standardized templates.
- [x] EP6-S1 — `/lookup add` stores guild-scoped references with audit logging.
- [x] EP6-S2 — `/lookup get` returns ranked matches with friendly misses.
- [x] EP6-S3 — `/lookup list` paginates entries (≤25 per page) with alphabetical ordering.
- [x] EP6-S4 — `/lookup remove` deletes entries or returns not-found warnings.
- [x] EP7-S1 — Postal-style ID generation shipped across repositories and demos.
- [ ] EP1 Quest Forge Flow — Preview, approval, and discard tooling pending.
- [ ] EP4 Friendly Player Registration Flow — Deferred until EP5 completion.
- [ ] EP5-S4 — Quest previews should move to threads and clean up automatically.
- [ ] EP7-S1 — Sweep remaining `.number` usage and document migration guidance.
- [ ] EP7-S2 — Postal IDs must surface in logging and demo documentation.

## 4. Non-Functional Requirements
- Performance: Data collection should not lag Discord interactions.
- Scalability: Support multiple concurrent quests and players.
- Security: Enforce role-based access; only admins or creators modify stored data.
- Reliability: Automated flows require minimal manual intervention.

## 5. Jira Configuration
- Issue types: Epic, Story, Task, Bug.
- Workflow: To Do → In Progress → In Review → Done.

## 6. Roadmap & Priority
- [ ] P1 — EP1 Quest Forge Flow (planned): Preview, approve, and discard flows outstanding.
- [x] P1 — EP2 Controlled Sign-Up Management (complete): Full review and decision flow live.
- [x] P1 — EP3 Nudge Button (complete): Cooldown-respected quest bumping delivered.
- [ ] P1 — EP7 External Quest IDs (in progress): Generator shipped; repo sweeps and docs remaining.
- [x] P2 — EP6 `/lookup` Command (complete): Guild-scoped lookup management with auditing delivered.
- [ ] P3 — EP5 Simple UI Improvements (partially complete): Previews still need thread cleanup and fallbacks.
- [ ] Deferred — EP4 Friendly Player Registration Flow (paused): Resume after EP5-S4 to avoid conflicting UX.

## 7. Epics & Stories
### EP1 — Quest Forge Flow (Priority P1, Status: Planned)
**Goal**: Enable DMs to draft, preview, and finalize quests inside Discord.  
**Scope**: Forge channel previews, approve/discard actions, quest board publishing.  
**Out of Scope**: Advanced markdown parsing, multi-message drafts.  
**Dependencies**: Quest embed builder, FastAPI quest creation endpoint.  
**Milestones**: Preview button → Approve/Discard actions → Thread previews → Publish.  
**Non-Functional Notes**: Avoid Database writes before approval, make discard idempotent, log every action.

#### Story EP1-S1 — Preview Forge Messages
- **Status**: Planned
- **User Story**: As a DM, I want a Preview button on my forge message so I can render an embed before publishing.
- **Acceptance Criteria**
  1. When a DM posts a quest draft in the forge channel, the bot attaches a DM-only Preview button.
- **Definition of Done**
  - [ ] Role checks enforce DM-only access.
  - [ ] Preview button interactions are logged for auditing.
  - [ ] No persistence occurs when a preview is generated.
- **Implementation Tasks**
  - [ ] Detect forge-channel messages in `src/app/bot/cogs/QuestCommandsCog.py`.
  - [ ] Attach a `discord.ui.View` with a Preview callback.
  - [ ] Expose a configurable forge channel setting.

#### Story EP1-S2 — Refreshable Previews
- **Status**: Planned
- **User Story**: As a DM, I want the preview to reflect my latest edits so I see final formatting.
- **Acceptance Criteria**
  1. When a DM updates the draft and clicks Preview again, the embed refreshes with the latest content and replaces older previews.
- **Definition of Done**
  - [ ] Embed renderer reused across preview and announce flows.
  - [ ] Preview output isolated to a thread or ephemeral message.
  - [ ] Errors surface ephemerally to the DM.
- **Implementation Tasks**
  - [ ] Parse forge message content and hydrate the quest embed.
  - [ ] Convert preview responses into auto-created threads.
  - [ ] Handle stale preview cleanup gracefully.

#### Story EP1-S3 — Approve to Publish
- **Status**: Planned
- **User Story**: As a DM, I want Approve to publish and persist the quest so players can sign up.
- **Acceptance Criteria**
  1. Given a valid preview, when Approve is clicked, the quest posts to the quest board and is saved with ANNOUNCED status.
- **Definition of Done**
  - [ ] Announcement includes the signup view and quest ID footer.
  - [ ] `POST /v1/quests` receives channel/message IDs and raw markdown.
  - [ ] Audit log entry is emitted.
- **Implementation Tasks**
  - [ ] Reuse the existing quest persistence flow.
  - [ ] Provide guild, channel, and message IDs to FastAPI.
  - [ ] Roll back gracefully on failures by deleting previews.

#### Story EP1-S4 — Discard Drafts Cleanly
- **Status**: Planned
- **User Story**: As a DM, I want Discard to clean up drafts so the forge channel stays tidy.
- **Acceptance Criteria**
  1. When Discard is clicked on an existing preview, the preview and thread are deleted with no quest record stored.
- **Definition of Done**
  - [ ] Discard handler is idempotent.
  - [ ] Discard actions are logged.
  - [ ] Error messaging is delivered ephemerally.
- **Implementation Tasks**
  - [ ] Track preview message and thread IDs.
  - [ ] Delete associated resources on discard.
  - [ ] Handle missing preview state gracefully.

#### Story EP1-S5 — Draft Quest Status
- **Status**: Planned
- **User Story**: As a Developer, I want a DRAFT status so future iterations can persist drafts.
- **Acceptance Criteria**
  1. QuestStatus.DRAFT can be stored without breaking existing flows.
- **Definition of Done**
  - [ ] Enum updates permit DRAFT.
  - [ ] Serialization logic supports all quest states.
  - [ ] Tests cover DRAFT handling.
- **Implementation Tasks**
  - [ ] Update `QuestStatus` in `src/app/domain/models/QuestModel.py`.
  - [ ] Adjust serialization/deserialization helpers.
  - [ ] Add regression tests in `tests/domain/models/test_quest_model.py`.

### EP2 — Controlled Sign-Up Management (Priority P1, Status: Complete)
**Goal**: Let DMs approve or decline players before they join quests.  
**Scope**: Request button, review panel, Accept/Decline updates, embed refresh.  
**Out of Scope**: Automated waitlisting, capacity caps.  
**Dependencies**: Mongo signups, FastAPI signup endpoints.  
**Milestones**: Request flow → Review UI → Accept/Decline actions → Embed synchronization.  
**Non-Functional Notes**: Maintain duplicate prevention, role checks, and comprehensive logging.

#### Story EP2-S1 — Request to Join
- **Status**: Complete
- **User Story**: As a Player, I want to request to join so the DM can review me.
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

#### Story EP2-S2 — Pending Requests Panel
- **Status**: Complete
- **User Story**: As a DM, I want to view pending requests so I can decide who joins.
- **Acceptance Criteria**
  1. When APPLIED signups exist and the requests panel opens, each applicant appears with Accept/Decline controls.
- **Definition of Done**
  - [x] DM-only view generated.
  - [x] Pagination available for >25 requests.
  - [x] Errors surface ephemerally.
- **Implementation Tasks**
  - [x] Implement `/quest requests` (slash command or panel).
  - [x] Render embed listing APPLIED players with metadata.
  - [x] Provide custom IDs linking actions to players.

#### Story EP2-S3 — Accept Applicants
- **Status**: Complete
- **User Story**: As a DM, I want to accept a player so the roster updates automatically.
- **Acceptance Criteria**
  1. When Accept is clicked, the signup status becomes SELECTED, the quest embed updates, and the player is notified.
- **Definition of Done**
  - [x] `POST /v1/quests/{id}/signups/{user_id}:select` invoked.
  - [x] Embed re-renders with SELECTED section.
  - [x] Notification sent ephemerally or via DM.
- **Implementation Tasks**
  - [x] Implement Accept button callback.
  - [x] Update embed builder to highlight SELECTED players.
  - [x] Send friendly confirmation to the player.

#### Story EP2-S4 — Decline Applicants
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

#### Story EP2-S5 — Duplicate Protection
- **Status**: Complete
- **User Story**: As a Developer, I want duplicate protections respected so the data stays clean.
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
  - [ ] Admin/staff need `/lookup` updates and refreshed demo docs for onboarding.

### EP3 — Nudge Button (Priority P1, Status: Complete)
**Goal**: Give DMs a cooldown-respecting quest bump.  
**Scope**: DM-only button, bump message, cooldown tracking.  
**Out of Scope**: Automated player reminders.  
**Dependencies**: Quest embed builder, Mongo quest fields.  
**Milestones**: Button visibility → Cooldown enforcement → Logging.  
**Non-Functional Notes**: Enforce 48-hour cooldown and maintain idempotent telemetry.

#### Story EP3-S1 — DM-Only Nudge Button
- **Status**: Complete
- **Definition of Done**
  - [x] Role gate ensures DM visibility.
  - [x] Button renders near Request controls.
  - [x] UI interactions logged.
- **Implementation Tasks**
  - [x] Add Nudge button to `QuestSignupView`.
  - [x] Filter visibility per interaction user.
  - [x] Document button behavior in demo materials.

#### Story EP3-S2 — Cooldown Enforcement
- **Status**: Complete
- **Definition of Done**
  - [x] `last_nudged_at` stored per quest.
  - [x] Cooldown feedback returned to the DM.
  - [x] Bump message links the original quest post.
- **Implementation Tasks**
  - [x] Add `last_nudged_at` field to the quest model and repository.
  - [x] Implement `POST /v1/quests/{id}:nudge`.
  - [x] Render bump embed referencing the quest.

#### Story EP3-S3 — Nudge Telemetry
- **Status**: Complete
- **Definition of Done**
  - [x] `send_demo_log` invoked on success.
  - [x] Errors captured with context.
  - [x] Tests validate the logging path.
- **Implementation Tasks**
  - [x] Tie logging into the nudge success path.
  - [x] Add unit tests using logging doubles.
  - [x] Update moderation SOP documentation.

### EP4 — Friendly Player Registration Flow (Deferred)
**Goal**: Onboard first-time players without friction.  
**Scope**: Character detection, quick-create modal, auto-continue signup.  
**Out of Scope**: Full character profile capture in the quick flow.  
**Dependencies**: Characters repository, quest signup interactions.  
**Milestones**: Detection → Modal → Persist → Continue signup.  
**Non-Functional Notes**: Require minimal fields, ensure owner scoping, handle errors gracefully.

#### Story EP4-S1 — Detect Missing Characters
- **Status**: Deferred
- **Definition of Done**
  - [ ] Character lookup by `owner_id`.
  - [ ] Modal displayed once per interaction.
  - [ ] Logging includes quest and player context.
- **Implementation Tasks**
  - [ ] Extend `QuestSignupView` to query the guild cache.
  - [ ] Present quick-register modal.
  - [ ] Handle parallel requests safely.

#### Story EP4-S2 — Quick-Create Character
- **Status**: Deferred
- **Definition of Done**
  - [ ] Character persisted with minimal fields.
  - [ ] `created_at` timestamp set.
  - [ ] Errors surface ephemerally.
- **Implementation Tasks**
  - [ ] Add quick-create helper (API or direct Mongo write).
  - [ ] Relax validation or provide placeholder links.
  - [ ] Store `guild_id` and `owner_id` correctly.

#### Story EP4-S3 — Resume Signup After Registration
- **Status**: Deferred
- **Definition of Done**
  - [ ] Signup triggered after character creation.
  - [ ] Failure recovery informs the user.
  - [ ] Telemetry recorded for adoption metrics.
- **Implementation Tasks**
  - [ ] Chain modal completion to signup logic.
  - [ ] Provide fallback instructions on failure.
  - [ ] Track adoption metrics.

#### Story EP4-S4 — Character Dropdown
- **Status**: Deferred
- **Definition of Done**
  - [ ] Dropdown options generated from guild cache.
  - [ ] Fallback to modal when no characters exist.
  - [ ] Tests cover select population.
- **Implementation Tasks**
  - [ ] Reuse `CharacterSelect` with improved labels.
  - [ ] Add tests ensuring fallback path works.
  - [ ] Update docs describing dropdown behavior.

### EP5 — Simple UI Improvements (Priority P3, Status: Partially Complete)
**Goal**: Polish embeds and interactions without altering business logic.  
**Scope**: Emoji headers, state cues, thread previews, ephemeral confirmations.  
**Out of Scope**: Discord theming beyond defaults.  
**Dependencies**: Embed builder, quest lifecycle handlers.  
**Milestones**: Embed polish → Role gating → State cues → Thread previews.  
**Non-Functional Notes**: Avoid regressions on existing commands.

#### Story EP5-S1 — Emoji Section Headers
- **Status**: Complete
- **Definition of Done**
  - [x] Embed builder centralized.
  - [x] Legacy commands reuse the builder.
  - [x] Snapshot tests cover section headers.
- **Implementation Tasks**
  - [x] Refactor embed builder into a helper.
  - [x] Update preview/announce flows to reuse the helper.
  - [x] Add tests verifying section headers.

#### Story EP5-S2 — Ephemeral Confirmations
- **Status**: Complete
- **Definition of Done**
  - [x] Quest interactions return ephemeral responses when appropriate.
  - [x] Logging includes interaction outcomes.
  - [x] Regression tests ensure `/joinquest` and `/leavequest` remain ephemeral.
- **Implementation Tasks**
  - [x] Review join/leave/accept flows.
  - [x] Add `tests/bot/test_quest_commands_ephemeral.py`.
  - [x] Extend coverage to review/decision panels and logging states.

#### Story EP5-S3 — Quest State Cues
- **Status**: Complete
- **Definition of Done**
  - [x] Footer template standardized.
  - [x] Triggered on Accept, Decline, and Close signups.
  - [x] Tests cover footer output.
- **Implementation Tasks**
  - [x] Implement footer builder.
  - [x] Hook into quest state transitions.
  - [x] Add tests for footer formatting.

#### Story EP5-S4 — Threaded Previews
- **Status**: Planned
- **Definition of Done**
  - [ ] Thread handling includes permission fallback.
  - [ ] Cleanup on finalize or discard.
  - [ ] Errors surface ephemerally.
- **Implementation Tasks**
  - [ ] Use `message.create_thread` for preview hosting.
  - [ ] Track thread IDs for cleanup.
  - [ ] Handle permission failures gracefully.

### EP6 — `/lookup` Command (Priority P2, Status: Complete)
**Goal**: Offer lightweight reference search for staff.  
**Scope**: Add/get/list/remove commands with per-guild storage.  
**Out of Scope**: Full-text fuzzy search beyond basic matching.  
**Dependencies**: Mongo collection, new bot cog.  
**Milestones**: Storage schema → Command set → Pagination → Auditing.  
**Non-Functional Notes**: Keep commands role-guarded with reliable responses.

#### Story EP6-S1 — Add Lookup Entries
- [x] `/lookup add name:<text> url:<url>` stores entries per guild and confirms success.
- [x] Upsert on `(guild_id, name)` with staff-only checks.
- [x] Logging and URL validation implemented.

#### Story EP6-S2 — Fetch Lookup Entries

- [x] `/lookup get` returns best matches (exact → prefix → contains).
- [x] Responses are ephemeral; misses logged for analysis.

#### Story EP6-S3 — List Lookup Entries

- [x] `/lookup list` paginates results with alphabetical ordering.
- [x] Pagination UI added with integration tests.

#### Story EP6-S4 — Remove Lookup Entries

- [x] `/lookup remove` deletes entries or surfaces not-found warnings.
- [x] Audit logging records removals.

### EP7 — External Quest IDs (Priority P1, Status: In Progress)

**Goal**: Preserve readable quest IDs while migrating entities to the new postal-style format across API, bot, and demo tooling.  
**Scope**: Postal generator, repository filters, logging alignment, demo seeding, regression tests.  
**Out of Scope**: Changing entity prefixes or removing legacy numeric parsing.  
**Dependencies**: `EntityID` model, Mongo repositories, quest/character cogs, demo commands, telemetry logging.  
**Milestones**: Generator + compatibility → Persistence rewrite → Logging cleanup → Regression suite.  
**Non-Functional Notes**: Detect collisions, maintain backward compatibility, avoid Mongo `_id` leakage.

Postal IDs follow an alternating letter-digit pattern (e.g., `QUESA1B2C3`) so they stay human-readable while remaining unique per prefix.

#### Story EP7-S1 — Postal IDs End-to-End

- **Status**: In Progress
- **Definition of Done**
  - [x] `EntityIDModel` generates postal bodies and normalizes legacy values.
  - [x] Repositories store/query against `.value`.
  - [x] Demo seeding ships postal IDs without counters.
  - [ ] Quest and character flows no longer access `.number`.
  - [ ] Migration notes documented in `docs/architecture.md`.
- **Implementation Tasks**
  - [x] Replace sequential counters with `EntityID.generate()`.
  - [x] Normalize owner/referee lookups to store `UserID.value`.
  - [ ] Sweep quest/character flows for `.number` assumptions.
  - [ ] Document guild migration notes.

#### Story EP7-S2 — Postal IDs in Telemetry

- **Status**: Planned
- **Definition of Done**
  - [ ] `send_demo_log` payloads include `quest_id.value`.
  - [ ] Logging avoids Mongo `_id`.
  - [ ] Audit fixtures updated with postal examples.
- **Implementation Tasks**
  - [ ] Update quest lifecycle logging to use `quest.quest_id.value`.
  - [ ] Refresh demo log templates and docs with postal-style examples.
  - [ ] Add regression notes in `docs/discord.md`.

## 8. Resources & Dependencies

- Framework: discord.py.
- Database: MongoDB Atlas.
- Infrastructure: Docker hosted on DigitalOcean.

## 9. Release Timeline

- [x] Milestone 1 — Bot skeleton and database setup.
- [x] Milestone 2 — Quest announcement plus sign-up automation.
- [ ] Milestone 3 — Summary linking and data tracking MVP.

## 10. Risks & Assumptions

### Risks

- Discord API limitations could block or throttle automation.
- Manual overrides by admins may introduce data inconsistency.

### Assumptions

- Single development team maintains the bot.
- Users are already familiar with Discord workflows.

## Appendix A — Experimental Branch Delta (vs `main`)

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
- [x] API schemas include `guild_id` with normalized telemetry field names (e.g., `messages_count_total`).
- [x] Documentation adds `docs/discord.md` with slash command details.
- [x] Discord intents checklist merged into `docs/architecture.md`; `docs/discord_intents.md` removed.
- [x] Migration compatibility maintained via provided utilities.
