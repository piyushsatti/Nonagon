from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional
from urllib.parse import urlparse

import discord

from app.bot.services import guild_settings_store
from app.bot.utils.log_stream import send_demo_log
from app.domain.models.CharacterModel import Character, CharacterRole
from app.domain.models.EntityIDModel import CharacterID

from .utils import build_character_embed, build_character_embed_from_model

if TYPE_CHECKING:
    from app.bot.cogs.CharacterCommandsCog import CharacterCommandsCog


class SessionCancelled(Exception):
    """Raised when the user cancels a DM session."""


class SessionTimeout(Exception):
    """Raised when the DM session times out awaiting a response."""


class SessionMessagingError(Exception):
    """Raised when the bot cannot send a DM message during a session."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CharacterSessionBase:
    def __init__(
        self,
        cog: "CharacterCommandsCog",
        guild: discord.Guild,
        member: discord.Member,
        dm_channel: discord.DMChannel,
    ) -> None:
        self.cog = cog
        self.bot = cog.bot
        self.guild = guild
        self.member = member
        self.dm = dm_channel
        self.timeout = 180
        self.data: Dict[str, Optional[str]] = {}

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
            raise SessionMessagingError(
                "I can't send you direct messages anymore. Enable DMs and run the command again."
            ) from exc
        except discord.HTTPException as exc:
            raise SessionMessagingError(f"Failed to send DM: {exc}") from exc

    async def _ask(
        self,
        prompt: str,
        *,
        required: bool,
        validator,
        allow_skip: bool = False,
        skip_message: Optional[str] = None,
        allow_clear: bool = False,
        clear_message: Optional[str] = None,
    ) -> Optional[str]:
        instructions = ["Type `cancel` to stop."]
        if allow_skip:
            instructions.append(skip_message or "Type `skip` to keep the current value.")
        if allow_clear:
            instructions.append(clear_message or "Type `clear` to remove this value.")
        await self._safe_send(f"{prompt}\n" + " ".join(instructions))

        while True:
            try:
                message = await self.bot.wait_for(
                    "message",
                    timeout=self.timeout,
                    check=lambda m: m.author.id == self.member.id
                    and m.channel.id == self.dm.id,
                )
            except asyncio.TimeoutError as exc:
                raise SessionTimeout from exc

            content = message.content.strip()
            lower = content.lower()
            if lower == "cancel":
                raise SessionCancelled()
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

    def _build_embed_from_data(
        self,
        *,
        status: CharacterRole,
        updated_at: Optional[datetime] = None,
    ) -> discord.Embed:
        return build_character_embed(
            name=self.data.get("name") or "Unnamed Character",
            ddb_link=self.data.get("ddb_link"),
            character_thread_link=self.data.get("character_thread_link"),
            token_link=self.data.get("token_link"),
            art_link=self.data.get("art_link"),
            description=self.data.get("description"),
            tags=self._parse_tags(),
            status=status,
            updated_at=updated_at,
        )

    def _parse_tags(self) -> List[str]:
        raw = self.data.get("tags")
        if not raw:
            return []
        return [tag.strip() for tag in raw.split(",") if tag.strip()]

    @staticmethod
    def _normalize_optional(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @staticmethod
    def _validate_name(value: str) -> str:
        name = value.strip()
        if not 2 <= len(name) <= 64:
            raise ValueError("Character name must be between 2 and 64 characters long.")
        return name

    @staticmethod
    def _validate_url(value: str) -> str:
        url = value.strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Please provide a valid URL (http/https).")
        return url

    @staticmethod
    def _validate_description(value: str) -> str:
        text = value.strip()
        if len(text) > 500:
            raise ValueError("Description must be 500 characters or fewer.")
        return text

    @staticmethod
    def _validate_notes(value: str) -> str:
        text = value.strip()
        if len(text) > 500:
            raise ValueError("Notes must be 500 characters or fewer.")
        return text

    @staticmethod
    def _sanitize_tags(value: str) -> str:
        tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        if len(tags) > 20:
            raise ValueError("Please provide 20 or fewer tags.")
        return ", ".join(tags)


@dataclass
class CharacterCreationResult:
    success: bool
    character_name: Optional[str] = None
    announcement_channel: Optional[discord.TextChannel] = None
    error: Optional[str] = None


@dataclass
class CharacterUpdateResult:
    success: bool
    character: Optional[Character] = None
    note: Optional[str] = None
    error: Optional[str] = None


class CharacterLinkView(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=120)
        self.add_item(discord.ui.Button(label="Open Announcement", url=url))


class CharacterConfirmView(discord.ui.View):
    def __init__(self, requester: discord.Member, *, timeout: int = 180):
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
            "Confirmed! Creating your character...", ephemeral=True
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
            "Character creation cancelled.", ephemeral=True
        )
        self.stop()

    async def on_timeout(self) -> None:
        self.result = None
        self.stop()


class CharacterCreationSession(CharacterSessionBase):
    def __init__(
        self,
        cog: "CharacterCommandsCog",
        guild: discord.Guild,
        member: discord.Member,
        dm_channel: discord.DMChannel,
    ) -> None:
        super().__init__(cog, guild, member, dm_channel)

    async def run(self) -> CharacterCreationResult:
        try:
            await self._safe_send(
                "Hello! Let's create your character. I'll ask a few questions — type `cancel` at any time to stop."
            )

            self.data["name"] = await self._ask(
                "**Step 1:** What's your character's name?",
                required=True,
                validator=self._validate_name,
            )
            self.data["ddb_link"] = await self._ask(
                "**Step 2:** Share the D&D Beyond (or sheet) link.",
                required=True,
                validator=self._validate_url,
            )
            self.data["character_thread_link"] = await self._ask(
                "**Step 3:** What's the forum/thread link for this character?",
                required=True,
                validator=self._validate_url,
            )
            self.data["token_link"] = await self._ask(
                "**Step 4:** Provide a token image link.",
                required=True,
                validator=self._validate_url,
            )
            self.data["art_link"] = await self._ask(
                "**Step 5:** Provide a character art link.",
                required=True,
                validator=self._validate_url,
            )
            self.data["description"] = await self._ask(
                "**Step 6:** Add an optional short description (max 500 characters).",
                required=False,
                validator=self._validate_description,
                allow_skip=True,
            )
            self.data["notes"] = await self._ask(
                "**Step 7:** Any private notes for staff? (max 500 characters).",
                required=False,
                validator=self._validate_notes,
                allow_skip=True,
            )
            self.data["tags"] = await self._ask(
                "**Step 8:** Optional tags (comma separated).",
                required=False,
                validator=self._sanitize_tags,
                allow_skip=True,
            )
        except SessionCancelled:
            await self._safe_send("Character creation cancelled. No data was saved.")
            return CharacterCreationResult(False, error="Character creation cancelled.")
        except SessionTimeout:
            await self._safe_send(
                "Timed out waiting for a response. Run `/character create` again when you're ready."
            )
            return CharacterCreationResult(
                False,
                error="Timed out waiting for a response. Run `/character create` again when you're ready.",
            )
        except SessionMessagingError as exc:
            return CharacterCreationResult(False, error=exc.message)

        tags = self._parse_tags()
        preview_embed = self._build_embed_from_data(status=CharacterRole.ACTIVE)

        try:
            await self._safe_send(
                "Here's a preview of what will be posted in the character channel:",
                embed=preview_embed,
            )
            notes = self.data.get("notes")
            if notes:
                await self._safe_send("**Private notes (not shared publicly):**\n" + notes)

            view = CharacterConfirmView(self.member)
            message = await self._safe_send(
                "Confirm below to create your character, or cancel to stop.", view=view
            )
        except SessionMessagingError as exc:
            return CharacterCreationResult(False, error=exc.message)

        await view.wait()
        try:
            await message.edit(view=None)
        except (discord.HTTPException, AttributeError):
            pass

        if view.result != "confirm":
            await self._safe_send("Character creation cancelled.")
            return CharacterCreationResult(False, error="Character creation cancelled.")

        return await self._persist_character(tags)

    async def _persist_character(self, tags: List[str]) -> CharacterCreationResult:
        channel, channel_error = self._resolve_character_channel()
        if channel is None:
            await self._safe_send(channel_error)
            return CharacterCreationResult(False, error=channel_error)

        try:
            user = await self.cog._get_cached_user(self.member)
        except RuntimeError as exc:
            await self._safe_send(
                "Internal error resolving your profile; please try again later."
            )
            return CharacterCreationResult(
                False,
                error="Internal error resolving your profile; please try again later.",
            )

        if not user.is_player:
            user.enable_player()

        char_id = self.cog._next_character_id(self.guild.id)
        description = self._normalize_optional(self.data.get("description"))
        notes = self._normalize_optional(self.data.get("notes"))
        character = Character(
            character_id=str(char_id),
            owner_id=user.user_id,
            name=self.data["name"] or "",
            ddb_link=self.data["ddb_link"] or "",
            character_thread_link=self.data["character_thread_link"] or "",
            token_link=self.data["token_link"] or "",
            art_link=self.data["art_link"] or "",
            description=description,
            notes=notes,
            tags=tags,
            created_at=datetime.now(timezone.utc),
            guild_id=self.guild.id,
            status=CharacterRole.ACTIVE,
        )

        try:
            character.validate_character()
        except ValueError as exc:
            await self._safe_send(f"Character validation failed: {exc}")
            return CharacterCreationResult(
                False, error=f"Character validation failed: {exc}"
            )

        if user.player is None:
            user.enable_player()
        if user.player is not None and char_id not in user.player.characters:
            user.player.characters.append(CharacterID.parse(str(char_id)))

        public_embed = build_character_embed_from_model(character)
        try:
            announcement = await channel.send(
                content=f"{self.member.mention} created a new character!",
                embed=public_embed,
            )
        except discord.Forbidden:
            error = (
                f"I don't have permission to post in {channel.mention}. "
                "Ask an admin to fix my channel permissions and try again."
            )
            await self._safe_send(error)
            return CharacterCreationResult(False, error=error)
        except discord.HTTPException as exc:
            error = f"Failed to post in {channel.mention}: {exc}"
            await self._safe_send(error)
            return CharacterCreationResult(False, error=error)

        await send_demo_log(
            self.cog.bot,
            self.guild,
            f"{self.member.mention} created character `{character.name}` ({char_id})",
        )

        thread = None
        thread_note = None
        thread_name = f"Character: {character.name}"[:90]
        thread_parent = announcement.channel
        if isinstance(thread_parent, discord.TextChannel):
            thread = await self._create_character_thread(
                thread_parent, announcement, thread_name
            )
            if thread is None:
                thread_note = (
                    "I couldn't create a private onboarding thread. Grant me the **Create Private Threads** permission or allow thread creation in the configured channel."
                )
        else:
            thread_note = "Character announcements are posted in a channel that does not support threads."

        if isinstance(announcement.channel, discord.TextChannel):
            character.announcement_channel_id = announcement.channel.id
        character.announcement_message_id = announcement.id
        if thread is not None:
            character.onboarding_thread_id = thread.id

        self.cog._persist_character(self.guild.id, character)
        await self.cog.bot.dirty_data.put((self.guild.id, self.member.id))

        summary_lines = [
            f"Character `{character.name}` (`{char_id}`) created!",
            f"Announcement: {announcement.jump_url}",
        ]
        if thread is not None:
            thread_link = f"https://discord.com/channels/{self.guild.id}/{thread.id}"
            summary_lines.append(f"Onboarding thread: {thread_link}")
        if thread_note:
            summary_lines.append(thread_note)

        await self._safe_send("\n".join(summary_lines))

        return CharacterCreationResult(
            True,
            character_name=character.name,
            announcement_channel=announcement.channel
            if isinstance(announcement.channel, discord.TextChannel)
            else None,
        )

    async def _create_character_thread(
        self,
        channel: discord.TextChannel,
        announcement: discord.Message,
        thread_name: str,
    ) -> Optional[discord.Thread]:
        try:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=channel.default_auto_archive_duration or 1440,
                reason="Character onboarding",
            )
        except (discord.Forbidden, discord.HTTPException):
            return None

        try:
            await thread.add_user(self.member)
        except discord.HTTPException:
            pass

        try:
            await thread.send(
                f"Onboarding thread for {self.member.mention}. "
                f"Announcement: {announcement.jump_url}"
            )
        except discord.HTTPException:
            pass

        return thread

    def _resolve_character_channel(
        self,
    ) -> tuple[Optional[discord.TextChannel], str]:
        settings = guild_settings_store.fetch_settings(self.guild.id) or {}
        channel_id = settings.get("character_commands_channel_id")
        if channel_id is None:
            return (
                None,
                "No character commands channel is configured. Ask an admin to run `/setup character` and try again.",
            )

        try:
            candidate = self.guild.get_channel(int(channel_id))
        except (TypeError, ValueError):
            candidate = None

        if not isinstance(candidate, discord.TextChannel):
            return (
                None,
                "The configured character channel is missing or not a text channel. Ask an admin to rerun `/setup character`.",
            )

        me = self.guild.me
        if me is None:
            return (
                None,
                "I couldn't resolve my bot member in this guild. Try again once I'm fully connected.",
            )

        perms = candidate.permissions_for(me)
        if not perms.send_messages:
            return (
                None,
                f"I need permission to send messages in {candidate.mention}. Update my permissions and try again.",
            )
        if not (perms.create_private_threads or perms.manage_threads):
            return (
                None,
                f"I need **Create Private Threads** permission in {candidate.mention} to start onboarding threads.",
            )

        return candidate, ""


class CharacterUpdateSession(CharacterSessionBase):
    def __init__(
        self,
        cog: "CharacterCommandsCog",
        guild: discord.Guild,
        member: discord.Member,
        dm_channel: discord.DMChannel,
        character: Character,
    ) -> None:
        super().__init__(cog, guild, member, dm_channel)
        self.character = character
        self.status = character.status
        self.data = {
            "name": character.name,
            "ddb_link": character.ddb_link,
            "character_thread_link": character.character_thread_link,
            "token_link": character.token_link,
            "art_link": character.art_link,
            "description": character.description,
            "notes": character.notes,
            "tags": ", ".join(character.tags) if character.tags else None,
        }

    def _apply_response(self, key: str, response: Optional[str]) -> None:
        if response is None:
            return
        self.data[key] = response if response != "" else None

    async def run(self) -> CharacterUpdateResult:
        try:
            await self._safe_send(
                "Let's update your character. For each prompt, type a new value, `skip` to keep the current value, or `clear` to remove optional fields."
            )
            current_embed = build_character_embed_from_model(self.character)
            await self._safe_send("Current profile:", embed=current_embed)

            responses = [
                (
                    "name",
                    "**Step 1:** Update the character name (or `skip`).",
                    self._validate_name,
                    True,
                    False,
                ),
                (
                    "ddb_link",
                    "**Step 2:** Update the D&D Beyond (or sheet) link.",
                    self._validate_url,
                    True,
                    False,
                ),
                (
                    "character_thread_link",
                    "**Step 3:** Update the forum/thread link.",
                    self._validate_url,
                    True,
                    False,
                ),
                (
                    "token_link",
                    "**Step 4:** Update the token image link.",
                    self._validate_url,
                    True,
                    False,
                ),
                (
                    "art_link",
                    "**Step 5:** Update the character art link.",
                    self._validate_url,
                    True,
                    False,
                ),
            ]

            for key, prompt, validator, required, allow_clear in responses:
                response = await self._ask(
                    prompt,
                    required=required,
                    validator=validator,
                    allow_skip=True,
                    skip_message="Type `skip` to keep the current value.",
                    allow_clear=allow_clear,
                )
                self._apply_response(key, response)

            optional_prompts = [
                (
                    "description",
                    "**Step 6:** Update the short description (max 500 characters).",
                    self._validate_description,
                ),
                (
                    "notes",
                    "**Step 7:** Update private notes for staff (max 500 characters).",
                    self._validate_notes,
                ),
                (
                    "tags",
                    "**Step 8:** Update tags (comma separated).",
                    self._sanitize_tags,
                ),
            ]

            for key, prompt, validator in optional_prompts:
                response = await self._ask(
                    prompt,
                    required=False,
                    validator=validator,
                    allow_skip=True,
                    skip_message="Type `skip` to keep the current value.",
                    allow_clear=True,
                    clear_message="Type `clear` to remove this value.",
                )
                self._apply_response(key, response)
        except SessionCancelled:
            await self._safe_send("Character update cancelled. No changes were applied.")
            return CharacterUpdateResult(success=False, error="Character update cancelled.")
        except SessionTimeout:
            await self._safe_send(
                "Timed out waiting for a response. Run `/character edit` again when you're ready."
            )
            return CharacterUpdateResult(
                success=False,
                error="Timed out waiting for a response. Run `/character edit` again when you're ready.",
            )
        except SessionMessagingError as exc:
            return CharacterUpdateResult(success=False, error=exc.message)

        tags = self._parse_tags()
        preview_embed = self._build_embed_from_data(
            status=self.status, updated_at=datetime.now(timezone.utc)
        )

        try:
            await self._safe_send("Preview of your updated character:", embed=preview_embed)
            notes = self._normalize_optional(self.data.get("notes"))
            if notes:
                await self._safe_send("**Private notes (not shared publicly):**\n" + notes)

            view = CharacterConfirmView(self.member)
            message = await self._safe_send(
                "Confirm below to apply these updates, or cancel to stop.", view=view
            )
        except SessionMessagingError as exc:
            return CharacterUpdateResult(success=False, error=exc.message)

        await view.wait()
        try:
            await message.edit(view=None)
        except (discord.HTTPException, AttributeError):
            pass

        if view.result != "confirm":
            await self._safe_send("Character update cancelled.")
            return CharacterUpdateResult(success=False, error="Character update cancelled.")

        return await self._persist_updates(tags)

    async def _persist_updates(self, tags: List[str]) -> CharacterUpdateResult:
        updated_character = Character(**self.character.to_dict())
        updated_character.name = self.data.get("name") or self.character.name
        updated_character.ddb_link = self.data.get("ddb_link") or self.character.ddb_link
        updated_character.character_thread_link = (
            self.data.get("character_thread_link") or self.character.character_thread_link
        )
        updated_character.token_link = (
            self.data.get("token_link") or self.character.token_link
        )
        updated_character.art_link = self.data.get("art_link") or self.character.art_link
        updated_character.description = self._normalize_optional(
            self.data.get("description")
        )
        updated_character.notes = self._normalize_optional(self.data.get("notes"))
        updated_character.tags = tags
        updated_character.status = self.status

        try:
            updated_character.validate_character()
        except ValueError as exc:
            await self._safe_send(f"Character validation failed: {exc}")
            return CharacterUpdateResult(False, error=f"Character validation failed: {exc}")

        self.cog._persist_character(self.guild.id, updated_character)
        note = await self.cog._update_character_announcement(self.guild, updated_character)

        summary = [
            f"Character `{updated_character.name}` (`{updated_character.character_id}`) updated!",
        ]
        if note:
            summary.append(note)
        await self._safe_send("\n".join(summary))

        return CharacterUpdateResult(
            success=True,
            character=updated_character,
            note=note,
        )

    async def _ask(
        self,
        prompt: str,
        *,
        required: bool,
        validator,
        allow_skip: bool = False,
    ) -> Optional[str]:
        instructions = ["Type `cancel` to stop."]
        if not required and allow_skip:
            instructions.append("Type `skip` to leave this blank.")
        await self._safe_send(f"{prompt}\n" + " ".join(instructions))

        while True:
            try:
                message = await self.bot.wait_for(
                    "message",
                    timeout=self.timeout,
                    check=lambda m: m.author.id == self.member.id
                    and m.channel.id == self.dm.id,
                )
            except asyncio.TimeoutError as exc:
                raise SessionTimeout from exc

            content = message.content.strip()
            if content.lower() == "cancel":
                raise SessionCancelled()
            if allow_skip and content.lower() == "skip":
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

        return None
