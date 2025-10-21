# Jira PRD: Project *Nonagon*
This document outlines the Product Requirements Document (PRD) for the Nonagon Discord bot project. It serves as a guide for development, tracking, and managing the bot's features and functionalities.

## 0. Overview
**Project Name**: Nonagon

**Project Description**: A Discord bot for tracking member interactions, automating quest announcements, and managing player sign-ups and summaries.

**Project Owner**: Piyush Satti

**Date Created**: 17 Aug 2025

**Version**: 1.0

**Status**: Draft

**Last Updated**: 21 Oct 2025 (EP7 postal-style IDs + demo alignment)

**Contributors**: Piyush Satti

**Contact**: piyushsatti@gmail.com

**Repository**: [GitHub - Nonagon](piyushsatti/nonagon)

- [x] **Story EP2-S1**  
  As a Player, I want to request to join so the DM can review me.  
  **Acceptance Criteria**  
  Given I click Request to Join, When processed, Then a signup with status=APPLIED is stored and I receive an ephemeral confirmation.  
  **DoD**  
  - Role check enforced  
  - Preview button rendered with logging  
  - No persistence triggered  
  **Tasks**  
  - [x] Detect forge-channel messages in src/app/bot/cogs/QuestCommandsCog.py.  
  - [x] Attach a discord.ui.View with Preview callback.  
  - [x] Expose configurable forge channel setting.

- [x] **Story EP2-S2**  
  As a DM, I want to view pending requests so I can decide who joins.  
  **Acceptance Criteria**  
  Given APPLIED signups exist, When I open the requests panel, Then I see each applicant with Accept/Decline controls.  
  **DoD**  
  - DM-only view generated  
  - Pagination for >25 requests  
  - Errors surfaced ephemerally  
  **Tasks**  
  - [x] Implement /quest requests (slash or panel).  
  - [x] Render embed listing APPLIED players with metadata.  
  - [x] Provide custom IDs tying actions to players.

- [x] **Story EP2-S3**  
  As a DM, I want to accept a player so the roster updates automatically.  
  **Acceptance Criteria**  
  Given I click Accept, When completed, Then the signup status becomes SELECTED, the quest embed shows the player, and the player is notified.  
  **DoD**  
  - Calls POST /v1/quests/{id}/signups/{user_id}:select  
  - Embed re-rendered with SELECTED section  
  - Notification delivered ephemerally or via DM  
  **Tasks**  
  - [x] Implement Accept button callback.  
  - [x] Update embed builder to highlight SELECTED players.  
  - [x] Send friendly confirmation to player.

- [x] **Story EP2-S4**  
  As a DM, I want to decline applicants so I manage capacity.  
  **Acceptance Criteria**  
  Given I click Decline, When completed, Then the signup is removed and the player receives a decline notification.  
  **DoD**  
  - Calls DELETE /v1/quests/{id}/signups/{user_id}  
  - Embed re-rendered without applicant  
  - Decline logged  
  **Tasks**  
  - [x] Add Decline button callback.  
  - [x] Handle missing signup gracefully.  
  - [x] Send decline message ephemerally.

- [x] **Story EP2-S5**  
  As a Developer, I want duplicate protections respected so the data stays clean.  
  **Acceptance Criteria**  
  Given a player already applied, When they request again, Then an error returns and no new entry is created.  
  **DoD**  
  - Domain guard remains intact  
  - API tests cover duplicate branch  
  - Messaging localized  
  **Tasks**  
  - [x] Confirm duplicate guard in Quest.add_signup.  
  - [x] Add regression tests in tests/api/test_quests.py.  
  - [x] Improve error string for Discord surfaces.
  * As Admin/Staff, I want `/lookup` and refreshed demo docs, so onboarding others remains efficient.

### Non-Functional (Constraints)
* **Performance**: Data collection should not lag Discord.
* **Scalability**: Handle multiple concurrent players/quests.
* **Security**: Role-based access; only Admins and creators can modify stored data.
* **Reliability**: Automated flows should require minimal manual intervention.

## 6. Jira Setup
* **Issue Types**: Epic, Story, Task, Bug
* **Workflow**: To Do -> In Progress -> In Review -> Done

## 7. Epics & Stories Breakdown
**Priority Roadmap**

- P1: EP1 Quest Forge Flow, EP2 Controlled Sign-Up Management, EP3 Nudge Button, EP5 Simple UI Improvements, EP7 External Quest IDs
- P2: EP6 `/lookup` Command
- Deferred: EP4 Friendly Player Registration Flow (resume after EP5)

Note: Execute epics sequentially within their priority band to reduce Discord UI churn and repeated QA.

### Epic 1: Quest Forge Flow (P1)
**Goal**: Enable DMs to draft, preview, and finalize quests inside Discord.  
**Scope**: Forge channel previews, approve/discard buttons, publish to quest board.  
**Out of Scope**: Advanced markdown parsing, multi-message drafts.  
**Dependencies**: Quest embed builder, FastAPI quest creation endpoint.  
**Milestones**: Preview button -> Approve/Discard actions -> Thread previews -> Publish.  
**NFRs**: No DB writes until approval, idempotent discard, logged actions.

**Story EP1-S1**  
As a DM, I want a Preview button on my forge message so I can render an embed before publishing.  
**Acceptance Criteria**  
Given the forge channel, When a DM posts a quest draft, Then the bot attaches a DM-only Preview button.  
**DoD**  
- Role check enforced  
- Preview button rendered with logging  
- No persistence triggered  
**Tasks**  
- Detect forge-channel messages in src/app/bot/cogs/QuestCommandsCog.py.  
- Attach a discord.ui.View with Preview callback.  
- Expose configurable forge channel setting.

**Story EP1-S2**  
As a DM, I want the preview to reflect my latest edits so I see final formatting.  
**Acceptance Criteria**  
Given I update my draft, When I click Preview again, Then the embed refreshes with updated content and replaces older previews.  
**DoD**  
- Embed renderer reused across preview/announce  
- Preview isolated to a thread or ephemeral message  
- Errors surfaced ephemerally  
**Tasks**  
- Parse message content and hydrate quest embed.  
- Convert preview responses into auto threads.  
- Handle stale preview cleanup.

**Story EP1-S3**  
As a DM, I want Approve to publish and persist the quest so players can sign up.  
**Acceptance Criteria**  
Given a valid preview, When I click Approve, Then the quest posts to the quest board and is saved with ANNOUNCED status.  
**DoD**  
- Announcement includes signup view and Quest ID footer  
- POST /v1/quests called with channel/message IDs and raw markdown  
- Audit log entry emitted  
**Tasks**  
- Reuse persistence flow from createquest.  
- Provide guild/channel/message IDs to FastAPI.  
- Handle failures with rollback (delete preview).

**Story EP1-S4**  
As a DM, I want Discard to clean up drafts so the forge channel stays tidy.  
**Acceptance Criteria**  
Given a preview exists, When I click Discard, Then the preview and thread are deleted and no quest record is stored.  
**DoD**  
- Idempotent discard handler  
- Logging for discard action  
- Error message delivered ephemerally  
**Tasks**  
- Track preview message/thread IDs.  
- Delete associated resources on discard.  
- Gracefully handle missing preview state.

**Story EP1-S5**  
As a Developer, I want a DRAFT status so future iterations can persist drafts.  
**Acceptance Criteria**  
Given a draft quest, When stored, Then QuestStatus.DRAFT is accepted without breaking existing flows.  
**DoD**  
- Enum updated and serialized  
- Tests cover DRAFT handling  
- API responses maintain defaults for slash-created quests  
**Tasks**  
- Update QuestStatus in src/app/domain/models/QuestModel.py.  
- Adjust serialization/deserialization helpers.  
- Add regression tests in 	ests/domain/models/test_quest_model.py.

### Epic 2: Controlled Sign-Up Management (P1)
**Goal**: Let DMs approve or decline players before they join quests.  
**Scope**: Request button, review panel, Accept/Decline, embed refresh.  
**Out of Scope**: Auto waitlisting, capacity caps.  
**Dependencies**: Mongo signups, FastAPI signup endpoints.  
**Milestones**: Request flow -> Review UI -> Accept/Decline actions -> Embed sync.  
**NFRs**: Duplicate prevention, role checks, thorough logging.

**Story EP2-S1**  
As a Player, I want to request to join so the DM can review me.  
**Acceptance Criteria**  
Given I click Request to Join, When processed, Then a signup with status=APPLIED is stored and I receive an ephemeral confirmation.  
**DoD**  
- Uses POST /v1/quests/{id}/signups  
- Duplicate attempts rejected politely  
- Interaction logged  
**Tasks**  
- Rename Join button to Request to Join.  
- Map interaction to FastAPI or cache persistence.  
- Handle duplicate errors via embed follow-up.

**Story EP2-S2**  
As a DM, I want to view pending requests so I can decide who joins.  
**Acceptance Criteria**  
Given APPLIED signups exist, When I open the requests panel, Then I see each applicant with Accept/Decline controls.  
**DoD**  
- DM-only view generated  
- Pagination for >25 requests  
- Errors surfaced ephemerally  
**Tasks**  
- Implement /quest requests (slash or panel).  
- Render embed listing APPLIED players with metadata.  
- Provide custom IDs tying actions to players.

**Story EP2-S3**  
As a DM, I want to accept a player so the roster updates automatically.  
**Acceptance Criteria**  
Given I click Accept, When completed, Then the signup status becomes SELECTED, the quest embed shows the player, and the player is notified.  
**DoD**  
- Calls POST /v1/quests/{id}/signups/{user_id}:select  
- Embed re-rendered with SELECTED section  
- Notification delivered ephemerally or via DM  
**Tasks**  
- Implement Accept button callback.  
- Update embed builder to highlight SELECTED players.  
- Send friendly confirmation to player.

**Story EP2-S4**  
As a DM, I want to decline applicants so I manage capacity.  
**Acceptance Criteria**  
Given I click Decline, When completed, Then the signup is removed and the player receives a decline notification.  
**DoD**  
- Calls DELETE /v1/quests/{id}/signups/{user_id}  
- Embed re-rendered without applicant  
- Decline logged  
**Tasks**  
- Add Decline button callback.  
- Handle missing signup gracefully.  
- Send decline message ephemerally.

**Story EP2-S5**  
As a Developer, I want duplicate protections respected so the data stays clean.  
**Acceptance Criteria**  
Given a player already applied, When they request again, Then an error returns and no new entry is created.  
**DoD**  
- Domain guard remains intact  
- API tests cover duplicate branch  
- Messaging localized  
**Tasks**  
- Confirm duplicate guard in Quest.add_signup.  
- Add regression tests in 	ests/api/test_quests.py.  
- Improve error string for Discord surfaces.

### Epic 3: Nudge Button (P1)
**Goal**: Give DMs a cooldown-respecting quest bump.  
**Scope**: DM-only button, bump message, cooldown tracking.  
**Out of Scope**: Automated reminders to players.  
**Dependencies**: Quest embed builder, Mongo quest fields.  
**Milestones**: Button visibility -> Cooldown enforcement -> Logging.  
**NFRs**: 48h cooldown, idempotent logging.

- [x] **Story EP3-S1**  
  As a DM, I want a Nudge button only I can see so I avoid confusing players.  
  **Acceptance Criteria**  
  Given a quest embed, When I (as DM) view it, Then a [Nudge emoji] Nudge button appears and hides for others.  
  **DoD**  
  - Role gate ensures DM visibility  
  - Button rendered near Request controls  
  - UI logged  
  **Tasks**  
  - [x] Add Nudge button to QuestSignupView.  
  - [x] Filter visibility per interaction user.  
  - [x] Document button behavior in demo.

- [x] **Story EP3-S2**  
  As a DM, I want nudges to respect a 48h cooldown so announcements stay tasteful.  
  **Acceptance Criteria**  
  Given the last nudge occurred < 48h ago, When I click Nudge, Then I see remaining cooldown; else a bump message posts referencing the quest.  
  **DoD**  
  - last_nudged_at stored per quest  
  - Cooldown feedback returned  
  - Bump message links original post  
  **Tasks**  
  - [x] Add last_nudged_at field to Quest model/repo.  
  - [x] Implement POST /v1/quests/{id}:nudge handler.  
  - [x] Render bump embed referencing quest.

- [x] **Story EP3-S3**  
  As a Moderator, I want nudge activity logged so I can audit outreach.  
  **Acceptance Criteria**  
  Given a successful nudge, When it posts, Then logs include quest_id, DM, and timestamp.  
  **DoD**  
  - send_demo_log invoked  
  - Errors captured with context  
  - Tests validate logging path  
  **Tasks**  
  - [x] Tie logging into nudge success path.  
  - [x] Add unit tests using logging doubles.  
  - [x] Update moderation SOP docs.

### Epic 4: Friendly Player Registration Flow (Deferred)

> **Status**: Paused. Resume after Epic 5 completes; keep stories in backlog for future planning.
**Goal**: Onboard first-time players without friction.  
**Scope**: Character detection, quick-create modal, auto-continue signup.  
**Out of Scope**: Full character profile capture in quick flow.  
**Dependencies**: Characters repo, quest signup interactions.  
**Milestones**: Detection -> Modal -> Persist -> Continue signup.  
**NFRs**: Minimal required fields, owner scoping, error resilience.

**Story EP4-S1**  
As a Player, I want the bot to detect I lack characters so I can register fast.  
**Acceptance Criteria**  
Given I have no characters, When I click Request to Join, Then a modal prompts for character name.  
**DoD**  
- Character lookup by owner_id  
- Modal shown once per interaction  
- Logging includes quest/player  
**Tasks**  
- Extend QuestSignupView to query guild cache.  
- Present quick-register modal.  
- Handle parallel requests.

**Story EP4-S2**  
As a Player, I want to quick-create a character so my signup continues automatically.  
**Acceptance Criteria**  
Given I submit the modal, When creation succeeds, Then a character record is stored with defaults and I see "[Check emoji] <name> registered."  
**DoD**  
- Character persisted with minimal fields  
- created_at set  
- Errors surfaced ephemerally  
**Tasks**  
- Add quick-create helper (API or direct Mongo write).  
- Relax validation or provide placeholder links.  
- Store guild_id/owner_id properly.

**Story EP4-S3**  
As a Player, I want the request to resume after registration so I avoid re-clicking.  
**Acceptance Criteria**  
Given quick-create succeeds, When the modal closes, Then my signup is submitted as APPLIED automatically.  
**DoD**  
- Signup triggered after character creation  
- Failure recovery informs user  
- Telemetry recorded  
**Tasks**  
- Chain modal completion to signup logic.  
- Provide fallback instructions on failure.  
- Track adoption metrics.

**Story EP4-S4**  
As a returning Player, I want a dropdown of my characters so I pick the right one.  
**Acceptance Criteria**  
Given I have characters, When I request to join, Then the dropdown lists my characters (max 25) with name + ID.  
**DoD**  
- Dropdown options generated from guild cache  
- Fallback to modal when none available  
- Tests cover select population  
**Tasks**  
- Reuse CharacterSelect with improved labels.  
- Add tests to ensure fallback path works.  
- Update docs describing dropdown behavior.

### Epic 5: Simple UI Improvements (P3)
**Goal**: Polish embeds and interactions without changing business logic.  
**Scope**: Emoji headers, state cues, thread previews, ephemeral confirmations.  
**Out of Scope**: Theming beyond Discord defaults.  
**Dependencies**: Embed builder, quest lifecycle handlers.  
**Milestones**: Embed polish -> Role gating -> State cues -> Thread previews.  
**NFRs**: No regression to existing commands.

- [x] **Story EP5-S1**  
  As a Member, I want emoji section headers so quest embeds are scannable.  
  **Acceptance Criteria**  
  Given a quest embed, When rendered, Then it shows [Target emoji] Quest, [Party emoji] Players, and [Clock emoji] Time sections.  
  **DoD**  
  - Embed builder centralized  
  - Legacy commands reuse builder  
  - Snapshot tests added  
  **Tasks**  
  - [x] Refactor embed builder into helper.  
  - [x] Update preview/announce flows to reuse helper.  
  - [x] Add tests verifying section headers.

**Story EP5-S2**  
As a Player, I want confirmations to be ephemeral so channels stay clean.  
**Acceptance Criteria**  
Given I interact with quest UI, When responses send, Then they're ephemeral unless broadcasting is needed.  
**DoD**  
- Audit all quest-related responses  
- Update to ephemeral where appropriate  
- Logging includes interaction outcomes  
**Tasks**  
- [x] Review join/leave/accept flows (audit confirmed existing ephemeral responses).  
- [x] Add regression tests so `/joinquest` and `/leavequest` confirmations stay ephemeral (`tests/bot/test_quest_commands_ephemeral.py`).  
  - [x] Extend coverage to review/decision panels and logging states.

- [x] **Story EP5-S3**  
  As a Player, I want quest state cues so I know if signups are closed.  
  **Acceptance Criteria**  
  Given quest status changes, When embed updates, Then the footer shows "Active" with a green circle or "Closed" with a red circle alongside "Approved by referee name - Updated with a relative timestamp."  
  **DoD**  
  - Footer template standardized  
  - Triggered on Accept/Decline/Close signups  
  - Tests cover footer output  
  **Tasks**  
  - [x] Implement footer builder.  
  - [x] Hook into quest state transitions.  
  - [x] Add tests for footer formatting.

**Story EP5-S4**  
As a DM, I want previews in threads so the forge channel stays tidy.  
**Acceptance Criteria**  
Given I click Preview, When the preview posts, Then it lives in an auto-created thread cleaned up on Approve/Discard.  
**DoD**  
- Thread handling with fallback  
- Cleanup on finalize/discard  
- Errors surfaced ephemerally  
**Tasks**  
- Use message.create_thread for preview hosting.  
- Track thread IDs for cleanup.  
- Handle permission failures gracefully.

### Epic 6: /lookup Command (P2)
**Goal**: Offer lightweight reference search for staff.  
**Scope**: Add/get/list/remove commands, per-guild storage.  
**Out of Scope**: Full-text fuzzy search beyond basics.  
**Dependencies**: Mongo collection, new bot cog.  
**Milestones**: Storage schema -> Command set -> Pagination -> Auditing.  
**NFRs**: Role-guarded, reliable responses.

- [x] **Story EP6-S1**  
As Staff, I want to add lookup entries so common docs stay handy.  
**Acceptance Criteria**  
Given /lookup add name:<text> url:<url>, When executed, Then the entry is stored per guild and confirmation returns.  
**DoD**  
- Upsert on (guild_id, name)  
- Staff-only permission check  
- Logging for audit  
**Tasks**  
- [x] Create LookupCommandsCog.  
- [x] Define Mongo lookup schema with compound index.  
- [x] Validate URL format.
  
- [x] **Story EP6-S2**  
As Staff, I want /lookup get to surface the best match so I find docs fast.  
**Acceptance Criteria**  
Given a query, When requested, Then the command returns the best match (exact > prefix > contains) or a friendly miss message.  
**DoD**  
- Case-insensitive search  
- Ephemeral reply  
- Misses logged  
**Tasks**  
- [x] Implement ranking logic.  
- [x] Format response embed.  
- [x] Track misses for future improvements.
  
- [x] **Story EP6-S3**  
As Staff, I want /lookup list so I can browse all references.  
**Acceptance Criteria**  
Given multiple entries, When I list them, Then they appear in a paginated view (<=25 per page).  
**DoD**  
- Pagination controls  
- Sorted alphabetically  
- Ephemeral to staff  
**Tasks**  
- [x] Build pagination UI.  
- [x] Query sorted results.  
- [x] Add integration tests.
  
- [x] **Story EP6-S4**  
As Staff, I want to remove lookup entries so stale links disappear.  
**Acceptance Criteria**  
Given /lookup remove name:<text>, When executed, Then the entry is deleted or a warning returns if not found.  
**DoD**  
- Role gate enforced  
- Friendly warning on missing entry  
- Logging recorded  
**Tasks**  
- [x] Delete by (guild_id, name).  
- [x] Surface not-found message.  
- [x] Hook into audit logging.

### Epic 7: External Quest IDs (P1)
**Goal**: Preserve readable quest IDs while migrating every entity to the new postal-style `PREFIX` + `L#L#L#` format across API, bot, and demo tooling.  
**Scope**: Postal generator, repository filters, logging alignment, demo seeding, regression tests.  
**Out of Scope**: Changing entity prefixes or dropping legacy numeric parsing (defer to post-release cleanup).  
**Dependencies**: EntityID model, Mongo repositories, quest/character cogs, demo commands, telemetry logging.  
**Milestones**: Generator + compatibility -> Persistence rewrite -> Logging cleanup -> Regression test suite.  
**NFRs**: Collision detection, backward compatibility with numeric IDs, no Mongo `_id` leakage.

- [ ] **Story EP7-S1**  
  As a Developer, I want postal-style IDs flowing end-to-end so Discord links and API payloads stay human-readable.  
  **Acceptance Criteria**  
  Given quest/character/summary operations, When IDs are generated or persisted, Then they use the postal-style body (`QUESH3X1T7`, etc.) while still parsing legacy numeric values without crashes.  
  **DoD**  
  - EntityIDModel generates postal bodies and normalizes legacy values.  
  - Repositories store/query against `*.value` instead of `.number`/`_id`.  
  - Demo seeding ships postal IDs without counters.  
  **Tasks**  
  - [x] Replace sequential counters with `EntityID.generate()` in repos and demo seeding.  
  - [x] Normalize owner/referee lookups to store `UserID.value`.  
  - [ ] Sweep quest/character flows to remove `.number` accesses that assume numeric IDs.  
  - [ ] Document migration notes for legacy guild data in docs/architecture.md.

- [ ] **Story EP7-S2**  
  As a Moderator, I want logs and telemetry streams to surface the postal IDs so investigations reference a single identifier.  
  **Acceptance Criteria**  
  Given quest lifecycle events, When they are logged or broadcast, Then the postal `QuestID` value appears alongside the guild context in both Discord and log_stream telemetry.  
  **DoD**  
  - send_demo_log payloads include `quest_id.value`.  
  - Quest/character actions avoid logging Mongo `_id`.  
  - Audit trail in logs/test fixtures updated.  
  **Tasks**  
  - [ ] Update quest lifecycle logging to use `quest.quest_id.value`.  
  - [ ] Refresh demo log templates and docs with postal-style examples.  
  - [ ] Add regression notes in docs/discord.md.

- [ ] **Story EP7-S3**  
  As a Developer, I want regression coverage for ID parsing so malformed IDs fail fast.  
  **Acceptance Criteria**  
  Given invalid ID strings, When parsed, Then descriptive errors raise and tests assert the behavior across all `EntityID` subclasses.  
  **DoD**  
  - Unit tests cover valid/invalid postal bodies and legacy numeric parsing.  
  - CI enforces rejection of short/unsupported prefixes.  
  - Docs detail the accepted patterns for contributors.  
  **Tasks**  
  - [ ] Add pytest coverage in `tests/domain/models` for postal vs numeric bodies.  
  - [ ] Update contributor checklist/PR template with ID-format reminder.  
  - [ ] Call out postal-style format in `docs/API.md` and `docs/discord.md`.

### Epic 8: Demo Markdown (P3)

**Goal**: Document the "green path" flow with visuals for developers.
**Scope**: docs/demo.md, screenshots/GIFs, doc links.
**Out of Scope**: Video hosting.
**Dependencies**: Completed quest flow, media assets.
**Milestones**: Draft narrative -> Capture media -> Link docs.
**NFRs**: Accessible, kept in sync.

**Story EP8-S1**
As a Developer, I want docs/demo.md to narrate the happy path so onboarding is quick.
**Acceptance Criteria:**
Given the doc, When followed, Then it covers Forge -> Approve -> Announce -> Request -> Approve -> Nudge with command samples.
**DoD:**

- Step-by-step instructions
- Command samples verified
- Linked from docs index

**Tasks:**

- Draft markdown with each step.
- Verify commands for accuracy.
- Update docs/index.md navigation.

**Story EP8-S2**
As a Developer, I want screenshots/GIFs so I can visualize interactions.
**Acceptance Criteria:**
Given each step, When viewing docs, Then an image or GIF with caption is present.
**DoD:**

- Assets stored under docs/media/
- Alt text provided
- File sizes optimized

**Tasks:**

- Capture media assets.
- Add references in markdown.
- Compress assets for repo.

**Story EP8-S3**
As a Developer, I want documentation upkeep baked into process so it stays current.
**Acceptance Criteria:**
Given future PRs, When changes ship, Then docs updates are part of DoD.
**DoD:**

- Contribution guide/PR template updated
- Reminder in team rituals
- Tracking note added

**Tasks:**

- Update contribution docs.
- Add checklist item to PR template.
- Monitor doc freshness periodically.

Note: Data & interface adjustments include last_nudged_at on quests, optional quick-create character schema tweaks, and a new lookup collection; coordinate migrations with release planning.

Note: Test plan spans domain (Quest/Character IDs, cooldowns), API (signups, nudge), and Discord interaction mocks; ensure regression coverage accompanies each epic.

## 8. Resources & Dependencies

- **Framework**: discord.py
- **Database**: MongoDB Atlas
- **Infra**: Docker, hosted on DigitalOcean

## 9. Timeline & Milestones

- **Milestone 1**: Bot Skeleton + DB setup
- **Milestone 2**: Quest Announcement + Sign-up Automation
- **Milestone 3**: Summary Linking + Data Tracking MVP

## 10. Risks & Assumptions

### Risks

- Discord API limitations.
- Manual overrides by Admins may cause data inconsistency.

### Assumptions

- Single dev team.
- Users already familiar with Discord workflows.

---

## Appendix A: Experimental Branch Delta (vs main)

This branch introduces multi-guild scoping, guild-aware APIs, and data migration utilities. Differences from main:

- Multi-guild data model and storage
  - Added `guild_id` to domain models (User, Character, Quest, Summary) and to all MongoDB documents.
  - Repositories and queries updated to filter by `guild_id` to prevent cross-guild collisions.
  - Sync adapters (flush paths) now upsert with compound filters including `guild_id`.
  - Per-guild compound indexes created for users, quests, and characters.

- Migration utilities
  - New script `scripts/migrations/backfill_guild_id.py` to populate `guild_id` on legacy documents and ensure indexes.

- Bot cache and persistence
  - `Nonagon.guild_data` and the background flush loop operate per-guild.
  - Cache loader prefers documents with `guild_id`, falls back to legacy data for bootstrap.

- Slash commands & cogs
  - All quest/character/statistics operations explicitly scope to the interaction guild.
  - Diagnostics and demo utilities updated to honor guild scoping.

- Public API changes
  - Introduced guild-scoped Users routes under `/v1/guilds/{guild_id}/users` with create/read/update/delete and role toggles.
  - API schemas updated to include `guild_id` and normalized telemetry field names (`messages_count_total`, etc.).

- Documentation
  - New `docs/discord.md` enumerates all slash commands, inputs, permissions, outputs, and logging.
  - Folded the Discord Intents checklist into `docs/architecture.md`; removed `docs/discord_intents.md`.

Note: Main branch retains single-guild assumptions and non-scoped API shapes; this branch is compatible with legacy data via the provided migration.



