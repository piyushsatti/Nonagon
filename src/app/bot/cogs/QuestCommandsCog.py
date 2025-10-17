from __future__ import annotations

import logging
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from pymongo import ReturnDocument

from app.bot.config import BOT_FLUSH_VIA_ADAPTER
from app.bot.utils.log_stream import send_demo_log
from app.domain.models.EntityIDModel import CharacterID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, PlayerStatus, Quest, QuestStatus
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_quest_sync


class JoinQuestModal(discord.ui.Modal):
    def __init__(self, cog: "QuestCommandsCog", quest_id: str) -> None:
        super().__init__(title=f"Join {quest_id}")
        self.cog = cog
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
            message = await self.cog._execute_join(
                interaction, quest_id_obj, char_id_obj
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send(message, ephemeral=True)


class QuestSignupView(discord.ui.View):
    def __init__(self, cog: "QuestCommandsCog", quest_id: Optional[str] = None) -> None:
        super().__init__(timeout=None)
        self.cog = cog
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
        label="Join Quest",
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
        # Respond with an ephemeral view containing a character select
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                "Unable to resolve characters outside a guild.", ephemeral=True
            )
            return

        class _EphemeralJoin(discord.ui.View):
            def __init__(
                self, cog: "QuestCommandsCog", quest_id: str, member: discord.Member
            ):
                super().__init__(timeout=60)
                self.add_item(CharacterSelect(cog, quest_id, member))

        await interaction.response.send_message(
            "Select your character to join:",
            view=_EphemeralJoin(self.cog, quest_id, interaction.user),
            ephemeral=True,
        )

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
            message = await self.cog._execute_leave(interaction, quest_id_obj)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        await interaction.followup.send(message, ephemeral=True)


class CharacterSelect(discord.ui.Select):
    def __init__(self, cog: "QuestCommandsCog", quest_id: str, member: discord.Member):
        self.cog = cog
        self.quest_id = quest_id
        self.member = member
        guild_entry = cog.bot.guild_data.get(member.guild.id)
        options: list[discord.SelectOption] = []
        if guild_entry is not None:
            db = guild_entry["db"]
            cursor = (
                db["characters"]
                .find(
                    {"owner_id.number": int(member.id)},
                    {"_id": 0, "character_id": 1, "name": 1},
                )
                .limit(25)
            )
            for doc in cursor:
                cid = doc.get("character_id", {})
                label = (
                    f"{cid.get('prefix','CHAR')}{int(cid.get('number',0)):04d}"
                    if isinstance(cid, dict)
                    else str(cid)
                )
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
                JoinQuestModal(self.cog, self.quest_id)
            )
            return

        try:
            quest_id_obj = QuestID.parse(self.quest_id)
            char_id_obj = CharacterID.parse(value)
            message = await self.cog._execute_join(
                interaction, quest_id_obj, char_id_obj
            )
        except Exception as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message(message, ephemeral=True)


class QuestCommandsCog(commands.Cog):
    """Slash commands for quest lifecycle management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        # Reuse listener helper to ensure cache consistency
        ensure_method = getattr(listener, "_ensure_cached_user", None)
        if ensure_method is None:
            raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

        user = await ensure_method(member)  # type: ignore[misc]
        return user

    def _next_quest_id(self, guild_id: int) -> QuestID:
        guild_entry = self.bot.guild_data[guild_id]
        db = guild_entry["db"]
        doc = db["counters"].find_one_and_update(
            {"_id": QuestID.prefix},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return QuestID(number=int(doc["seq"]))

    def _quest_to_doc(self, quest: Quest) -> dict:
        doc = asdict(quest)
        doc["guild_id"] = quest.guild_id
        doc.setdefault("quest_id", {})
        doc["quest_id"]["prefix"] = quest.quest_id.prefix
        doc.setdefault("referee_id", {})
        doc["referee_id"]["prefix"] = quest.referee_id.prefix
        if isinstance(quest.status, QuestStatus):
            doc["status"] = quest.status.value

        normalized_signups = []
        for signup in doc.get("signups", []):
            user_doc = signup.get("user_id", {})
            char_doc = signup.get("character_id", {})
            normalized_signups.append(
                {
                    "user_id": {
                        "prefix": UserID.prefix,
                        "number": user_doc.get("number"),
                    },
                    "character_id": {
                        "prefix": CharacterID.prefix,
                        "number": char_doc.get("number"),
                    },
                    "status": (
                        signup.get("status").value
                        if isinstance(signup.get("status"), PlayerStatus)
                        else signup.get("status")
                    ),
                }
            )
        doc["signups"] = normalized_signups
        if quest.duration is not None:
            doc["duration"] = quest.duration.total_seconds()
        return doc

    def _persist_quest(self, guild_id: int, quest: Quest) -> None:
        if BOT_FLUSH_VIA_ADAPTER:
            from app.bot.database import db_client

            upsert_quest_sync(db_client, guild_id, quest)
            return
        guild_entry = self.bot.guild_data[guild_id]
        db = guild_entry["db"]
        quest.guild_id = guild_id
        payload = self._quest_to_doc(quest)
        db["quests"].update_one(
            {"guild_id": guild_id, "quest_id.number": quest.quest_id.number},
            {"$set": payload},
            upsert=True,
        )

    def _quest_from_doc(self, guild_id: int, doc: dict) -> Quest:
        quest_id_doc = doc.get("quest_id", {})
        ref_doc = doc.get("referee_id", {})
        stored_gid = doc.get("guild_id", guild_id)

        quest = Quest(
            quest_id=QuestID(number=int(quest_id_doc.get("number"))),
            guild_id=int(stored_gid),
            referee_id=UserID(number=int(ref_doc.get("number"))),
            channel_id=doc["channel_id"],
            message_id=doc["message_id"],
            raw=doc.get("raw", ""),
            title=doc.get("title"),
            description=doc.get("description"),
            starting_at=doc.get("starting_at"),
            duration=(
                timedelta(seconds=float(doc["duration"]))
                if doc.get("duration") is not None
                else None
            ),
            image_url=doc.get("image_url"),
        )

        status_value = doc.get("status")
        if status_value:
            quest.status = (
                status_value
                if isinstance(status_value, QuestStatus)
                else QuestStatus(status_value)
            )

        quest.started_at = doc.get("started_at")
        quest.ended_at = doc.get("ended_at")

        signups: list[PlayerSignUp] = []
        for entry in doc.get("signups", []):
            uid = entry.get("user_id")
            cid = entry.get("character_id")
            status = entry.get("status")
            if uid is None or cid is None:
                continue
            user_id = (
                uid
                if isinstance(uid, UserID)
                else UserID(number=int(uid.get("number")))
            )
            char_id = (
                cid
                if isinstance(cid, CharacterID)
                else CharacterID(number=int(cid.get("number")))
            )
            signups.append(
                PlayerSignUp(
                    user_id=user_id,
                    character_id=char_id,
                    status=(
                        status
                        if isinstance(status, PlayerStatus)
                        else PlayerStatus(status) if status else PlayerStatus.APPLIED
                    ),
                )
            )

        quest.signups = signups
        return quest

    def _fetch_quest(self, guild_id: int, quest_id: QuestID) -> Optional[Quest]:
        guild_entry = self.bot.guild_data[guild_id]
        db = guild_entry["db"]
        doc = db["quests"].find_one(
            {
                "guild_id": guild_id,
                "quest_id.number": quest_id.number,
                "quest_id.prefix": quest_id.prefix,
            }
        )
        if doc is None:
            doc = db["quests"].find_one(
                {
                    "quest_id.number": quest_id.number,
                    "quest_id.prefix": quest_id.prefix,
                }
            )
            if doc is None:
                return None
        return self._quest_from_doc(guild_id, doc)

    async def quest_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        await self._ensure_guild_cache(interaction.guild)
        db = self.bot.guild_data[interaction.guild.id]["db"]
        cursor = (
            db["quests"]
            .find(
                {
                    "$or": [
                        {"guild_id": interaction.guild.id},
                        {"guild_id": {"$exists": False}},
                    ]
                },
                {"_id": 0, "quest_id": 1, "title": 1, "starting_at": 1},
            )
            .sort("starting_at", -1)
            .limit(20)
        )
        choices: list[app_commands.Choice[str]] = []
        term = (current or "").upper()
        for doc in cursor:
            qid = doc.get("quest_id", {})
            label = f"{qid.get('prefix','QUES')}{int(qid.get('number',0)):04d}"
            if term and term not in label:
                continue
            title = doc.get("title") or label
            choices.append(app_commands.Choice(name=f"{label} — {title}", value=label))
        return choices[:25]

    async def character_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            return []
        await self._ensure_guild_cache(interaction.guild)
        db = self.bot.guild_data[interaction.guild.id]["db"]
        cursor = (
            db["characters"]
            .find(
                {
                    "guild_id": interaction.guild.id,
                    "owner_id.number": int(interaction.user.id),
                },
                {"_id": 0, "character_id": 1, "name": 1},
            )
            .limit(20)
        )
        term = (current or "").upper()
        choices: list[app_commands.Choice[str]] = []
        for doc in cursor:
            cid = doc.get("character_id", {})
            label = (
                f"{cid.get('prefix','CHAR')}{int(cid.get('number',0)):04d}"
                if isinstance(cid, dict)
                else str(cid)
            )
            if term and term not in label:
                continue
            name = doc.get("name") or label
            choices.append(app_commands.Choice(name=f"{label} — {name}", value=label))
        return choices[:25]

    async def _execute_join(
        self,
        interaction: discord.Interaction,
        quest_id: QuestID,
        character_id: CharacterID,
    ) -> str:
        guild = interaction.guild
        if guild is None:
            raise ValueError("This action must be performed inside a guild.")

        member = interaction.user
        if not isinstance(member, discord.Member):
            raise ValueError("Only guild members can join quests.")

        user = await self._get_cached_user(member)

        if not user.is_player:
            raise ValueError(
                "You need the PLAYER role to join quests. Use `/character_add` first."
            )

        if not user.is_character_owner(character_id):
            raise ValueError("You can only join with characters you own.")

        quest = self._fetch_quest(guild.id, quest_id)
        if quest is None:
            raise ValueError("Quest not found.")

        if not quest.is_signup_open:
            raise ValueError("Signups are closed for this quest.")

        try:
            quest.add_signup(user.user_id, character_id)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        self._persist_quest(guild.id, quest)

        channel = guild.get_channel(int(quest.channel_id))
        if channel is None:
            try:
                channel = await guild.fetch_channel(int(quest.channel_id))
            except Exception as exc:  # pragma: no cover - best effort logging
                logging.debug(
                    "Unable to fetch quest channel %s in guild %s: %s",
                    quest.channel_id,
                    guild.id,
                    exc,
                )
                channel = None

        if channel is not None:
            await channel.send(
                f"{member.mention} joined quest `{quest.title or quest.quest_id}` with character `{str(character_id)}`."
            )

        await send_demo_log(
            self.bot,
            guild,
            f"{member.mention} joined quest `{quest.title or quest.quest_id}` with `{str(character_id)}`",
        )

        return (
            f"You have joined quest `{quest_id}` with character `{str(character_id)}`."
        )

    async def _execute_leave(
        self,
        interaction: discord.Interaction,
        quest_id: QuestID,
    ) -> str:
        guild = interaction.guild
        if guild is None:
            raise ValueError("This action must be performed inside a guild.")

        member = interaction.user
        if not isinstance(member, discord.Member):
            raise ValueError("Only guild members can leave quests.")

        quest = self._fetch_quest(guild.id, quest_id)
        if quest is None:
            raise ValueError("Quest not found.")

        try:
            quest.remove_signup(UserID(number=member.id))
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        self._persist_quest(guild.id, quest)

        channel = guild.get_channel(int(quest.channel_id))
        if channel is None:
            try:
                channel = await guild.fetch_channel(int(quest.channel_id))
            except Exception as exc:  # pragma: no cover - best effort logging
                logging.debug(
                    "Unable to fetch quest channel %s in guild %s: %s",
                    quest.channel_id,
                    guild.id,
                    exc,
                )
                channel = None

        if channel is not None:
            await channel.send(
                f"{member.mention} withdrew from quest `{quest.title or quest.quest_id}`."
            )

        await send_demo_log(
            self.bot,
            guild,
            f"{member.mention} withdrew from quest `{quest.title or quest.quest_id}`",
        )

        return f"You have been removed from quest `{quest_id}`."

    async def _remove_signup_view(self, guild: discord.Guild, quest: Quest) -> None:
        try:
            channel = guild.get_channel(int(quest.channel_id))
            if channel is None:
                channel = await guild.fetch_channel(int(quest.channel_id))
            message = await channel.fetch_message(int(quest.message_id))
            await message.edit(view=None)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logging.debug(
                "Unable to remove signup view for quest %s in guild %s: %s",
                quest.quest_id,
                guild.id,
                exc,
            )

    async def _send_summary_reminders(self, guild: discord.Guild, quest: Quest) -> None:
        if not quest.signups:
            return

        for signup in quest.signups:
            user_id = getattr(signup.user_id, "number", None)
            if user_id is None:
                continue

            user_record = (
                self.bot.guild_data.get(guild.id, {}).get("users", {}).get(user_id)
            )
            if user_record is not None and not getattr(user_record, "dm_opt_in", True):
                continue

            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    continue

            try:
                await member.send(
                    f"Thanks for playing `{quest.title or quest.quest_id}`! "
                    "Don't forget to submit your quest summary for bonus rewards."
                )
            except Exception as exc:  # pragma: no cover - DM failures expected
                logging.debug(
                    "Unable to DM summary reminder to user %s in guild %s: %s",
                    user_id,
                    guild.id,
                    exc,
                )

        await send_demo_log(
            self.bot,
            guild,
            f"Summary reminders sent for quest `{quest.title or quest.quest_id}`",
        )

    @app_commands.command(
        name="createquest", description="Create a new quest announcement."
    )
    @app_commands.describe(
        title="Quest title",
        description="Short quest description or hook",
        start_time_epoch="Quest start time as epoch seconds",
        duration_hours="Duration in hours (minimum 1)",
        image_url="Optional cover image URL",
    )
    async def createquest(
        self,
        interaction: discord.Interaction,
        title: str,
        start_time_epoch: app_commands.Range[int, 0],
        duration_hours: app_commands.Range[int, 1, 48],
        description: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None or interaction.channel is None:
            await interaction.followup.send(
                "This command can only be used inside a guild text channel.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                "Only guild members can create quests.", ephemeral=True
            )
            return

        start_time = datetime.fromtimestamp(start_time_epoch, tz=timezone.utc)

        try:
            user = await self._get_cached_user(member)
        except RuntimeError as exc:
            logging.exception("Failed to resolve user for quest creation: %s", exc)
            await interaction.followup.send(
                "Internal error resolving your profile; please try again later.",
                ephemeral=True,
            )
            return

        if not user.is_referee:
            await interaction.followup.send(
                "You need the REFEREE role to create quests.", ephemeral=True
            )
            return

        quest_id = self._next_quest_id(interaction.guild.id)
        duration = timedelta(hours=int(duration_hours))
        raw_markdown = f"## {title}\n\n{description or 'No description provided.'}"

        embed = discord.Embed(
            title=title,
            description=description or "No description provided.",
            colour=discord.Color.blurple(),
        )
        start_epoch = int(start_time.timestamp())
        embed.add_field(
            name="Starts",
            value=f"<t:{start_epoch}:F>",
            inline=True,
        )
        embed.add_field(name="Countdown", value=f"<t:{start_epoch}:R>", inline=True)
        embed.add_field(name="Duration", value=f"{int(duration_hours)}h", inline=True)
        embed.set_footer(text=f"Quest ID: {quest_id}")
        if image_url:
            embed.set_image(url=image_url)

        announcement = await interaction.channel.send(
            content=f"{member.mention} scheduled a quest!",
            embed=embed,
            view=QuestSignupView(self, str(quest_id)),
        )

        quest = Quest(
            quest_id=quest_id,
            guild_id=interaction.guild.id,
            referee_id=user.user_id,
            channel_id=str(announcement.channel.id),
            message_id=str(announcement.id),
            raw=raw_markdown,
            title=title,
            description=description,
            starting_at=start_time,
            duration=duration,
            image_url=image_url,
        )

        try:
            quest.validate_quest()
        except ValueError as exc:
            await announcement.delete()
            await interaction.followup.send(
                f"Quest validation failed: {exc}", ephemeral=True
            )
            return

        self._persist_quest(interaction.guild.id, quest)
        logging.info(
            "Quest %s created by %s in guild %s",
            quest.quest_id,
            member.id,
            interaction.guild.id,
        )

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"Quest `{quest.quest_id}` created by {member.mention} in {interaction.channel.mention}",
        )

        await interaction.followup.send(
            f"Quest `{quest.quest_id}` created and announced in {announcement.channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="joinquest",
        description="Join an announced quest with one of your characters.",
    )
    @app_commands.autocomplete(
        quest_id=quest_id_autocomplete, character_id=character_id_autocomplete
    )
    @app_commands.describe(
        quest_id="Quest identifier (e.g. QUES0001)",
        character_id="Character identifier (e.g. CHAR0001)",
    )
    async def joinquest(
        self,
        interaction: discord.Interaction,
        quest_id: str,
        character_id: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
            char_id_obj = CharacterID.parse(character_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            message = await self._execute_join(interaction, quest_id_obj, char_id_obj)
        except RuntimeError as exc:
            logging.exception("Failed to resolve user for quest join: %s", exc)
            await interaction.followup.send(
                "Internal error resolving your profile; please try again later.",
                ephemeral=True,
            )
            return
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="leavequest", description="Withdraw from a quest signup."
    )
    @app_commands.autocomplete(quest_id=quest_id_autocomplete)
    @app_commands.describe(
        quest_id="Quest identifier (e.g. QUES0001)",
    )
    async def leavequest(
        self,
        interaction: discord.Interaction,
        quest_id: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            message = await self._execute_leave(interaction, quest_id_obj)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="startquest", description="Close signups and mark a quest as started."
    )
    @app_commands.describe(quest_id="Quest identifier (e.g. QUES0001)")
    async def startquest(self, interaction: discord.Interaction, quest_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                "Only guild members can start quests.", ephemeral=True
            )
            return

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        quest = self._fetch_quest(interaction.guild.id, quest_id_obj)
        if quest is None:
            await interaction.followup.send("Quest not found.", ephemeral=True)
            return

        if quest.referee_id.number != member.id:
            await interaction.followup.send(
                "Only the quest referee can start the quest.", ephemeral=True
            )
            return

        quest.close_signups()
        quest.started_at = datetime.now(timezone.utc)

        self._persist_quest(interaction.guild.id, quest)
        logging.info(
            "Quest %s started by %s in guild %s",
            quest_id_obj,
            member.id,
            interaction.guild.id,
        )

        await self._remove_signup_view(interaction.guild, quest)

        channel = interaction.guild.get_channel(int(quest.channel_id))
        if channel is not None:
            await channel.send(
                f"Quest `{quest.title or quest.quest_id}` has started! Signups are now closed."
            )

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"Quest `{quest.title or quest.quest_id}` started by {member.mention}",
        )

        await interaction.followup.send(
            f"Quest `{quest_id_obj}` marked as started.", ephemeral=True
        )

    @app_commands.command(
        name="endquest",
        description="Mark a quest as completed and record the finish time.",
    )
    @app_commands.describe(quest_id="Quest identifier (e.g. QUES0001)")
    async def endquest(self, interaction: discord.Interaction, quest_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                "Only guild members can end quests.", ephemeral=True
            )
            return

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        quest = self._fetch_quest(interaction.guild.id, quest_id_obj)
        if quest is None:
            await interaction.followup.send("Quest not found.", ephemeral=True)
            return

        if quest.referee_id.number != member.id:
            await interaction.followup.send(
                "Only the quest referee can end the quest.", ephemeral=True
            )
            return

        quest.set_completed()
        quest.ended_at = datetime.now(timezone.utc)

        self._persist_quest(interaction.guild.id, quest)
        logging.info(
            "Quest %s ended by %s in guild %s",
            quest_id_obj,
            member.id,
            interaction.guild.id,
        )

        await self._remove_signup_view(interaction.guild, quest)

        channel = interaction.guild.get_channel(int(quest.channel_id))
        if channel is not None:
            await channel.send(
                f"Quest `{quest.title or quest.quest_id}` has been marked as completed. Please submit your summaries!"
            )

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"Quest `{quest.title or quest.quest_id}` completed by {member.mention}",
        )

        await self._send_summary_reminders(interaction.guild, quest)

        await interaction.followup.send(
            f"Quest `{quest_id_obj}` marked as completed.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    cog = QuestCommandsCog(bot)
    await bot.add_cog(cog)
    bot.add_view(QuestSignupView(cog))
