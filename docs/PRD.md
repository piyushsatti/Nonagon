# Jira PRD: Project *Nonagon*
This document outlines the Product Requirements Document (PRD) for the Nonagon Discord bot project. It serves as a guide for development, tracking, and managing the bot's features and functionalities.

## 0. Overview
**Project Name**: Nonagon

**Project Description**: A Discord bot for tracking member interactions, automating quest announcements, and managing player sign-ups and summaries.

**Project Owner**: Piyush Satti

**Date Created**: 17 Aug 2025

**Version**: 1.0

**Status**: Draft

**Last Updated**: 24 Aug 2025

**Contributors**: Piyush Satti

**Contact**: piyushsatti@gmail.com

**Repository**: [GitHub - Nonagon](piyushsatti/nonagon)

## 1. Problem Statement
There are two main problems:

1. Admins do not have any data on the various activities going on in the server. Without data, insights cannot be drawn for growth.
2. Quest announcement, player sign-up management, and adventure summary tracking is a tedious process with a lot of manual labor. Automated solutions should exist to ease the burden on players and referees.

## 2. Goals

1. Provide in-depth data tracking for insights:

   * Track member interactions (frequency, participation, quests hosted, summaries written).
   * Store data on quests and summaries.

2. Automate quest processes:

   * Players sign up with characters.
   * Referees pick signees.
   * Summaries auto-link to relevant outlets.

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

  * As a Member, I want to view quests without signing up, so I can stay engaged.

* **Player**:

  * As a Player, I want to sign up with any of my characters, so I can participate easily.
  * As a Player, I want to publish adventure summaries, so others can reference past quests.
  * As a Player, I want my quest announcements to show up in a website.

* **Referee**:

  * As a Referee, I want to create quest posts where players can sign up.
  * As a Referee, I want to select players from signees, so I can manage my game efficiently.
  * As a Referee, I want to create DM summaries hidden from players.

* **Admin**:

  * As an Admin, I want to track participation data, so I can measure server growth.

### Non-Functional (Constraints)
* **Performance**: Data collection should not lag Discord.
* **Scalability**: Handle multiple concurrent players/quests.
* **Security**: Role-based access; only Admins and creators can modify stored data.
* **Reliability**: Automated flows should require minimal manual intervention.

## 6. Jira Setup
* **Issue Types**: Epic, Story, Task, Bug
* **Workflow**: To Do → In Progress → In Review → Done

## 7. Epics & Stories Breakdown

### Epic 1: Data Tracking *(In Progress)*

* [ ] **Story 1**: As an Admin, I want to track how often members interact (messages, participation).
  * [ ] Subtask 1.1: Define DB schema for storing message counts and activity frequency.
  * [ ] Subtask 1.2: Implement Discord event listeners for message tracking.
  * [ ] Subtask 1.3: Write aggregation logic for weekly/monthly activity reports.
  * [ ] Subtask 1.4: Add admin-only command to fetch interaction data.
* [ ] **Story 2**: As an Admin, I want to track how many quests each member plays/hosts.
  * [ ] Subtask 2.1: Extend DB schema to track quests joined vs. hosted.
  * [ ] Subtask 2.2: Capture participation events when users join quests.
  * [ ] Subtask 2.3: Capture hosting events when referees create quests.
  * [ ] Subtask 2.4: Build summary query for quests per user.
* [ ] **Story 3**: As an Admin, I want data on summaries written (player/referee).
  * [ ] Subtask 3.1: Extend DB schema to store summaries by type (player/referee).
  * [ ] Subtask 3.2: Implement tracking hook when summaries are posted.
  * [ ] Subtask 3.3: Generate reports linking summaries back to quests.

### Epic 2: Quest Automation ✅ *(Completed — backed by `QuestIngestionService`, quest use cases, and Discord signup flows)*

* [x] **Story 1**: As a Referee, I want to create quest posts for player sign-ups.
  * [x] Subtask 1.1: Define DB schema for quest objects (title, description, referee, status).
  * [x] Subtask 1.2: Create Discord command to generate quest posts.
  * [x] Subtask 1.3: Implement embed message formatting for quests.
  * [x] Subtask 1.4: Save quest metadata into database.
* [x] **Story 2**: As a Player, I want to sign up with any character.
  * [x] Subtask 2.1: Create schema for player characters linked to Discord ID.
  * [x] Subtask 2.2: Build sign-up flow (reaction/button-based).
  * [x] Subtask 2.3: Store sign-ups in DB.
  * [x] Subtask 2.4: Error handling for duplicate sign-ups.
* [x] **Story 3**: As a Referee, I want to select players from signees.
  * [x] Subtask 3.1: Implement UI (Discord dropdown/buttons) for selecting players.
  * [x] Subtask 3.2: Update quest status with selected players.
  * [x] Subtask 3.3: Store selection results in DB.
  * [x] Subtask 3.4: Notify selected players automatically.
* [x] **Story 4**: As a Member, I want to view quest posts without signing up.
  * [x] Subtask 4.1: Publicly display quests in designated channel.
  * [x] Subtask 4.2: Restrict actions for non-players (view-only).

### Epic 3: Summaries & Linking ✅ *(Completed — delivered via `AdventureSummaryIngestionService` and summary use cases)*

* [x] **Story 1**: As a Player, I want to publish summaries linked to quests.
  * [x] Subtask 1.1: Extend quest schema to accept player summary links.
  * [x] Subtask 1.2: Create command/button for submitting summaries.
  * [x] Subtask 1.3: Auto-link summary to relevant quest.
  * [x] Subtask 1.4: Confirmation message to player after submission.
* [x] **Story 2**: As a Referee, I want to create DM-only summaries.
  * [x] Subtask 2.1: Add schema field for DM-only summaries.
  * [x] Subtask 2.2: Create restricted command for Referees.
  * [x] Subtask 2.3: Ensure DM summaries hidden from Players.
* [x] **Story 3**: As an Admin, I want summaries linked automatically to quests and outlets.
  * [x] Subtask 3.1: Implement auto-linking logic across DB + Discord.
  * [x] Subtask 3.2: Set up integration for posting summaries to relevant channels/outlets.
  * [ ] Subtask 3.3: Build admin command to audit summary-to-quest links. *(Pending: add explicit admin audit command.)*

### Epic 4: Frontend for Quests *(Not Started)*

* [ ] **Story 1**: As a Player, I want to view current/old quests on a website.
  * [ ] Subtask 1.1: Define API schema for fetching quests and summaries.
  * [ ] Subtask 1.2: Set up basic frontend project structure.
  * [ ] Subtask 1.3: Implement integration with backend API.
  * [ ] Subtask 1.4: Host frontend on a Vercel app.
  * [ ] Subtask 1.5: Integrate with `smokebombstudios.com`.

### Cross-Epic Tasks (Ops/Infra)

* [x] **Task 1**: Setup project repo and CI/CD pipeline.
* [x] **Task 2**: Containerize with Docker and configure deployment on DigitalOcean.
* [x] **Task 3**: Implement environment configs (API keys, DB URIs, secrets).
* [x] **Task 4**: Write initial unit tests for Discord commands.
* [x] **Task 5**: Monitoring & logging setup.

### Future Epics (Backlog Seeds)

* Epic 5 (Planned): Analytics dashboards & self-serve reports.
* Epic 6 (Planned): Player portal / character management UX refresh.
* Epic 7 (Planned): Live operations tooling (forced resync, incident recovery).

## 8. Resources & Dependencies

* **Framework**: discord.py
* **Database**: MongoDB Atlas
* **Infra**: Docker, hosted on DigitalOcean

## 9. Timeline & Milestones

* **Milestone 1**: Bot Skeleton + DB setup
* **Milestone 2**: Quest Announcement + Sign-up Automation
* **Milestone 3**: Summary Linking + Data Tracking MVP

## 10. Risks & Assumptions

### Risks

* Discord API limitations.
* Manual overrides by Admins may cause data inconsistency.

### Assumptions

* Single dev team.
* Users already familiar with Discord workflows.

