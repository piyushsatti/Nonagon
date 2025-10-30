from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import discord
import pytest
import pytest_asyncio
from discord.ext import commands

from app.bot.cogs.quests.cog import QuestCommandsCog
from app.domain.models.EntityIDModel import QuestID, UserID
from app.domain.models.QuestModel import Quest


@pytest_asyncio.fixture
async def bot():
    intents = discord.Intents.none()
    client = commands.Bot(command_prefix="!", intents=intents)
    try:
        yield client
    finally:
        await client.close()


def _build_quest() -> Quest:
    return Quest(
        quest_id=QuestID.parse("QUES0001"),
        guild_id=123,
        referee_id=UserID.parse("USER0001"),
        channel_id="456",
        message_id="789",
        raw="Quest body",
        title="Golden Apple",
        description="Retrieve the golden apple.",
        starting_at=datetime.now(timezone.utc) + timedelta(days=1),
    )


def test_build_nudge_embed_includes_jump_link(bot):
    cog = QuestCommandsCog(bot)
    quest = _build_quest()
    member = SimpleNamespace(mention="@Ref")
    jump_url = "https://discord.com/channels/123/456/789"
    bumped_at = datetime.now(timezone.utc)

    embed = cog._build_nudge_embed(quest, member, jump_url, bumped_at=bumped_at)

    assert embed.title == "Quest Nudge: Golden Apple"
    assert jump_url in embed.description
    assert embed.timestamp == bumped_at
    assert f"Quest ID: {quest.quest_id}" in embed.footer.text


@pytest.mark.asyncio
async def test_emit_nudge_log_invokes_demo_log(bot):
    cog = QuestCommandsCog(bot)
    calls: list[tuple] = []

    async def fake_demo_log(bot_arg, guild_arg, message):
        calls.append((bot_arg, guild_arg, message))

    cog._demo_log = fake_demo_log

    guild = SimpleNamespace(id=123)
    member = SimpleNamespace(mention="@Ref")

    await cog._emit_nudge_log(guild, member, "Golden Apple")

    assert calls
    logged_bot, logged_guild, message = calls[0]
    assert logged_bot is bot
    assert logged_guild is guild
    assert "Golden Apple" in message
    assert member.mention in message
