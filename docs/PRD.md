# Jira PRD: Project *Nonagon*
This document outlines the Product Requirements Document (PRD) for the Nonagon Discord bot project. It serves as a guide for development, tracking, and managing the bot's features and functionalities.

## 0. Overview
**Project Name**: Nonagon

**Project Description**: A Discord bot for tracking member interactions, automating quest announcements, and managing player sign-ups and summaries.

**Project Owner**: Piyush Satti

**Date Created**: 17 Aug 2025

**Version**: 1.0

**Status**: Draft

**Last Updated**: 25 Aug 2025 (Roadmap refresh; see Experimental Delta below)

**Contributors**: Piyush Satti

**Contact**: piyushsatti@gmail.com

**Repository**: [GitHub - Nonagon](piyushsatti/nonagon)

## 1. Problem Statement
There are two main problems:

1. Admins do not have any data on the various activities going on in the server. Without data, insights cannot be drawn for growth.
2. Quest announcement, player sign-up management, and adventure summary tracking is a tedious process with a lot of manual labor. Automated solutions should exist to ease the burden on players and referees.

## 2. Goals

1. Deliver guided quest management inside Discord:

   * DMs draft, preview, approve, and publish quests from a forge channel.
   * Quest announcements stay up to date with roster, state, and identifiers.

2. Control enrollment while streamlining player onboarding:

   * Players request to join and await explicit DM approval.
   * First-time players register characters via a friendly modal flow.

3. Maintain supportive tooling and documentation:

   * DM-only nudges resurface quests on cooldown.
   * `/lookup` command shares reference material quickly.
   * Demo markdown keeps the "green path" discoverable for new contributors.

## 3. Stakeholders

* **Member**: Participates in community without gaming.
* **Player**: Joins games and writes player-side summaries.
* **Referee**: Hosts games, accepts signees, writes DM summaries.
* **Admin**: Full access to data and edits.

## 4. Scope & Deliverables

**In Scope**

* Data tracking of member interactions.
* Quest lifecycle automation.
* Role-based permissions (Member, Player, Referee, Admin).

**Out of Scope**

* Complex analytics dashboards.
* End-user querying of data.

## 5. Requirements
### Functional (User Stories)
* **Member**:

  * As a Member, I want polished quest embeds with clear status (Active/Closed), so I instantly know if signups remain open.

* **Player**:

  * As a Player, I want to request to join quests and receive ephemeral confirmation, so I have clarity on my signup.
  * As a Player, I want a quick modal to register my first character, so onboarding does not block participation.
  * As a Player, I want reminders and notifications to be ephemeral, so channels stay tidy.

* **Referee (DM)**:

  * As a DM, I want to draft and preview quests in a forge flow, so I can iterate before announcing.
  * As a DM, I want to accept or decline join requests, so I control the roster.
  * As a DM, I want a nudge button with cooldown, so I can re-promote quests responsibly.

* **Admin / Staff**:

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
- P1: EP1 Quest Forge Flow, EP2 Controlled Sign-Up Management, EP4 Friendly Player Registration Flow, EP3 Nudge Button, EP7 External Quest IDs
- P2: EP6 `/lookup` Command
- P3: EP5 Simple UI Improvements, EP8 Demo Markdown

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

**Story EP3-S1**  
As a DM, I want a Nudge button only I can see so I avoid confusing players.  
**Acceptance Criteria**  
Given a quest embed, When I (as DM) view it, Then a [Nudge emoji] Nudge button appears and hides for others.  
**DoD**  
- Role gate ensures DM visibility  
- Button rendered near Request controls  
- UI logged  
**Tasks**  
- Add Nudge button to QuestSignupView.  
- Filter visibility per interaction user.  
- Document button behavior in demo.

**Story EP3-S2**  
As a DM, I want nudges to respect a 48h cooldown so announcements stay tasteful.  
**Acceptance Criteria**  
Given the last nudge occurred < 48h ago, When I click Nudge, Then I see remaining cooldown; else a bump message posts referencing the quest.  
**DoD**  
- last_nudged_at stored per quest  
- Cooldown feedback returned  
- Bump message links original post  
**Tasks**  
- Add last_nudged_at field to Quest model/repo.  
- Implement POST /v1/quests/{id}:nudge handler.  
- Render bump embed referencing quest.

**Story EP3-S3**  
As a Moderator, I want nudge activity logged so I can audit outreach.  
**Acceptance Criteria**  
Given a successful nudge, When it posts, Then logs include quest_id, DM, and timestamp.  
**DoD**  
- send_demo_log invoked  
- Errors captured with context  
- Tests validate logging path  
**Tasks**  
- Tie logging into nudge success path.  
- Add unit tests using logging doubles.  
- Update moderation SOP docs.

### Epic 4: Friendly Player Registration Flow (P1)
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

**Story EP5-S1**  
As a Member, I want emoji section headers so quest embeds are scannable.  
**Acceptance Criteria**  
Given a quest embed, When rendered, Then it shows [Target emoji] Quest, [Party emoji] Players, and [Clock emoji] Time sections.  
**DoD**  
- Embed builder centralized  
- Legacy commands reuse builder  
- Snapshot tests added  
**Tasks**  
- Refactor embed builder into helper.  
- Update preview/announce flows to reuse helper.  
- Add tests verifying section headers.

**Story EP5-S2**  
As a Player, I want confirmations to be ephemeral so channels stay clean.  
**Acceptance Criteria**  
Given I interact with quest UI, When responses send, Then they're ephemeral unless broadcasting is needed.  
**DoD**  
- Audit all quest-related responses  
- Update to ephemeral where appropriate  
- Logging includes interaction outcomes  
**Tasks**  
- Review join/leave/accept flows.  
- Toggle ephemeral=True in callbacks.  
- Add integration tests.

**Story EP5-S3**  
As a Player, I want quest state cues so I know if signups are closed.  
**Acceptance Criteria**  
Given quest status changes, When embed updates, Then footer shows Active (green circle) Active or Closed (red circle) Closed with "Approved by @DM - Updated <relative time>."  
**DoD**  
- Footer template standardized  
- Triggered on Accept/Decline/Close Signups  
- Tests cover footer output  
**Tasks**  
- Implement footer builder.  
- Hook into quest state transitions.  
- Add tests for footer formatting.

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

**Story EP6-S1**  
As Staff, I want to add lookup entries so common docs stay handy.  
**Acceptance Criteria**  
Given /lookup add name:<text> url:<url>, When executed, Then the entry is stored per guild and confirmation returns.  
**DoD**  
- Upsert on (guild_id, name)  
- Staff-only permission check  
- Logging for audit  
**Tasks**  
- Create LookupCommandsCog.  
- Define Mongo lookup schema with compound index.  
- Validate URL format.

**Story EP6-S2**  
As Staff, I want /lookup get to surface the best match so I find docs fast.  
**Acceptance Criteria**  
Given a query, When requested, Then the command returns the best match (exact > prefix > contains) or a friendly miss message.  
**DoD**  
- Case-insensitive search  
- Ephemeral reply  
- Misses logged  
**Tasks**  
- Implement ranking logic.  
- Format response embed.  
- Track misses for future improvements.

**Story EP6-S3**  
As Staff, I want /lookup list so I can browse all references.  
**Acceptance Criteria**  
Given multiple entries, When I list them, Then they appear in a paginated view (<=25 per page).  
**DoD**  
- Pagination controls  
- Sorted alphabetically  
- Ephemeral to staff  
**Tasks**  
- Build pagination UI.  
- Query sorted results.  
- Add integration tests.

**Story EP6-S4**  
As Staff, I want to remove lookup entries so stale links disappear.  
**Acceptance Criteria**  
Given /lookup remove name:<text>, When executed, Then the entry is deleted or a warning returns if not found.  
**DoD**  
- Role gate enforced  
- Friendly warning on missing entry  
- Logging recorded  
**Tasks**  
- Delete by (guild_id, name).  
- Surface not-found message.  
- Hook into audit logging.

### Epic 7: External Quest IDs (P1)
**Goal**: Ensure human-readable quest IDs remain the external identifier.  
**Scope**: Audit ID usage, logging, tests.  
**Out of Scope**: Changing ID format beyond QUES0001.  
**Dependencies**: EntityID model, Mongo repository, bot cogs.  
**Milestones**: Audit -> Fix stragglers -> Tests.  
**NFRs**: No _id leakage, consistent formatting.

**Story EP7-S1**  
As a Developer, I want Quest IDs used across layers so references stay clear.  
**Acceptance Criteria**  
Given quest operations, When IDs pass through API/bot layers, Then QuestID strings are used instead of Mongo _id.  
**DoD**  
- Audit covers API, repo, bot  
- Stragglers fixed  
- Tests verify parse/format  
**Tasks**  
- Review EntityIDModel, QuestsRepoMongo, quest cog.  
- Update any _id logging.  
- Extend unit tests.

**Story EP7-S2**  
As a Moderator, I want logs to include Quest ID so investigations are simple.  
**Acceptance Criteria**  
Given quest events, When logged, Then quest_id appears with guild context.  
**DoD**  
- Logging statements updated  
- Demo log templates refreshed  
- Tests confirm formatting  
**Tasks**  
- Update log calls in quest lifecycle.  
- Adjust send_demo_log usage.  
- Add logging assertions.

**Story EP7-S3**  
As a Developer, I want regression coverage for ID parsing so errors surface early.  
**Acceptance Criteria**  
Given malformed IDs, When parsed, Then informative errors raise and tests cover them.  
**DoD**  
- Negative tests in place  
- CI protects ID parsing  
- Docs clarify ID format  
**Tasks**  
- Add failure-case tests.  
- Update docs referencing quest IDs.  
- Note migration requirements if format changes later.

### Epic 8: Demo Markdown (P3)
**Goal**: Document the "green path" flow with visuals for developers.  
**Scope**: docs/demo.md, screenshots/GIFs, doc links.  
**Out of Scope**: Video hosting.  
**Dependencies**: Completed quest flow, media assets.  
**Milestones**: Draft narrative -> Capture media -> Link docs.  
**NFRs**: Accessible, kept in sync.

**Story EP8-S1**  
As a Developer, I want docs/demo.md to narrate the happy path so onboarding is quick.  
**Acceptance Criteria**  
Given the doc, When followed, Then it covers Forge -> Approve -> Announce -> Request -> Approve -> Nudge with command samples.  
**DoD**  
- Step-by-step instructions  
- Command samples verified  
- Linked from docs index  
**Tasks**  
- Draft markdown with each step.  
- Verify commands for accuracy.  
- Update docs/index.md navigation.

**Story EP8-S2**  
As a Developer, I want screenshots/GIFs so I can visualize interactions.  
**Acceptance Criteria**  
Given each step, When viewing docs, Then an image or GIF with caption is present.  
**DoD**  
- Assets stored under docs/media/  
- Alt text provided  
- File sizes optimized  
**Tasks**  
- Capture media assets.  
- Add references in markdown.  
- Compress assets for repo.

**Story EP8-S3**  
As a Developer, I want documentation upkeep baked into process so it stays current.  
**Acceptance Criteria**  
Given future PRs, When changes ship, Then docs updates are part of DoD.  
**DoD**  
- Contribution guide/PR template updated  
- Reminder in team rituals  
- Tracking note added  
**Tasks**  
- Update contribution docs.  
- Add checklist item to PR template.  
- Monitor doc freshness periodically.

Note: Data & interface adjustments include last_nudged_at on quests, optional quick-create character schema tweaks, and a new lookup collection; coordinate migrations with release planning.

Note: Test plan spans domain (Quest/Character IDs, cooldowns), API (signups, nudge), and Discord interaction mocks; ensure regression coverage accompanies each epic.
## 8. Resources & Dependencies
* **Framework**: discord.py
* **Database**: MongoDB Atlas
* **Infra**: Docker, hosted on DigitalOcean

## 9. Timeline & Milestones
* **Milestone 1**: Bot Skeleton + DB setup
* **Milestone 2**: Quest Announcement + Sign-up Automation
* **Milestone 3**: Summary Linking + Data Tracking MVP

## 10. Risks & Assumptions
**Risks**
* Discord API limitations.
* Manual overrides by Admins may cause data inconsistency.

**Assumptions**
* Single dev team.
* Users already familiar with Discord workflows.

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



