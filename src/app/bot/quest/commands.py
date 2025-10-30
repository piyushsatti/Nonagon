from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import discord
from app.bot.cogs._staff_utils import is_allowed_staff
from app.domain.models.EntityIDModel import QuestID
from app.domain.models.QuestModel import PlayerStatus, QuestStatus

from .sessions import (
    QuestAnnounceView,
    QuestCreationSession,
    QuestUpdateSession,
)

if TYPE_CHECKING:
    from app.bot.cogs.QuestCommandsCog import QuestCommandsCog


async def quest_create(cog: "QuestCommandsCog", interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a guild.", ephemeral=True
        )
        return

    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message(
            "Only guild members can manage quests.", ephemeral=True
        )
        return

    try:
        user = await cog._get_cached_user(member)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    if not user.is_referee and not is_allowed_staff(cog.bot, member):
        await interaction.response.send_message(
            "You need the REFEREE role or an allowed staff role to create quests.",
            ephemeral=True,
        )
        return

    if member.id in cog._active_quest_sessions:
        await interaction.response.send_message(
            "You already have an active quest session. Complete or cancel it before starting a new one.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    cog._active_quest_sessions.add(member.id)
    try:
        try:
            dm_channel = await member.create_dm()
        except discord.Forbidden:
            await interaction.followup.send(
                "I can't send you direct messages. Enable DMs from server members and run `/quest create` again.",
                ephemeral=True,
            )
            return

        session = QuestCreationSession(cog, interaction.guild, member, user, dm_channel)
        try:
            result = await session.run()
        except RuntimeError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not result.success or result.quest is None:
            await interaction.followup.send(
                result.error or "Quest creation cancelled.",
                ephemeral=True,
            )
            return

        quest = result.quest
        cog._persist_quest(interaction.guild.id, quest)
        dm_sent = True
        dm_message = (
            f"Quest `{quest.quest_id}` is saved as a draft.\n"
            f"Run `/quest announce` in the server with Quest ID `{quest.quest_id}` when you're ready to publish, "
            "or `/quest edit` to make further changes."
        )
        try:
            await session.send_completion_summary(quest, dm_message)
        except RuntimeError:
            dm_sent = False
        except Exception:
            dm_sent = False

        reply = (
            f"Quest `{quest.quest_id}` drafted. "
            "Use `/quest announce` when you're ready to publish it."
        )
        if dm_sent:
            reply += " I sent you a DM with the preview and next steps."
        else:
            reply += " I couldn't DM you the preview—check your privacy settings."

        post_view = QuestAnnounceView(
            cog,
            session,
            interaction.guild,
            member,
            quest,
        )
        await session._update_preview(
            quest,
            header=(
                "**Quest Draft Saved**\n"
                "Announce immediately or schedule an announcement using the buttons below."
            ),
            view=post_view,
        )

        await interaction.followup.send(reply, ephemeral=True)
    finally:
        cog._active_quest_sessions.discard(member.id)


async def quest_announce(
    cog: "QuestCommandsCog",
    interaction: discord.Interaction,
    quest: str,
    time: Optional[str] = None,
) -> None:
    await interaction.response.defer(ephemeral=True)

    if interaction.guild is None:
        await interaction.followup.send(
            "This command can only be used inside a guild.", ephemeral=True
        )
        return

    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.followup.send(
            "Only guild members can manage quests.", ephemeral=True
        )
        return

    try:
        quest_id = QuestID.parse(quest.upper())
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    existing = cog._fetch_quest(interaction.guild.id, quest_id)
    if existing is None:
        await interaction.followup.send("Quest not found.", ephemeral=True)
        return

    try:
        user = await cog._get_cached_user(member)
    except RuntimeError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    if user.user_id != existing.referee_id and not is_allowed_staff(cog.bot, member):
        await interaction.followup.send(
            "Only the quest referee or allowed staff can announce this quest.",
            ephemeral=True,
        )
        return

    if existing.channel_id and existing.message_id and not time:
        await interaction.followup.send(
            "This quest has already been announced.", ephemeral=True
        )
        return

    if time:
        parsed_time = cog._parse_datetime_input(time)
        if parsed_time is None:
            await interaction.followup.send(
                "Could not parse the provided time. Enter epoch seconds (UTC).",
                ephemeral=True,
            )
            return
        if parsed_time <= datetime.now(timezone.utc):
            await interaction.followup.send(
                "Scheduled time must be in the future.", ephemeral=True
            )
            return
        existing.announce_at = parsed_time
        existing.status = QuestStatus.DRAFT
        cog._persist_quest(interaction.guild.id, existing)
        await interaction.followup.send(
            f"Quest `{existing.quest_id}` will be announced at <t:{int(parsed_time.timestamp())}:F>.",
            ephemeral=True,
        )
        return

    if existing.channel_id and existing.message_id:
        await interaction.followup.send(
            "Quest is already announced. Use `/quest nudge` or `/quest edit` instead.",
            ephemeral=True,
        )
        return

    try:
        await cog._announce_quest_now(
            interaction.guild,
            existing,
            invoker=member,
            fallback_channel=interaction.channel
            if isinstance(interaction.channel, discord.TextChannel)
            else None,
        )
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("Quest announce failed: %s", exc)
        await interaction.followup.send(
            "Unable to announce the quest right now. Please try again shortly.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        f"Quest `{existing.quest_id}` announced in <#{existing.channel_id}>.",
        ephemeral=True,
    )


async def quest_nudge(
    cog: "QuestCommandsCog", interaction: discord.Interaction, quest: str
) -> None:
    await interaction.response.defer(ephemeral=True)
    if interaction.guild is None:
        await interaction.followup.send(
            "This command can only be used inside a guild.", ephemeral=True
        )
        return

    try:
        quest_id = QuestID.parse(quest.upper())
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    try:
        message = await cog._execute_nudge(interaction, quest_id)
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("Quest nudge failed: %s", exc)
        await interaction.followup.send("Unable to nudge the quest right now.", ephemeral=True)
        return

    await interaction.followup.send(message, ephemeral=True)


async def quest_cancel(
    cog: "QuestCommandsCog", interaction: discord.Interaction, quest: str
) -> None:
    await interaction.response.defer(ephemeral=True)
    if interaction.guild is None:
        await interaction.followup.send(
            "This command can only be used inside a guild.", ephemeral=True
        )
        return

    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.followup.send(
            "Only guild members can manage quests.", ephemeral=True
        )
        return

    try:
        quest_id = QuestID.parse(quest.upper())
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    existing = cog._fetch_quest(interaction.guild.id, quest_id)
    if existing is None:
        await interaction.followup.send("Quest not found.", ephemeral=True)
        return

    try:
        user = await cog._get_cached_user(member)
    except RuntimeError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    if user.user_id != existing.referee_id and not is_allowed_staff(cog.bot, member):
        await interaction.followup.send(
            "Only the quest referee or allowed staff can cancel this quest.",
            ephemeral=True,
        )
        return

    existing.set_cancelled()
    existing.announce_at = None
    cog._persist_quest(interaction.guild.id, existing)

    if existing.channel_id and existing.message_id:
        try:
            await cog._sync_quest_announcement(
                interaction.guild,
                existing,
                approved_by_display=cog.lookup_user_display(
                    interaction.guild.id, existing.referee_id
                ),
                last_updated_at=datetime.now(timezone.utc),
                view=None,
            )
        except Exception:
            logging.exception(
                "Failed to update cancelled quest %s in guild %s",
                existing.quest_id,
                interaction.guild.id,
            )
        await cog._remove_signup_view(interaction.guild, existing)

    await interaction.followup.send(
        f"Quest `{existing.quest_id}` cancelled.", ephemeral=True
    )


async def quest_players(
    cog: "QuestCommandsCog", interaction: discord.Interaction, quest: str
) -> None:
    await interaction.response.defer(ephemeral=True)

    if interaction.guild is None:
        await interaction.followup.send(
            "This command can only be used inside a guild.", ephemeral=True
        )
        return

    try:
        quest_id = QuestID.parse(quest.upper())
    except ValueError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    existing = cog._fetch_quest(interaction.guild.id, quest_id)
    if existing is None:
        await interaction.followup.send("Quest not found.", ephemeral=True)
        return

    if existing.status is not QuestStatus.COMPLETED:
        await interaction.followup.send(
            "Player list is available after the quest is marked as completed.",
            ephemeral=True,
        )
        return

    selected_lines: List[str] = []
    pending_lines: List[str] = []
    for signup in existing.signups:
        user_display = cog.lookup_user_display(
            interaction.guild.id, signup.user_id
        )
        label = f"{user_display} — `{signup.character_id}`"
        if signup.status is PlayerStatus.SELECTED:
            selected_lines.append(label)
        else:
            pending_lines.append(label)

    if not selected_lines and not pending_lines:
        await interaction.followup.send(
            "No player signups were recorded for this quest.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"Players for {existing.title or existing.quest_id}",
        colour=discord.Colour.blurple(),
        timestamp=datetime.now(timezone.utc),
    )
    if selected_lines:
        embed.add_field(
            name="Selected Players",
            value="\n".join(selected_lines),
            inline=False,
        )
    else:
        embed.add_field(
            name="Selected Players",
            value="None recorded.",
            inline=False,
        )

    if pending_lines:
        embed.add_field(
            name="Pending Requests",
            value="\n".join(pending_lines),
            inline=False,
        )
    else:
        embed.add_field(
            name="Pending Requests",
            value="None pending.",
            inline=False,
        )

    await interaction.followup.send(embed=embed, ephemeral=True)


async def quest_edit(
    cog: "QuestCommandsCog", interaction: discord.Interaction, quest: str
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a guild.", ephemeral=True
        )
        return

    member = interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message(
            "Only guild members can manage quests.", ephemeral=True
        )
        return

    try:
        quest_id = QuestID.parse(quest.upper())
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    existing = cog._fetch_quest(interaction.guild.id, quest_id)
    if existing is None:
        await interaction.response.send_message("Quest not found.", ephemeral=True)
        return

    try:
        user = await cog._get_cached_user(member)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    if user.user_id != existing.referee_id and not is_allowed_staff(cog.bot, member):
        await interaction.response.send_message(
            "Only the quest referee or allowed staff can edit this quest.",
            ephemeral=True,
        )
        return

    if member.id in cog._active_quest_sessions:
        await interaction.response.send_message(
            "You already have an active quest session. Complete or cancel it before starting a new one.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    cog._active_quest_sessions.add(member.id)
    try:
        try:
            dm_channel = await member.create_dm()
        except discord.Forbidden:
            await interaction.followup.send(
                "I can't send you direct messages. Enable DMs from server members and run `/quest edit` again.",
                ephemeral=True,
            )
            return

        session = QuestUpdateSession(
            cog,
            interaction.guild,
            member,
            user,
            dm_channel,
            existing,
        )
        try:
            result = await session.run()
        except RuntimeError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        if not result.success or result.quest is None:
            await interaction.followup.send(
                result.error or "Quest update cancelled.",
                ephemeral=True,
            )
            return

        cog._persist_quest(interaction.guild.id, result.quest)
        if result.quest.channel_id and result.quest.message_id:
            await cog._sync_quest_announcement(
                interaction.guild,
                result.quest,
                last_updated_at=datetime.now(timezone.utc),
            )

        dm_summary_lines = [
            f"Quest `{result.quest.quest_id}` updated successfully."
        ]
        if result.quest.channel_id:
            dm_summary_lines.append(
                f"The announcement in <#{result.quest.channel_id}> has been refreshed."
            )
        dm_summary_lines.append(
            "Need more tweaks? Run `/quest edit` again at any time."
        )
        dm_sent = True
        try:
            await session.send_completion_summary(
                result.quest, "\n".join(dm_summary_lines)
            )
        except RuntimeError:
            dm_sent = False
        except Exception:
            dm_sent = False

        response = f"Quest `{result.quest.quest_id}` updated."
        if result.quest.channel_id:
            response += f" Announcement refreshed in <#{result.quest.channel_id}>."
        if dm_sent:
            response += " DM sent with the latest preview."
        else:
            response += " I couldn't DM the preview—check your privacy settings."

        if not result.quest.channel_id and result.quest.status is QuestStatus.DRAFT:
            post_view = QuestAnnounceView(
                cog,
                session,
                interaction.guild,
                member,
                result.quest,
            )
            await session._update_preview(
                result.quest,
                header=(
                    "**Quest Draft Saved**\n"
                    "Announce immediately or schedule an announcement using the buttons below."
                ),
                view=post_view,
            )

        await interaction.followup.send(response, ephemeral=True)
    finally:
        cog._active_quest_sessions.discard(member.id)
