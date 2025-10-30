from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Type

import discord

from app.domain.models.QuestModel import Quest, QuestStatus
from app.domain.models.UserModel import User

from app.bot.cogs.quests.embeds import build_quest_embed

if TYPE_CHECKING:
    from app.bot.cogs.quests.cog import QuestCommandsCog


class QuestConfirmView(discord.ui.View):
    def __init__(self, requester: discord.Member, *, timeout: int = 180) -> None:
        super().__init__(timeout=timeout)
        self.requester_id = requester.id
        self.result: Optional[str] = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "This confirmation belongs to someone else.", ephemeral=True
            )
            return
        self.result = "confirm"
        await interaction.response.send_message(
            "Confirmed!", ephemeral=True
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "This confirmation belongs to someone else.", ephemeral=True
            )
            return
        self.result = "cancel"
        await interaction.response.send_message(
            "Cancelled.", ephemeral=True
        )
        self.stop()

    async def on_timeout(self) -> None:
        self.result = None
        self.stop()


@dataclass
class QuestCreationResult:
    success: bool
    quest: Optional[Quest] = None
    error: Optional[str] = None


@dataclass
class QuestUpdateResult:
    success: bool
    quest: Optional[Quest] = None
    error: Optional[str] = None


class QuestSessionBase:
    def __init__(
        self,
        cog: "QuestCommandsCog",
        guild: discord.Guild,
        member: discord.Member,
        user: User,
        dm_channel: discord.DMChannel,
    ) -> None:
        self.cog = cog
        self.guild = guild
        self.member = member
        self.user = user
        self.dm = dm_channel
        self.timeout = 300
        self.data: Dict[str, Optional[str]] = {}
        self._preview_message: Optional[discord.Message] = None

    async def _safe_send(
        self,
        content: Optional[str] = None,
        *,
        embed: Optional[discord.Embed] = None,
        view: Optional[discord.ui.View] = None,
    ) -> discord.Message:
        try:
            return await self.dm.send(content=content, embed=embed, view=view)
        except discord.Forbidden as exc:
            raise RuntimeError(
                "I can't send you direct messages anymore. Enable DMs and run the command again."
            ) from exc
        except discord.HTTPException as exc:
            raise RuntimeError(f"Failed to send DM: {exc}") from exc

    async def _ask(
        self,
        prompt: str,
        *,
        required: bool,
        allow_skip: bool = False,
        allow_clear: bool = False,
        validator: Optional[Type[Exception] | callable] = None,
    ) -> Optional[str]:
        instructions = ["Type `cancel` to stop."]
        if allow_skip:
            instructions.append("Type `skip` to keep the current value.")
        if allow_clear:
            instructions.append("Type `clear` to remove this value.")
        await self._safe_send(f"{prompt}\n" + " ".join(instructions))

        while True:
            try:
                message = await self.cog.bot.wait_for(
                    "message",
                    timeout=self.timeout,
                    check=lambda m: m.author.id == self.member.id and m.channel.id == self.dm.id,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError from exc

            content = message.content.strip()
            lower = content.lower()
            if lower == "cancel":
                raise RuntimeError("cancelled")
            if allow_clear and lower == "clear":
                return ""
            if allow_skip and lower == "skip":
                return None
            if not content:
                if required:
                    await self._safe_send("Please provide a response, or type `cancel`.")
                    continue
                return None
            try:
                return validator(content) if validator else content
            except ValueError as exc:
                await self._safe_send(f"{exc}\nPlease try again.")

    def _build_preview_embed(
        self,
        quest: Quest,
    ) -> discord.Embed:
        return build_quest_embed(
            quest,
            self.guild,
            lookup_user_display=self.cog.lookup_user_display,
            referee_display=self.cog.lookup_user_display(
                self.guild.id, quest.referee_id
            ),
        )

    async def _update_preview(
        self,
        quest: Quest,
        *,
        header: Optional[str] = None,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        embed = self._build_preview_embed(quest)
        content = header or "**Current quest preview:**"
        if self._preview_message is None:
            self._preview_message = await self._safe_send(
                content,
                embed=embed,
                view=view,
            )
            return
        try:
            await self._preview_message.edit(
                content=content,
                embed=embed,
                view=view,
            )
        except discord.HTTPException:
            self._preview_message = await self._safe_send(
                content,
                embed=embed,
                view=view,
            )

    async def send_completion_summary(self, quest: Quest, note: str) -> None:
        await self._safe_send(note, embed=self._build_preview_embed(quest))

    async def _flash_message(
        self,
        interaction: discord.Interaction,
        message: str,
        *,
        delay: float = 5.0,
    ) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            with suppress(Exception):
                await self._safe_send(message)
            return
        try:
            await asyncio.sleep(delay)
            if interaction.followup:
                await interaction.delete_original_response()
        except Exception:
            pass

    def _parse_datetime(self, value: str) -> Optional[datetime]:
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            try:
                return datetime.fromtimestamp(int(text), tz=timezone.utc)
            except (OverflowError, ValueError):
                return None
        return None

    def _parse_duration(self, value: str) -> Optional[timedelta]:
        text = value.strip()
        if not text:
            return None
        try:
            hours_float = float(text)
        except ValueError:
            return None
        if hours_float <= 0:
            return None
        return timedelta(hours=hours_float)


class QuestWizardContext:
    def __init__(
        self,
        session: "QuestSessionBase",
        quest: Quest,
        mode: Literal["create", "update"],
        timeout: int = 600,
    ) -> None:
        self.session = session
        self.quest = quest
        self.mode = mode
        self.timeout = timeout
        loop = asyncio.get_running_loop()
        self.future: asyncio.Future = loop.create_future()

    def resolve(self, result: Any) -> None:
        if not self.future.done():
            self.future.set_result(result)

    def reject(self, error: Exception) -> None:
        if not self.future.done():
            self.future.set_exception(error)


class QuestWizardView(discord.ui.View):
    def __init__(self, context: QuestWizardContext) -> None:
        super().__init__(timeout=context.timeout)
        self.context = context
        if context.mode == "create":
            self.submit_button.label = "Save Draft"
        else:
            self.submit_button.label = "Save Changes"
        self._all_items: list[discord.ui.Item] = list(self.children)

    def _build_result(self, success: bool, error: Optional[str] = None) -> Any:
        if self.context.mode == "create":
            return QuestCreationResult(
                success,
                quest=self.context.quest if success else None,
                error=error,
            )
        return QuestUpdateResult(
            success,
            quest=self.context.quest if success else None,
            error=error,
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.context.session.member.id:
            await interaction.response.send_message(
                "This wizard is controlled by someone else.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        result = self._build_result(False, "Wizard timed out. Start again when ready.")
        self.context.resolve(result)
        try:
            await self.context.session._update_preview(self.context.quest, view=None)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Title", style=discord.ButtonStyle.primary)
    async def edit_title(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await interaction.response.send_modal(QuestTitleModal(self.context, self))
        except discord.NotFound:
            return

    @discord.ui.button(label="Description", style=discord.ButtonStyle.primary)
    async def edit_description(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await interaction.response.send_modal(
                QuestDescriptionModal(self.context, self)
            )
        except discord.NotFound:
            return

    @discord.ui.button(label="Start Time", style=discord.ButtonStyle.secondary)
    async def edit_start_time(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await interaction.response.send_modal(QuestStartModal(self.context, self))
        except discord.NotFound:
            return

    @discord.ui.button(label="Duration", style=discord.ButtonStyle.secondary)
    async def edit_duration(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await interaction.response.send_modal(QuestDurationModal(self.context, self))
        except discord.NotFound:
            return

    @discord.ui.button(label="Image", style=discord.ButtonStyle.secondary)
    async def edit_image(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            await interaction.response.send_modal(QuestImageModal(self.context, self))
        except discord.NotFound:
            return

    @discord.ui.button(label="Refresh Preview", style=discord.ButtonStyle.secondary)
    async def refresh_preview(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        await self.context.session._update_preview(
            self.context.quest,
            view=self,
        )

    @discord.ui.button(style=discord.ButtonStyle.success)
    async def submit_button(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        missing: list[str] = []
        if not self.context.quest.title:
            missing.append("title")
        if not self.context.quest.starting_at:
            missing.append("start time")
        if not self.context.quest.duration:
            missing.append("duration")
        if missing:
            await self.context.session._flash_message(
                interaction,
                f"Please set the {', '.join(missing)} before saving.",
            )
            return

        try:
            self.context.quest.validate_quest()
        except ValueError as exc:
            await self.context.session._flash_message(
                interaction,
                f"Quest validation failed: {exc}",
            )
            return

        await interaction.response.defer()
        result = self._build_result(True)
        self.context.resolve(result)
        self._set_disabled(True)
        await self.context.session._update_preview(
            self.context.quest,
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        if self.context.mode == "create":
            message = "Quest creation cancelled."
        else:
            message = "Quest update cancelled."
        result = self._build_result(False, message)
        self.context.resolve(result)
        self._set_disabled(True)
        await self.context.session._update_preview(
            self.context.quest,
            view=self,
        )
        self.stop()

    def _set_disabled(self, value: bool) -> None:
        for item in self._all_items:
            item.disabled = value


class _BaseQuestModal(discord.ui.Modal):
    def __init__(self, context: QuestWizardContext, view: QuestWizardView, *, title: str):
        super().__init__(title=title)
        self.context = context
        self.view = view


class QuestTitleModal(_BaseQuestModal):
    def __init__(self, context: QuestWizardContext, view: QuestWizardView) -> None:
        super().__init__(context, view, title="Quest Title")
        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="Enter a quest title",
            min_length=3,
            max_length=100,
            default=self.context.quest.title or "",
        )
        self.add_item(self.title_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.context.quest.title = self.title_input.value.strip()
        await interaction.response.defer()
        await self.context.session._update_preview(
            self.context.quest,
            view=self.view,
        )


class QuestDescriptionModal(_BaseQuestModal):
    def __init__(self, context: QuestWizardContext, view: QuestWizardView) -> None:
        super().__init__(context, view, title="Quest Description")
        self.description_input = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=2000,
            default=self.context.quest.description or "",
            placeholder="Optional description. Leave blank to clear.",
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.context.quest.description = self.description_input.value.strip() or None
        await interaction.response.defer()
        await self.context.session._update_preview(
            self.context.quest,
            view=self.view,
        )


class QuestStartModal(_BaseQuestModal):
    def __init__(self, context: QuestWizardContext, view: QuestWizardView) -> None:
        super().__init__(context, view, title="Quest Start Time")
        default_value = ""
        if context.quest.starting_at:
            default_value = str(
                int(context.quest.starting_at.replace(tzinfo=timezone.utc).timestamp())
            )
        self.start_input = discord.ui.TextInput(
            label="Start Time (epoch seconds)",
            placeholder="Example: 1761424020",
            default=default_value,
            max_length=32,
        )
        self.add_item(self.start_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.start_input.value.strip()
        parsed = self.context.session._parse_datetime(value)
        if parsed is None:
            await self.context.session._flash_message(
                interaction,
                "Could not parse start time. Provide epoch seconds (UTC).",
            )
            return
        self.context.quest.starting_at = parsed
        await interaction.response.defer()
        await self.context.session._update_preview(
            self.context.quest,
            view=self.view,
        )


class QuestDurationModal(_BaseQuestModal):
    def __init__(self, context: QuestWizardContext, view: QuestWizardView) -> None:
        super().__init__(context, view, title="Quest Duration")
        default_value = ""
        if context.quest.duration is not None:
            default_value = (
                f"{context.quest.duration.total_seconds() / 3600:.2f}".rstrip("0").rstrip(".")
            )
        self.duration_input = discord.ui.TextInput(
            label="Duration (hours)",
            placeholder="Enter a positive number (e.g., 2 or 2.5)",
            default=default_value,
            max_length=10,
        )
        self.add_item(self.duration_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.duration_input.value.strip()
        parsed = self.context.session._parse_duration(value)
        if parsed is None:
            await self.context.session._flash_message(
                interaction,
                "Duration must be a positive number of hours (e.g., 2 or 2.5).",
            )
            return
        self.context.quest.duration = parsed
        await interaction.response.defer()
        await self.context.session._update_preview(
            self.context.quest,
            view=self.view,
        )


class QuestImageModal(_BaseQuestModal):
    def __init__(self, context: QuestWizardContext, view: QuestWizardView) -> None:
        super().__init__(context, view, title="Quest Image")
        self.image_input = discord.ui.TextInput(
            label="Image URL",
            required=False,
            default=context.quest.image_url or "",
            placeholder="Must start with http or https. Leave blank to clear.",
        )
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.image_input.value.strip()
        if value and not value.lower().startswith(("http://", "https://")):
            await self.context.session._flash_message(
                interaction,
                "Image URL must start with http:// or https://",
            )
            return
        self.context.quest.image_url = value or None
        await interaction.response.defer()
        await self.context.session._update_preview(
            self.context.quest,
            view=self.view,
        )


class QuestAnnounceView(discord.ui.View):
    def __init__(
        self,
        cog: "QuestCommandsCog",
        session: QuestSessionBase,
        guild: discord.Guild,
        member: discord.Member,
        quest: Quest,
    ) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.session = session
        self.guild = guild
        self.member = member
        self.quest = quest
        self._all_items: list[discord.ui.Item] = list(self.children)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "Only the quest referee can use these buttons.", ephemeral=True
            )
            return False
        return True

    def _set_disabled(self, value: bool) -> None:
        for item in self._all_items:
            item.disabled = value

    @discord.ui.button(label="Announce Now", style=discord.ButtonStyle.success)
    async def announce_now(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        if self.quest.channel_id and self.quest.message_id:
            await interaction.followup.send(
                "This quest is already announced. Use `/quest edit` for changes.",
            )
            return
        try:
            await self.cog._announce_quest_now(
                self.guild,
                self.quest,
                invoker=self.member,
                fallback_channel=None,
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc))
            return
        except Exception:  # pragma: no cover - defensive
            await interaction.followup.send("Unable to announce the quest right now.")
            raise

        channel_display = "the configured channel"
        if self.quest.channel_id:
            channel = self.guild.get_channel(int(self.quest.channel_id))
            if channel is not None:
                channel_display = channel.mention
        await interaction.followup.send(
            f"Quest `{self.quest.quest_id}` announced in {channel_display}.",
        )
        self._set_disabled(True)
        await self.session._update_preview(
            self.quest,
            header="**Quest Announced**\nUse `/quest edit` for further changes.",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Schedule", style=discord.ButtonStyle.secondary)
    async def schedule_button(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.quest.channel_id and self.quest.message_id:
            await interaction.response.send_message(
                "Announced quests cannot be rescheduled via this wizard.",
                ephemeral=True,
            )
            return
        try:
            await interaction.response.send_modal(
                QuestScheduleModal(self.cog, self.session, self.guild, self.quest, self)
            )
        except discord.NotFound:
            return

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(  # type: ignore[override]
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self._set_disabled(True)
        await interaction.response.defer()
        await self.session._update_preview(
            self.quest,
            header="**Quest Draft Saved**",
            view=self,
        )
        self.stop()


class QuestScheduleModal(discord.ui.Modal):
    def __init__(
        self,
        cog: "QuestCommandsCog",
        session: QuestSessionBase,
        guild: discord.Guild,
        quest: Quest,
        view: QuestAnnounceView,
    ) -> None:
        super().__init__(title="Schedule Quest Announcement")
        self.cog = cog
        self.session = session
        self.guild = guild
        self.quest = quest
        self.view = view
        self.time_input = discord.ui.TextInput(
            label="Announcement Time (epoch seconds, UTC)",
            placeholder="Example: 1761424020",
            max_length=32,
        )
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        value = self.time_input.value.strip()
        if not value.isdigit():
            await self.session._flash_message(
                interaction,
                "Enter epoch seconds (UTC).",
            )
            return
        seconds = int(value)
        scheduled = datetime.fromtimestamp(seconds, tz=timezone.utc)
        if scheduled <= datetime.now(timezone.utc):
            await self.session._flash_message(
                interaction,
                "Scheduled time must be in the future.",
            )
            return
        self.quest.announce_at = scheduled
        self.quest.status = QuestStatus.DRAFT
        self.cog._persist_quest(self.guild.id, self.quest)
        await interaction.response.send_message(
            f"Quest `{self.quest.quest_id}` will announce at <t:{seconds}:F>.",
        )
        header = (
            "**Quest Draft Saved**\n"
            f"Scheduled to announce at <t:{seconds}:F>."
        )
        await self.session._update_preview(
            self.quest,
            header=header,
            view=self.view,
        )


class QuestCreationSession(QuestSessionBase):
    def __init__(
        self,
        cog: "QuestCommandsCog",
        guild: discord.Guild,
        member: discord.Member,
        user: User,
        dm_channel: discord.DMChannel,
    ) -> None:
        super().__init__(cog, guild, member, user, dm_channel)

    async def run(self) -> QuestCreationResult:
        quest_id = self.cog._next_quest_id(self.guild.id)
        quest = Quest(
            quest_id=quest_id,
            guild_id=self.guild.id,
            referee_id=self.user.user_id,
            raw="",
            status=QuestStatus.DRAFT,
        )
        context = QuestWizardContext(self, quest, mode="create")
        view = QuestWizardView(context)
        await self._update_preview(
            quest,
            header=(
                "**Quest Draft Preview**\n"
                "Use the buttons below to update fields. "
                "Title, start time, and duration are required. "
                "Start time must be epoch seconds (UTC)."
            ),
            view=view,
        )
        try:
            result: QuestCreationResult = await context.future
        finally:
            if self._preview_message is not None:
                with suppress(Exception):
                    await self._preview_message.edit(view=None)

        if result.success and result.quest:
            description_text = result.quest.description or "No description provided."
            result.quest.raw = f"## {result.quest.title}\n\n{description_text}"
        return result


class QuestUpdateSession(QuestSessionBase):
    def __init__(
        self,
        cog: "QuestCommandsCog",
        guild: discord.Guild,
        member: discord.Member,
        user: User,
        dm_channel: discord.DMChannel,
        quest: Quest,
    ) -> None:
        super().__init__(cog, guild, member, user, dm_channel)
        self.quest = quest

    async def run(self) -> QuestUpdateResult:
        context = QuestWizardContext(self, self.quest, mode="update")
        view = QuestWizardView(context)
        await self._update_preview(
            self.quest,
            header="**Quest Preview**\nUpdate fields with the buttons below, then save your changes. Start time must be epoch seconds (UTC).",
            view=view,
        )
        try:
            result: QuestUpdateResult = await context.future
        finally:
            if self._preview_message is not None:
                with suppress(Exception):
                    await self._preview_message.edit(view=None)

        return result
