from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.character import (
    CharacterConfirmView,
    CharacterLinkView,
    CharacterCreationSession,
    CharacterUpdateSession,
    build_character_embed,
    build_character_embed_from_model,
    status_label,
)
from app.bot.services import guild_settings_store
from app.bot.utils.log_stream import send_demo_log
from app.bot.cogs._staff_utils import is_allowed_staff
from app.domain.models.CharacterModel import Character, CharacterRole
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_character_sync
from app.bot.config import BOT_FLUSH_VIA_ADAPTER
from app.infra.serialization import from_bson, to_bson


class CharacterCommandsCog(commands.Cog):
    """Slash commands for player character management."""

    character = app_commands.Group(
        name="character", description="Manage Nonagon character profiles."
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_dm_sessions: set[int] = set()

    async def _fetch_character(
        self, guild: discord.Guild, raw_character_id: str
    ) -> Optional[Character]:
        await self._ensure_guild_cache(guild)
        guild_entry = self.bot.guild_data[guild.id]
        db = guild_entry["db"]
        try:
            normalized = str(CharacterID.parse(raw_character_id))
        except Exception:
            normalized = raw_character_id.strip().upper()

        doc = db["characters"].find_one(
            {"guild_id": guild.id, "character_id": normalized}
        )
        if doc is None:
            doc = db["characters"].find_one(
                {"guild_id": guild.id, "character_id.value": normalized}
            )
        if doc is None:
            return None

        character = from_bson(Character, doc)
        character.guild_id = guild.id
        if isinstance(character.tags, list):
            character.tags = [str(tag) for tag in character.tags]
        else:
            character.tags = []
        if not isinstance(character.owner_id, UserID):
            try:
                character.owner_id = UserID.parse(str(character.owner_id))
            except Exception:
                pass
        if not character.status:
            character.status = CharacterRole.ACTIVE
        return character

    def _can_manage_character(
        self, member: discord.Member, character: Character
    ) -> bool:
        try:
            owner_id = UserID.from_body(str(member.id))
        except Exception:
            owner_id = None
        if owner_id and character.owner_id == owner_id:
            return True
        return is_allowed_staff(self.bot, member)

    async def _update_character_announcement(
        self, guild: discord.Guild, character: Character
    ) -> Optional[str]:
        channel_id = character.announcement_channel_id
        message_id = character.announcement_message_id
        if not channel_id or not message_id:
            return "No announcement message is stored for this character."

        channel: Optional[discord.abc.GuildChannel] = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                return "Unable to access the stored announcement channel."

        if not isinstance(channel, discord.TextChannel):
            return "Stored announcement channel is not a text channel."

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return "Announcement message could not be found."
        except discord.Forbidden:
            return "I lack permission to edit the announcement message."
        except discord.HTTPException as exc:
            logging.exception(
                "Failed to fetch announcement message %s/%s: %s",
                channel_id,
                message_id,
                exc,
            )
            return "Failed to fetch the announcement message."

        embed = self._build_character_embed_from_model(character)
        try:
            await message.edit(embed=embed)
        except discord.HTTPException as exc:
            logging.exception("Failed to edit character announcement message: %s", exc)
            return "Failed to update the announcement message."

        note: Optional[str] = None
        if character.onboarding_thread_id:
            thread = guild.get_thread(character.onboarding_thread_id)
            if thread is None:
                candidate = self.bot.get_channel(character.onboarding_thread_id)
                if isinstance(candidate, discord.Thread):
                    thread = candidate
            if thread is not None:
                desired_name = self._desired_thread_name(character)
                if thread.name != desired_name:
                    try:
                        await thread.edit(
                            name=desired_name,
                            reason="Character profile updated",
                        )
                    except discord.HTTPException as exc:
                        logging.debug("Failed to rename character thread: %s", exc)
                        note = (
                            note or ""
                        ) + " Thread rename failed due to missing permissions."
            elif note is None:
                note = "The onboarding thread could not be found."

        return note

    async def _owned_character_docs(
        self, guild: discord.Guild, member: discord.Member
    ) -> List[dict]:
        await self._ensure_guild_cache(guild)
        guild_entry = self.bot.guild_data[guild.id]
        db = guild_entry["db"]
        owner_id = str(UserID.from_body(str(member.id)))
        cursor = db["characters"].find(
            {
                "guild_id": guild.id,
                "owner_id.value": owner_id,
            },
            {
                "_id": 0,
                "character_id": 1,
                "name": 1,
                "ddb_link": 1,
                "status": 1,
                "announcement_channel_id": 1,
                "announcement_message_id": 1,
            },
        )
        return list(cursor)

    @staticmethod
    def _normalize_character_id(raw: object) -> str:
        if isinstance(raw, dict):
            value = raw.get("value")
            if value is not None:
                return str(value)
            prefix = raw.get("prefix", CharacterID.prefix)
            number = raw.get("number")
            if number is not None:
                return f"{prefix}{number}"
        return str(raw)

    async def _handle_status_change(
        self,
        interaction: discord.Interaction,
        character_id: str,
        target_status: CharacterRole,
        success_message: str,
        already_message: str,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can manage characters.", ephemeral=True
            )
            return

        character = await self._fetch_character(interaction.guild, character_id)
        if character is None:
            await interaction.response.send_message(
                f"Character `{character_id}` was not found.", ephemeral=True
            )
            return

        if not self._can_manage_character(member, character):
            await interaction.response.send_message(
                "You do not have permission to modify this character.",
                ephemeral=True,
            )
            return

        if character.status is target_status:
            await interaction.response.send_message(
                already_message.format(name=character.name),
                ephemeral=True,
            )
            return

        if target_status is CharacterRole.INACTIVE:
            character.deactivate()
        else:
            character.activate()

        self._persist_character(interaction.guild.id, character)
        note = await self._update_character_announcement(interaction.guild, character)

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"{member.mention} set character `{character.name}` ({character.character_id}) to {self._status_label(character.status)}.",
        )

        message = success_message.format(name=character.name)
        if note:
            message = f"{message}\n{note}"

        await interaction.response.send_message(message, ephemeral=True)

    @staticmethod
    def _status_label(status: CharacterRole) -> str:
        return status_label(status)

    def _build_character_embed(
        self,
        *,
        name: str,
        ddb_link: Optional[str],
        character_thread_link: Optional[str],
        token_link: Optional[str],
        art_link: Optional[str],
        description: Optional[str],
        tags: List[str],
        status: CharacterRole,
        updated_at: Optional[datetime] = None,
    ) -> discord.Embed:
        return build_character_embed(
            name=name,
            ddb_link=ddb_link,
            character_thread_link=character_thread_link,
            token_link=token_link,
            art_link=art_link,
            description=description,
            tags=tags,
            status=status,
            updated_at=updated_at,
        )

    def _build_character_embed_from_model(self, character: Character) -> discord.Embed:
        return build_character_embed_from_model(
            character, updated_at=datetime.now(timezone.utc)
        )

    @staticmethod
    def _desired_thread_name(character: Character) -> str:
        base = f"Character: {character.name}".strip()
        if character.status is CharacterRole.INACTIVE:
            base = f"[Retired] {base}"
        return base[:90]

    async def _ensure_guild_cache(self, guild: discord.Guild) -> None:
        if guild.id not in self.bot.guild_data:
            await self.bot.load_or_create_guild_cache(guild)

    async def _get_cached_user(self, member: discord.Member) -> User:
        await self._ensure_guild_cache(member.guild)
        guild_entry = self.bot.guild_data[member.guild.id]

        user = guild_entry["users"].get(member.id)
        if user is not None:
            return user

        listener: Optional[commands.Cog] = self.bot.get_cog("ListnerCog")
        if listener is None:
            raise RuntimeError("Listener cog not loaded; cannot resolve users.")

        ensure_method = getattr(listener, "_ensure_cached_user", None)
        if ensure_method is None:
            raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

        user = await ensure_method(member)  # type: ignore[misc]
        return user

    def _next_character_id(self, guild_id: int) -> CharacterID:
        guild_entry = self.bot.guild_data[guild_id]
        db = guild_entry["db"]
        coll = db["characters"]
        while True:
            candidate = CharacterID.generate()
            exists = coll.count_documents(
                {"guild_id": guild_id, "character_id": str(candidate)}, limit=1
            )
            if not exists:
                return candidate

    def _persist_character(self, guild_id: int, character: Character) -> None:
        if BOT_FLUSH_VIA_ADAPTER:
            from app.bot.database import db_client
            upsert_character_sync(db_client, guild_id, character)
            return
        guild_entry = self.bot.guild_data[guild_id]
        db = guild_entry["db"]
        character.guild_id = guild_id
        doc = to_bson(character)
        doc["guild_id"] = guild_id
        doc["character_id"] = str(character.character_id)
        db["characters"].update_one(
            {"guild_id": guild_id, "character_id": str(character.character_id)},
            {"$set": doc},
            upsert=True,
        )

    @character.command(
        name="create",
        description="Start a DM wizard to create a new character profile.",
    )
    @app_commands.guild_only()
    async def character_create(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can create characters.", ephemeral=True
            )
            return

        if member.id in self._active_dm_sessions:
            await interaction.response.send_message(
                "You already have an active character creation session. Check your DMs or wait for it to finish.",
                ephemeral=True,
            )
            return

        self._active_dm_sessions.add(member.id)
        try:
            await interaction.response.send_message(
                "Check your DMs — I'll walk you through creating a character.",
                ephemeral=True,
            )

            try:
                dm_channel = await member.create_dm()
            except discord.Forbidden:
                await interaction.followup.send(
                    "I can't send you direct messages. Enable DMs from server members and run `/character create` again.",
                    ephemeral=True,
                )
                return

            session = CharacterCreationSession(self, interaction.guild, member, dm_channel)
            result = await session.run()

            if result.success:
                channel_info = (
                    result.announcement_channel.mention
                    if result.announcement_channel is not None
                    else "the configured character channel"
                )
                await interaction.followup.send(
                    f"Character `{result.character_name}` created successfully in {channel_info}.",
                    ephemeral=True,
                )
            else:
                message = result.error or "Character creation cancelled."
                await interaction.followup.send(message, ephemeral=True)
        finally:
            self._active_dm_sessions.discard(member.id)

    @character.command(name="list", description="List your characters.")
    @app_commands.guild_only()
    async def character_list(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can list characters.", ephemeral=True
            )
            return

        characters = await self._owned_character_docs(interaction.guild, member)

        if not characters:
            await interaction.response.send_message(
                "You do not have any characters yet. Use `/character create` to start a new profile.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{member.display_name}'s Characters",
            colour=discord.Color.green(),
        )
        for doc in characters:
            char_id = self._normalize_character_id(doc.get("character_id"))
            status_value = doc.get("status") or CharacterRole.ACTIVE.value
            status_prefix = "[Retired] " if status_value != CharacterRole.ACTIVE.value else ""
            embed.add_field(
                name=f"{status_prefix}{char_id} — {doc.get('name', 'Unnamed')}",
                value=doc.get("ddb_link", "No sheet link"),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @character.command(
        name="edit", description="Update a character profile via DM."
    )
    @app_commands.describe(character="Character ID (e.g. CHAR0001)")
    @app_commands.guild_only()
    async def character_edit(
        self, interaction: discord.Interaction, character: str
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can update characters.", ephemeral=True
            )
            return

        character_obj = await self._fetch_character(interaction.guild, character)
        if character_obj is None:
            await interaction.response.send_message(
                f"Character `{character}` was not found.", ephemeral=True
            )
            return

        if not self._can_manage_character(member, character_obj):
            await interaction.response.send_message(
                "You do not have permission to modify this character.",
                ephemeral=True,
            )
            return

        if member.id in self._active_dm_sessions:
            await interaction.response.send_message(
                "You already have an active character session. Complete or cancel it before starting a new one.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            dm_channel = await member.create_dm()
        except discord.Forbidden:
            await interaction.followup.send(
                "I can't send you direct messages. Enable DMs from server members and run `/character edit` again.",
                ephemeral=True,
            )
            return

        self._active_dm_sessions.add(member.id)
        try:
            session = CharacterUpdateSession(
                self, interaction.guild, member, dm_channel, character_obj
            )
            result = await session.run()
        finally:
            self._active_dm_sessions.discard(member.id)

        if not result.success or result.character is None:
            message = result.error or "Character update cancelled."
            await interaction.followup.send(message, ephemeral=True)
            return

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"{member.mention} updated character `{result.character.name}` ({result.character.character_id}).",
        )

        note = result.note or ""
        response = (
            f"Character `{result.character.name}` updated successfully."
            + (f"\n{note}" if note else "")
        )
        await interaction.followup.send(response, ephemeral=True)

    @character.command(
        name="state", description="Set a character's status to active or retired."
    )
    @app_commands.describe(
        character="Character ID (e.g. CHAR0001)",
        state="Choose the new state for the character.",
    )
    @app_commands.choices(
        state=[
            app_commands.Choice(name="Active", value="active"),
            app_commands.Choice(name="Retired", value="retired"),
        ]
    )
    @app_commands.guild_only()
    async def character_state(
        self,
        interaction: discord.Interaction,
        character: str,
        state: app_commands.Choice[str],
    ) -> None:
        target_status = (
            CharacterRole.ACTIVE if state.value == "active" else CharacterRole.INACTIVE
        )
        success_message = (
            "Character `{name}` has been restored to active status."
            if target_status is CharacterRole.ACTIVE
            else "Character `{name}` has been retired."
        )
        already_message = (
            "Character `{name}` is already active."
            if target_status is CharacterRole.ACTIVE
            else "Character `{name}` is already retired."
        )
        await self._handle_status_change(
            interaction,
            character,
            target_status=target_status,
            success_message=success_message,
            already_message=already_message,
        )

    @character.command(
        name="show",
        description="Get the announcement link for one of your characters.",
    )
    @app_commands.describe(character="Character ID (e.g. CHAR0001)")
    @app_commands.guild_only()
    async def character_show(
        self, interaction: discord.Interaction, character: str
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can inspect characters.", ephemeral=True
            )
            return

        character_obj = await self._fetch_character(interaction.guild, character)
        if character_obj is None:
            await interaction.response.send_message(
                f"Character `{character}` was not found.", ephemeral=True
            )
            return

        if not self._can_manage_character(member, character_obj):
            await interaction.response.send_message(
                "You do not have permission to view this character's announcement.",
                ephemeral=True,
            )
            return

        channel_id = character_obj.announcement_channel_id
        message_id = character_obj.announcement_message_id
        if not channel_id or not message_id:
            await interaction.response.send_message(
                "No announcement link is stored for this character.", ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await interaction.guild.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden, discord.NotFound):
                channel = None
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "The stored announcement channel could not be accessed.", ephemeral=True
            )
            return

        jump_url: str = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{message_id}"
        try:
            message = await channel.fetch_message(message_id)
            jump_url = message.jump_url
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        embed = discord.Embed(
            title=f"{character_obj.name}",
            description=f"Character ID: `{character_obj.character_id}`",
            colour=discord.Colour.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="Status",
            value=self._status_label(character_obj.status),
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=channel.mention,
            inline=True,
        )
        if character_obj.ddb_link:
            embed.add_field(name="Sheet", value=character_obj.ddb_link, inline=False)

        view = CharacterLinkView(jump_url)
        await interaction.response.send_message(
            "Here's your character announcement link:",
            ephemeral=True,
            embed=embed,
            view=view,
        )

    async def _character_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return []
        try:
            docs = await self._owned_character_docs(interaction.guild, interaction.user)
        except Exception:
            return []

        current_lower = current.lower()
        choices: List[app_commands.Choice[str]] = []
        for doc in docs:
            char_id = self._normalize_character_id(doc.get("character_id"))
            name = doc.get("name", "Unnamed")
            display = f"{name} ({char_id})"
            if current_lower and current_lower not in display.lower():
                continue
            choices.append(app_commands.Choice(name=display[:100], value=char_id))
            if len(choices) >= 25:
                break
        return choices

    @character_edit.autocomplete("character")
    async def character_edit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._character_autocomplete(interaction, current)

    @character_state.autocomplete("character")
    async def character_state_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._character_autocomplete(interaction, current)

    @character_show.autocomplete("character")
    async def character_show_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        return await self._character_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(CharacterCommandsCog(bot))
