from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.abc import Messageable
from discord.ext import commands
from pymongo import ReturnDocument

from app.bot.config import (
    BOT_FLUSH_VIA_ADAPTER,
    FORGE_CHANNEL_IDS,
    QUEST_API_BASE_URL,
    QUEST_BOARD_CHANNEL_ID,
)
from app.bot.utils.log_stream import send_demo_log
from app.bot.utils.quest_embeds import QuestEmbedData, QuestEmbedRoster, build_quest_embed
from app.domain.models.EntityIDModel import CharacterID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, PlayerStatus, Quest, QuestStatus
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_quest_sync


class ForgeDraftView(discord.ui.View):
    def __init__(self, cog: "QuestCommandsCog", message: discord.Message) -> None:
        super().__init__(timeout=None)
        self.cog = cog
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
            user = await self.cog._get_cached_user(interaction.user)
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
        key = (self.guild_id, self.message_id)
        state = self.cog._forge_previews.get(key)
        if state is None:
            state = ForgePreviewState()
            self.cog._forge_previews[key] = state
        return state

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

        draft = self.cog._parse_forge_draft(message.content)
        quest_id = f"DRAFT{self.message_id}"
        embed = self.cog._draft_to_embed(draft, quest_id=quest_id, referee_display=interaction.user.mention)

        state = self._preview_state()
        preview_link: Optional[str] = None

        if interaction.guild is not None:
            thread = None
            if state.thread_id:
                thread = interaction.guild.get_thread(state.thread_id)
                if thread is None:
                    try:
                        thread = await interaction.guild.fetch_channel(state.thread_id)
                    except Exception:
                        thread = None

            if thread is None:
                try:
                    name = f"Quest Preview {interaction.user.display_name}"[:90]
                    thread = await message.create_thread(name=name, auto_archive_duration=60)
                    state.thread_id = thread.id
                except Exception:
                    thread = None

            if thread is not None:
                if state.preview_message_id:
                    try:
                        preview_message = await thread.fetch_message(state.preview_message_id)
                        await preview_message.edit(embed=embed, content=None)
                    except Exception:
                        preview_message = await thread.send(embed=embed)
                        state.preview_message_id = preview_message.id
                else:
                    preview_message = await thread.send(embed=embed)
                    state.preview_message_id = preview_message.id

                state.last_rendered_at = datetime.now(timezone.utc)
                preview_link = thread.jump_url

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

        draft = self.cog._parse_forge_draft(message.content)

        try:
            result = await self.cog._approve_forge_draft(
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
            await interaction.followup.send(
                "Draft already removed.", ephemeral=True
            )
            return

        await self.cog._discard_forge_draft(interaction, source_message=message)
        await interaction.followup.send("Draft discarded.", ephemeral=True)



@dataclass(slots=True)
class ForgePreviewState:
    thread_id: Optional[int] = None
    preview_message_id: Optional[int] = None
    last_rendered_at: Optional[datetime] = None


@dataclass(slots=True)
class ForgeDraft:
    raw: str
    title: Optional[str] = None
    description: Optional[str] = None
    starting_at: Optional[datetime] = None
    duration: Optional[timedelta] = None
    image_url: Optional[str] = None


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
        self._forge_previews: dict[tuple[int, int], ForgePreviewState] = {}

    # ---------- Quest Embed Helpers ----------

    def _lookup_user_display(self, guild_id: int, user_id: UserID) -> str:
        guild_entry = self.bot.guild_data.get(guild_id)
        if guild_entry:
            for cached in guild_entry.get("users", {}).values():
                try:
                    if cached.user_id == user_id:
                        if cached.discord_id:
                            return f"<@{cached.discord_id}>"
                        return str(cached.user_id)
                except AttributeError:
                    continue
        return str(user_id)

    def _quest_to_embed_data(
        self,
        quest: Quest,
        guild: Optional[discord.Guild],
        *,
        referee_display: Optional[str] = None,
        approved_by_display: Optional[str] = None,
        last_updated_at: Optional[datetime] = None,
    ) -> QuestEmbedData:
        roster_selected: list[str] = []
        roster_pending: list[str] = []

        for signup in quest.signups:
            label = (
                f"{self._lookup_user_display(quest.guild_id, signup.user_id)} — {str(signup.character_id)}"
            )
            if signup.status is PlayerStatus.SELECTED:
                roster_selected.append(label)
            else:
                roster_pending.append(label)

        roster = QuestEmbedRoster(selected=roster_selected, pending=roster_pending)

        referee_label = referee_display
        if referee_label is None:
            referee_label = self._lookup_user_display(quest.guild_id, quest.referee_id)

        data = QuestEmbedData(
            quest_id=str(quest.quest_id),
            title=quest.title,
            description=quest.description,
            status=quest.status,
            starting_at=quest.starting_at,
            duration=quest.duration,
            referee_display=referee_label,
            roster=roster,
            image_url=quest.image_url,
            last_updated_at=last_updated_at or datetime.now(timezone.utc),
            approved_by_display=approved_by_display,
        )
        return data

    def _build_quest_embed(
        self,
        quest: Quest,
        guild: Optional[discord.Guild],
        *,
        referee_display: Optional[str] = None,
        approved_by_display: Optional[str] = None,
        last_updated_at: Optional[datetime] = None,
    ) -> discord.Embed:
        data = self._quest_to_embed_data(
            quest,
            guild,
            referee_display=referee_display,
            approved_by_display=approved_by_display,
            last_updated_at=last_updated_at,
        )
        return build_quest_embed(data)

    def _is_forge_channel(self, channel: Optional[Messageable]) -> bool:
        if channel is None:
            return False

        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return False

        if FORGE_CHANNEL_IDS:
            return int(channel_id) in FORGE_CHANNEL_IDS

        return False

    def _draft_to_embed(
        self,
        draft: ForgeDraft,
        *,
        quest_id: str,
        referee_display: str,
        status: QuestStatus = QuestStatus.DRAFT,
    ) -> discord.Embed:
        roster = QuestEmbedRoster()
        data = QuestEmbedData(
            quest_id=quest_id,
            title=draft.title,
            description=draft.description,
            status=status,
            starting_at=draft.starting_at,
            duration=draft.duration,
            referee_display=referee_display,
            roster=roster,
            image_url=draft.image_url,
            last_updated_at=datetime.now(timezone.utc),
            approved_by_display=referee_display,
        )
        return build_quest_embed(data)

    def _parse_forge_draft(self, raw: str) -> ForgeDraft:
        title: Optional[str] = None
        description_lines: list[str] = []
        starting_at: Optional[datetime] = None
        duration: Optional[timedelta] = None
        image_url: Optional[str] = None

        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                description_lines.append(stripped)
                continue

            key, sep, value = stripped.partition(":")
            if sep and key.lower() in {"title", "name", "quest"}:
                if not title:
                    title = value.strip() or None
                continue

            if sep and key.lower() in {"start", "starts", "when"}:
                parsed = self._parse_start_datetime(value)
                if parsed is not None:
                    starting_at = parsed
                    continue

            if sep and key.lower() in {"duration", "length"}:
                parsed_duration = self._parse_duration(value)
                if parsed_duration is not None:
                    duration = parsed_duration
                    continue

            if sep and key.lower() in {"image", "cover", "thumbnail"}:
                url = value.strip()
                if url.lower().startswith("http"):
                    image_url = url
                    continue

            description_lines.append(stripped)

        if title is None:
            for idx, line in enumerate(description_lines):
                if line:
                    title = line
                    description_lines = description_lines[idx + 1 :]
                    break

        description = "\n".join(description_lines).strip() or None

        return ForgeDraft(
            raw=raw,
            title=title,
            description=description,
            starting_at=starting_at,
            duration=duration,
            image_url=image_url,
        )

    def _parse_start_datetime(self, value: str) -> Optional[datetime]:
        text = value.strip()
        if not text:
            return None

        t_match = re.search(r"<t:(\d+)", text)
        if t_match:
            seconds = int(t_match.group(1))
            return datetime.fromtimestamp(seconds, tz=timezone.utc)

        normalized = text.replace("UTC", "+00:00").replace("utc", "+00:00")
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(normalized, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        try:
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None

    def _parse_duration(self, value: str) -> Optional[timedelta]:
        text = value.strip().lower()
        if not text:
            return None

        hours = 0
        minutes = 0
        match = re.findall(r"(\d+)\s*h", text)
        if match:
            hours = sum(int(m) for m in match)
        match_min = re.findall(r"(\d+)\s*m", text)
        if match_min:
            minutes = sum(int(m) for m in match_min)

        if hours == 0 and minutes == 0:
            try:
                hours = int(text)
            except ValueError:
                return None

        return timedelta(hours=hours, minutes=minutes)

    async def _cleanup_forge_preview(
        self, guild: discord.Guild, message_id: int
    ) -> None:
        state = self._forge_previews.pop((guild.id, message_id), None)
        if state is None:
            return

        if state.thread_id:
            thread = guild.get_thread(state.thread_id)
            if thread is None:
                try:
                    thread = await guild.fetch_channel(state.thread_id)
                except Exception:
                    thread = None
            if thread is not None:
                try:
                    await thread.delete()
                except Exception:
                    pass

    async def _resolve_board_channel(
        self, guild: discord.Guild, fallback: discord.TextChannel
    ) -> Messageable:
        if QUEST_BOARD_CHANNEL_ID:
            channel = guild.get_channel(QUEST_BOARD_CHANNEL_ID)
            if channel is None:
                try:
                    channel = await guild.fetch_channel(QUEST_BOARD_CHANNEL_ID)
                except Exception:
                    channel = None
            if channel is not None:
                return channel
        return fallback

    async def _approve_forge_draft(
        self,
        interaction: discord.Interaction,
        *,
        draft: ForgeDraft,
        author: discord.Member,
        source_message: discord.Message,
    ) -> Optional[str]:
        guild = interaction.guild
        if guild is None:
            return None

        board_channel = await self._resolve_board_channel(
            guild, fallback=source_message.channel
        )

        quest_id = self._next_quest_id(guild.id)

        quest = Quest(
            quest_id=quest_id,
            guild_id=guild.id,
            referee_id=UserID(number=author.id),
            channel_id=str(board_channel.id),
            message_id="0",
            raw=draft.raw,
            title=draft.title,
            description=draft.description,
            starting_at=draft.starting_at,
            duration=draft.duration,
            image_url=draft.image_url,
            status=QuestStatus.ANNOUNCED,
        )

        try:
            quest.validate_quest()
        except ValueError as exc:
            raise ValueError(f"Quest validation failed: {exc}")

        embed = self._draft_to_embed(
            draft,
            quest_id=str(quest_id),
            referee_display=author.mention,
            status=QuestStatus.ANNOUNCED,
        )

        announcement = await board_channel.send(
            content=f"{author.mention} scheduled a quest!",
            embed=embed,
            view=QuestSignupView(self, str(quest_id)),
        )

        quest.message_id = str(announcement.id)
        quest.channel_id = str(announcement.channel.id)
        persisted_via_api = await self._persist_quest_via_api(guild, quest)
        if not persisted_via_api:
            self._persist_quest(guild.id, quest)

        await self._cleanup_forge_preview(guild, source_message.id)

        try:
            await source_message.edit(view=None)
        except Exception:
            pass

        await send_demo_log(
            self.bot,
            guild,
            f"Quest `{quest.quest_id}` approved by {author.mention} in {board_channel.mention}",
        )

        return (
            f"Quest `{quest.quest_id}` announced in {announcement.channel.mention}."
        )

    async def _discard_forge_draft(
        self,
        interaction: discord.Interaction,
        *,
        source_message: discord.Message,
    ) -> None:
        if interaction.guild is None:
            return

        await self._cleanup_forge_preview(interaction.guild, source_message.id)

        try:
            await source_message.edit(view=None)
        except Exception:
            pass

    @commands.Cog.listener("on_message")
    async def _on_message_forge_hook(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if message.guild is None:
            return

        if not self._is_forge_channel(message.channel):
            return

        if not isinstance(message.author, discord.Member):
            return

        try:
            user = await self._get_cached_user(message.author)
        except Exception:
            return

        if not user.is_referee:
            return

        if message.components:
            return

        view = ForgeDraftView(self, message)
        try:
            await message.edit(view=view)
            logging.info(
                "Attached forge view to message %s in guild %s channel %s",
                message.id,
                message.guild.id,
                message.channel.id,
            )
        except Exception as exc:
            logging.debug(
                "Unable to attach forge view for message %s in guild %s: %s",
                message.id,
                message.guild.id,
                exc,
            )


    async def _sync_quest_announcement(
        self,
        guild: discord.Guild,
        quest: Quest,
        *,
        approved_by_display: Optional[str] = None,
        last_updated_at: Optional[datetime] = None,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        channel = guild.get_channel(int(quest.channel_id))
        if channel is None:
            try:
                channel = await guild.fetch_channel(int(quest.channel_id))
            except Exception as exc:  # pragma: no cover - defensive log
                logging.debug(
                    "Unable to resolve quest channel %s in guild %s: %s",
                    quest.channel_id,
                    guild.id,
                    exc,
                )
                return

        try:
            message = await channel.fetch_message(int(quest.message_id))
        except Exception as exc:  # pragma: no cover - defensive log
            logging.debug(
                "Unable to fetch quest message %s in guild %s: %s",
                quest.message_id,
                guild.id,
                exc,
            )
            return

        embed = self._build_quest_embed(
            quest,
            guild,
            approved_by_display=approved_by_display,
            last_updated_at=last_updated_at,
        )

        try:
            resolved_view = view
            if resolved_view is None and quest.is_signup_open:
                resolved_view = QuestSignupView(self, str(quest.quest_id))
            await message.edit(embed=embed, view=resolved_view)
        except Exception as exc:  # pragma: no cover - defensive log
            logging.debug(
                "Unable to update quest announcement %s in guild %s: %s",
                quest.quest_id,
                guild.id,
                exc,
            )

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

    async def _persist_quest_via_api(self, guild: discord.Guild, quest: Quest) -> bool:
        if not QUEST_API_BASE_URL:
            return False

        base_url = QUEST_API_BASE_URL.rstrip("/")
        url = f"{base_url}/v1/guilds/{guild.id}/quests"
        payload: dict[str, object] = {
            "quest_id": str(quest.quest_id),
            "referee_id": str(quest.referee_id),
            "raw": quest.raw,
            "title": quest.title,
            "description": quest.description,
            "image_url": quest.image_url,
            "linked_quests": [str(qid) for qid in quest.linked_quests],
            "linked_summaries": [str(sid) for sid in quest.linked_summaries],
        }

        if quest.starting_at is not None:
            payload["starting_at"] = quest.starting_at.isoformat()

        if quest.duration is not None:
            payload["duration_hours"] = int(quest.duration.total_seconds() // 3600)

        params = {
            "channel_id": quest.channel_id,
            "message_id": quest.message_id,
        }

        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, params=params) as resp:
                    if resp.status != 201:
                        text = await resp.text()
                        raise RuntimeError(
                            f"Quest API persistence failed with {resp.status}: {text}"
                        )
            return True
        except Exception as exc:
            logging.warning(
                "Falling back to direct quest persistence for %s in guild %s: %s",
                quest.quest_id,
                guild.id,
                exc,
            )
            return False

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
        quest.last_nudged_at = doc.get("last_nudged_at")

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

        await self._sync_quest_announcement(
            guild,
            quest,
            last_updated_at=datetime.now(timezone.utc),
        )

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

        await self._sync_quest_announcement(
            guild,
            quest,
            last_updated_at=datetime.now(timezone.utc),
        )

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

        quest = Quest(
            quest_id=quest_id,
            guild_id=interaction.guild.id,
            referee_id=user.user_id,
            channel_id=str(interaction.channel.id),
            message_id="",
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
            await interaction.followup.send(
                f"Quest validation failed: {exc}", ephemeral=True
            )
            return

        embed = self._build_quest_embed(
            quest,
            interaction.guild,
            referee_display=member.mention,
            approved_by_display=member.mention,
        )

        announcement = await interaction.channel.send(
            content=f"{member.mention} scheduled a quest!",
            embed=embed,
            view=QuestSignupView(self, str(quest_id)),
        )

        quest.channel_id = str(announcement.channel.id)
        quest.message_id = str(announcement.id)

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

        await self._sync_quest_announcement(
            interaction.guild,
            quest,
            last_updated_at=quest.started_at,
            view=None,
        )
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

        await self._sync_quest_announcement(
            interaction.guild,
            quest,
            last_updated_at=quest.ended_at,
            view=None,
        )
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
