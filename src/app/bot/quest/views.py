from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import discord

from app.bot.quest.models import ForgePreviewState, parse_forge_draft
from app.bot.utils.log_stream import send_demo_log
from app.domain.models.EntityIDModel import CharacterID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, PlayerStatus, Quest

if TYPE_CHECKING:
    from app.bot.quest.service import QuestService

NO_PENDING_REQUESTS_LABEL = "No pending requests"


class ForgeDraftView(discord.ui.View):
    def __init__(self, service: "QuestService", message: discord.Message) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.guild_id = message.guild.id if message.guild else 0
        self.channel_id = message.channel.id
        self.message_id = message.id
        self.author_id = message.author.id

    async def _ensure_referee(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Forge actions are only available inside a guild.", ephemeral=True
            )
            return False

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the draft author can manage this quest.", ephemeral=True
            )
            return False

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Only guild members can manage forge drafts.", ephemeral=True
            )
            return False

        try:
            user = await self.service.get_cached_user(interaction.user)
        except Exception:
            await interaction.response.send_message(
                "Unable to resolve your profile; please try again shortly.",
                ephemeral=True,
            )
            return False

        if not user.is_referee:
            await interaction.response.send_message(
                "You need the REFEREE role to manage quests.", ephemeral=True
            )
            return False

        return True

    async def _resolve_message(self, interaction: discord.Interaction) -> Optional[discord.Message]:
        channel = interaction.guild.get_channel(self.channel_id) if interaction.guild else None
        if channel is None and interaction.guild is not None:
            try:
                channel = await interaction.guild.fetch_channel(self.channel_id)
            except Exception:
                return None

        if channel is None:
            return None

        try:
            return await channel.fetch_message(self.message_id)
        except Exception:
            return None

    def _preview_state(self) -> ForgePreviewState:
        return self.service.forge_preview_state(self.guild_id, self.message_id)

    async def _resolve_thread(
        self,
        interaction: discord.Interaction,
        message: discord.Message,
        state: ForgePreviewState,
    ) -> Optional[discord.Thread]:
        guild = interaction.guild
        if guild is None:
            return None

        thread: Optional[discord.Thread] = None
        if state.thread_id:
            thread = guild.get_thread(state.thread_id)
            if thread is None:
                try:
                    fetched = await guild.fetch_channel(state.thread_id)
                except Exception:
                    fetched = None
                if isinstance(fetched, discord.Thread):
                    thread = fetched

        if thread is not None:
            return thread

        try:
            name = f"Quest Preview {interaction.user.display_name}"[:90]
            thread = await message.create_thread(name=name, auto_archive_duration=60)
        except Exception:
            return None

        state.thread_id = thread.id
        return thread

    async def _send_preview_to_thread(
        self,
        thread: discord.Thread,
        state: ForgePreviewState,
        embed: discord.Embed,
    ) -> Optional[str]:
        try:
            if state.preview_message_id:
                preview_message = await thread.fetch_message(state.preview_message_id)
                await preview_message.edit(embed=embed, content=None)
            else:
                preview_message = await thread.send(embed=embed)
                state.preview_message_id = preview_message.id
        except Exception:
            try:
                preview_message = await thread.send(embed=embed)
                state.preview_message_id = preview_message.id
            except Exception:
                return None

        state.last_rendered_at = datetime.now(timezone.utc)
        return thread.jump_url

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.primary)
    async def preview_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._ensure_referee(interaction):
            return

        message = await self._resolve_message(interaction)
        if message is None:
            await interaction.response.send_message(
                "Unable to locate the draft message.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        draft = parse_forge_draft(message.content)
        quest_id = f"DRAFT{self.message_id}"
        embed = self.service.build_draft_embed(
            draft,
            quest_id=quest_id,
            referee_display=interaction.user.mention,
        )

        state = self._preview_state()
        thread = await self._resolve_thread(interaction, message, state)
        preview_link = None
        if thread is not None:
            preview_link = await self._send_preview_to_thread(thread, state, embed)

        if preview_link:
            await interaction.followup.send(
                f"Preview updated in [thread]({preview_link}).", ephemeral=True
            )
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._ensure_referee(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await self._resolve_message(interaction)
        if message is None or interaction.guild is None:
            await interaction.followup.send(
                "Unable to locate the draft message for approval.", ephemeral=True
            )
            return

        draft = parse_forge_draft(message.content)

        try:
            result = await self.service.approve_forge_draft(
                interaction,
                draft=draft,
                author=interaction.user,
                source_message=message,
            )
        except Exception as exc:
            logging.exception("Forge approve failed: %s", exc)
            await interaction.followup.send(
                "Quest approval failed; please try again later.", ephemeral=True
            )
            return

        if result is None:
            await interaction.followup.send(
                "Quest approval aborted; please review the draft details.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(result, ephemeral=True)

    @discord.ui.button(label="Discard", style=discord.ButtonStyle.danger)
    async def discard_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not await self._ensure_referee(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await self._resolve_message(interaction)
        if message is None:
            await interaction.followup.send("Draft already removed.", ephemeral=True)
            return

        await self.service.discard_forge_draft(interaction, source_message=message)
        await interaction.followup.send("Draft discarded.", ephemeral=True)


class JoinQuestModal(discord.ui.Modal):
    def __init__(self, service: "QuestService", quest_id: str) -> None:
        super().__init__(title=f"Join {quest_id}")
        self.service = service
        self.quest_id = quest_id
        self.character_input = discord.ui.TextInput(
            label="Character ID",
            placeholder="CHAR0001",
            min_length=5,
            max_length=20,
        )
        self.add_item(self.character_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            quest_id_obj = QuestID.parse(self.quest_id)
            char_id_obj = CharacterID.parse(self.character_input.value.strip().upper())
            message = await self.service.execute_join(
                interaction, quest_id_obj, char_id_obj
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send(message, ephemeral=True)


class QuestSignupView(discord.ui.View):
    def __init__(self, service: "QuestService", quest_id: Optional[str] = None) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.quest_id = quest_id

    def _resolve_quest_id(self, interaction: discord.Interaction) -> str:
        if self.quest_id:
            return self.quest_id

        if interaction.message and interaction.message.embeds:
            footer = interaction.message.embeds[0].footer.text or ""
            match = re.search(r"Quest ID:\s*(\w+)", footer)
            if match:
                return match.group(1)
        raise ValueError("Unable to determine quest id from message.")

    @discord.ui.button(
        label="Request to Join",
        style=discord.ButtonStyle.success,
        custom_id="quest_signup:join",
    )
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            quest_id = self._resolve_quest_id(interaction)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                "Unable to resolve characters outside a guild.", ephemeral=True
            )
            return

        class _EphemeralJoin(discord.ui.View):
            def __init__(
                self, service: "QuestService", quest_id: str, member: discord.Member
            ):
                super().__init__(timeout=60)
                self.add_item(CharacterSelect(service, quest_id, member))

        await interaction.response.send_message(
            "Select your character to request a spot:",
            view=_EphemeralJoin(self.service, quest_id, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Review Requests",
        style=discord.ButtonStyle.secondary,
        custom_id="quest_signup:review",
    )
    async def review_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            quest_id_raw = self._resolve_quest_id(interaction)
            quest_id = QuestID.parse(quest_id_raw)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                "Unable to review requests outside a guild.", ephemeral=True
            )
            return

        try:
            reviewer = await self.service.get_cached_user(interaction.user)
        except Exception:
            await interaction.response.send_message(
                "Unable to resolve your profile; please try again shortly.",
                ephemeral=True,
            )
            return

        if not reviewer.is_referee:
            await interaction.response.send_message(
                "Only referees can review quest requests.", ephemeral=True
            )
            return

        quest = self.service.fetch_quest(interaction.guild.id, quest_id)
        if quest is None:
            await interaction.response.send_message(
                "Quest not found; please refresh the announcement.",
                ephemeral=True,
            )
            return

        pending = [s for s in quest.signups if s.status is not PlayerStatus.SELECTED]
        if not pending and not quest.is_signup_open:
            await interaction.response.send_message(
                "No pending requests and signups are already closed.",
                ephemeral=True,
            )
            return

        view = SignupDecisionView(
            service=self.service,
            guild=interaction.guild,
            quest=quest,
            reviewer=interaction.user,
            pending=pending,
        )

        await interaction.response.send_message(
            view.render_panel_text(), view=view, ephemeral=True
        )

    @discord.ui.button(
        label="Nudge",
        style=discord.ButtonStyle.primary,
        custom_id="quest_signup:nudge",
        emoji="🔔",
        row=1,
    )
    async def nudge_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            quest_id_raw = self._resolve_quest_id(interaction)
            quest_id = QuestID.parse(quest_id_raw)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await self.service.execute_nudge(interaction, quest_id)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(
        label="Leave Quest",
        style=discord.ButtonStyle.danger,
        custom_id="quest_signup:leave",
    )
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            quest_id = self._resolve_quest_id(interaction)
            quest_id_obj = QuestID.parse(quest_id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await self.service.execute_leave(interaction, quest_id_obj)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send(message, ephemeral=True)


class CharacterSelect(discord.ui.Select):
    def __init__(self, service: "QuestService", quest_id: str, member: discord.Member):
        self.service = service
        self.quest_id = quest_id
        self.member = member
        guild_entry = service.bot.guild_data.get(member.guild.id)
        options: list[discord.SelectOption] = []
        if guild_entry is not None:
            db = guild_entry["db"]
            owner_id = str(UserID.from_body(str(member.id)))
            cursor = (
                db["characters"]
                .find(
                    {"owner_id.value": owner_id},
                    {"_id": 0, "character_id": 1, "name": 1},
                )
                .limit(25)
            )
            for doc in cursor:
                cid = doc.get("character_id", {})
                if isinstance(cid, dict):
                    if "value" in cid:
                        label = cid["value"]
                    else:
                        label = f"{cid.get('prefix', 'CHAR')}{cid.get('number', '')}"
                else:
                    label = str(cid)
                name = doc.get("name") or label
                options.append(
                    discord.SelectOption(label=f"{label} — {name}", value=label)
                )

        super().__init__(
            placeholder="Choose your character…",
            min_values=1,
            max_values=1,
            options=options
            or [discord.SelectOption(label="Enter ID via modal", value="__MODAL__")],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        value = self.values[0]
        if value == "__MODAL__":
            await interaction.response.send_modal(
                JoinQuestModal(self.service, self.quest_id)
            )
            return

        try:
            quest_id_obj = QuestID.parse(self.quest_id)
            char_id_obj = CharacterID.parse(value)
            message = await self.service.execute_join(
                interaction, quest_id_obj, char_id_obj
            )
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message(message, ephemeral=True)


class SignupDecisionView(discord.ui.View):
    def __init__(
        self,
        *,
        service: "QuestService",
        guild: discord.Guild,
        quest: Quest,
        reviewer: discord.Member,
        pending: List[PlayerSignUp],
    ) -> None:
        super().__init__(timeout=120)
        self.service = service
        self.guild = guild
        self.quest = quest
        self.reviewer = reviewer
        self.pending_signups: List[PlayerSignUp] = list(pending)
        self.pending_map: dict[str, PlayerSignUp] = {
            str(signup.user_id): signup for signup in self.pending_signups
        }
        self.selected_user_id: Optional[str] = None

        self.select = SignupPendingSelect(self)
        self.add_item(self.select)
        self.accept_button = SignupApproveButton()
        self.decline_button = SignupDeclineButton()
        self.add_item(self.accept_button)
        self.add_item(self.decline_button)
        self.close_button = SignupCloseButton()
        self.add_item(self.close_button)

        self._refresh_from_quest()

    def render_panel_text(self) -> str:
        quest_name = self.quest.title or str(self.quest.quest_id)
        lines = [f"Pending requests for `{quest_name}`:"]
        if not self.pending_signups:
            lines.append("All requests have been reviewed.")
            if self.quest.is_signup_open:
                lines.append("You can close signups once the roster looks right.")
            if not self.quest.is_signup_open:
                lines.append("Signups are currently closed for this quest.")
            return "\n".join(lines)

        if not self.quest.is_signup_open:
            lines.append("Signups are currently closed for this quest.")

        for signup in self.pending_signups:
            marker = "->" if str(signup.user_id) == self.selected_user_id else "- "
            label = self.service.format_signup_label(self.guild.id, signup)
            lines.append(f"{marker} {label}")
        return "\n".join(lines)

    def _build_options(self) -> List[discord.SelectOption]:
        options: List[discord.SelectOption] = []
        for signup in self.pending_signups[:25]:
            user_id_str = str(signup.user_id)
            label = self.service.format_signup_label(self.guild.id, signup)
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=user_id_str,
                    default=user_id_str == self.selected_user_id,
                )
            )
        return options

    def _refresh_from_quest(self) -> None:
        self.pending_signups = [
            signup
            for signup in self.quest.signups
            if signup.status is not PlayerStatus.SELECTED
        ]
        self.pending_map = {
            str(signup.user_id): signup for signup in self.pending_signups
        }

        if self.selected_user_id and self.selected_user_id not in self.pending_map:
            self.selected_user_id = None

        if not self.selected_user_id and self.pending_signups:
            self.selected_user_id = str(self.pending_signups[0].user_id)

        options = self._build_options()
        if not options:
            self.select.options = [
                discord.SelectOption(
                    label=NO_PENDING_REQUESTS_LABEL, value="NONE", default=True
                )
            ]
            self.select.disabled = True
            self.select.placeholder = NO_PENDING_REQUESTS_LABEL
            self.accept_button.disabled = True
            self.decline_button.disabled = True
        else:
            self.select.options = options
            self.select.disabled = False
            self.select.placeholder = "Select a request to review"
            self.accept_button.disabled = False
            self.decline_button.disabled = False

        self.close_button.disabled = not self.quest.is_signup_open
        if not self.quest.is_signup_open:
            self.accept_button.disabled = True
            self.decline_button.disabled = True

    async def handle_accept(self, interaction: discord.Interaction) -> None:
        signup = self.pending_map.get(self.selected_user_id or "")
        if signup is None:
            await interaction.response.send_message(
                "Select a request to accept first.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            via_api = await self.service.select_signup_via_api(
                self.guild, self.quest, signup.user_id
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not via_api:
            try:
                self.quest.select_signup(signup.user_id)
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
            self.service.persist_quest(self.guild.id, self.quest)
        else:
            refreshed = self.service.fetch_quest(self.guild.id, self.quest.quest_id)
            if refreshed is not None:
                self.quest = refreshed

        await self.service.sync_quest_announcement(
            self.guild,
            self.quest,
            approved_by_display=self.reviewer.mention,
            last_updated_at=datetime.now(timezone.utc),
        )

        await self._notify_player(signup, accepted=True)
        await self._notify_channel(signup, accepted=True)
        await send_demo_log(
            self.service.bot,
            self.guild,
            f"{self.reviewer.mention} accepted {self.service.format_signup_label(self.guild.id, signup)} for `{self.quest.title or self.quest.quest_id}`",
        )

        self._refresh_from_quest()
        await interaction.message.edit(content=self.render_panel_text(), view=self)

        await interaction.followup.send(
            f"Accepted {self.service.format_signup_label(self.guild.id, signup)}.",
            ephemeral=True,
        )

    async def handle_decline(self, interaction: discord.Interaction) -> None:
        signup = self.pending_map.get(self.selected_user_id or "")
        if signup is None:
            await interaction.response.send_message(
                "Select a request to decline first.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            via_api = await self.service.remove_signup_via_api(
                self.guild, self.quest, signup.user_id
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not via_api:
            try:
                self.quest.remove_signup(signup.user_id)
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
            self.service.persist_quest(self.guild.id, self.quest)
        else:
            refreshed = self.service.fetch_quest(self.guild.id, self.quest.quest_id)
            if refreshed is not None:
                self.quest = refreshed

        await self.service.sync_quest_announcement(
            self.guild,
            self.quest,
            approved_by_display=self.reviewer.mention,
            last_updated_at=datetime.now(timezone.utc),
        )

        await self._notify_player(signup, accepted=False)
        await self._notify_channel(signup, accepted=False)
        await send_demo_log(
            self.service.bot,
            self.guild,
            f"{self.reviewer.mention} declined {self.service.format_signup_label(self.guild.id, signup)} for `{self.quest.title or self.quest.quest_id}`",
        )

        self._refresh_from_quest()
        await interaction.message.edit(content=self.render_panel_text(), view=self)

        await interaction.followup.send(
            f"Declined {self.service.format_signup_label(self.guild.id, signup)}.",
            ephemeral=True,
        )

    async def handle_close(self, interaction: discord.Interaction) -> None:
        if not self.quest.is_signup_open:
            await interaction.response.send_message(
                "Signups are already closed for this quest.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            via_api = await self.service.close_signups_via_api(self.guild, self.quest)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not via_api:
            try:
                self.quest.close_signups()
            except ValueError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
            self.service.persist_quest(self.guild.id, self.quest)
        else:
            refreshed = self.service.fetch_quest(self.guild.id, self.quest.quest_id)
            if refreshed is not None:
                self.quest = refreshed
            else:
                try:
                    self.quest.close_signups()
                except ValueError:
                    pass

        await self.service.sync_quest_announcement(
            self.guild,
            self.quest,
            approved_by_display=self.reviewer.mention,
            last_updated_at=datetime.now(timezone.utc),
        )

        await self._notify_channel_closed()
        await send_demo_log(
            self.service.bot,
            self.guild,
            f"{self.reviewer.mention} closed signups for `{self.quest.title or self.quest.quest_id}`",
        )

        self._refresh_from_quest()
        await interaction.message.edit(content=self.render_panel_text(), view=self)

        await interaction.followup.send(
            "Signups closed. Players can no longer request to join.",
            ephemeral=True,
        )

    async def _notify_player(self, signup: PlayerSignUp, *, accepted: bool) -> None:
        member = await self.service.resolve_member_for_user_id(
            self.guild, signup.user_id
        )
        if member is None:
            return

        quest_name = self.quest.title or str(self.quest.quest_id)
        character_label = str(signup.character_id)
        if accepted:
            text = (
                f"Good news! {self.reviewer.display_name} approved your request to join "
                f"`{quest_name}` with `{character_label}`."
            )
        else:
            text = (
                f"Your request to join `{quest_name}` with `{character_label}` was declined "
                f"by {self.reviewer.display_name}."
            )

        try:
            await member.send(text)
        except Exception:
            pass

    async def _notify_channel(self, signup: PlayerSignUp, *, accepted: bool) -> None:
        try:
            channel = self.guild.get_channel(int(self.quest.channel_id))
            if channel is None:
                channel = await self.guild.fetch_channel(int(self.quest.channel_id))
        except Exception:
            channel = None

        if channel is None:
            return

        action = "accepted" if accepted else "declined"
        label = self.service.format_signup_label(self.guild.id, signup)
        try:
            await channel.send(
                f"{self.reviewer.mention} {action} {label} for quest `{self.quest.title or self.quest.quest_id}`."
            )
        except Exception:
            pass

    async def _notify_channel_closed(self) -> None:
        channel_id_raw = self.quest.channel_id
        if not channel_id_raw:
            return

        try:
            channel_id = int(channel_id_raw)
        except (TypeError, ValueError):
            channel = None
        else:
            try:
                channel = self.guild.get_channel(channel_id)
                if channel is None:
                    channel = await self.guild.fetch_channel(channel_id)
            except Exception:
                channel = None

        if channel is None:
            return

        try:
            await channel.send(
                f"{self.reviewer.mention} closed signups for quest `{self.quest.title or self.quest.quest_id}`."
            )
        except Exception:
            pass


class SignupPendingSelect(discord.ui.Select):
    def __init__(self, parent: SignupDecisionView) -> None:
        self.parent = parent
        options = parent._build_options()
        if not options:
            options = [discord.SelectOption(label=NO_PENDING_REQUESTS_LABEL, value="NONE")]
            disabled = True
        else:
            disabled = False
        super().__init__(
            placeholder="Select a request to review",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.disabled:
            await interaction.response.send_message(
                "No pending requests to review.", ephemeral=True
            )
            return

        value = self.values[0]
        if value == "NONE":
            await interaction.response.send_message(
                "No pending requests to review.", ephemeral=True
            )
            return

        self.parent.selected_user_id = value
        self.parent._refresh_from_quest()
        await interaction.response.edit_message(
            content=self.parent.render_panel_text(), view=self.parent
        )


class SignupApproveButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Accept", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, SignupDecisionView):
            await view.handle_accept(interaction)


class SignupDeclineButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Decline", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, SignupDecisionView):
            await view.handle_decline(interaction)


class SignupCloseButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Close Signups", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, SignupDecisionView):
            await view.handle_close(interaction)
