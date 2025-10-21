from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.cogs.QuestCommandsCog import QuestCommandsCog, SignupDecisionView
from app.domain.models.EntityIDModel import CharacterID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, Quest


def _build_quest() -> Quest:
    quest = Quest(
        quest_id=QuestID(number=1),
        guild_id=123,
        referee_id=UserID(number=999),
        channel_id="555",
        message_id="999",
        raw="",
        title="Test Quest",
    )
    return quest

def _make_interaction() -> SimpleNamespace:
    response = SimpleNamespace(
        defer=AsyncMock(),
        send_message=AsyncMock(),
    )
    followup = SimpleNamespace(send=AsyncMock())
    return SimpleNamespace(
        guild=SimpleNamespace(id=123456789),
        user=SimpleNamespace(id=987654321),
        response=response,
        followup=followup,
    )


@pytest.mark.asyncio
async def test_joinquest_success_confirmation_ephemeral() -> None:
    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)
    interaction = _make_interaction()

    cog._execute_join = AsyncMock(return_value="Signup confirmed.")

    await cog.joinquest(interaction, "QUES0001", "CHAR0001")

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    interaction.followup.send.assert_awaited_once_with("Signup confirmed.", ephemeral=True)


@pytest.mark.asyncio
async def test_joinquest_invalid_id_reply_ephemeral() -> None:
    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)
    interaction = _make_interaction()

    cog._execute_join = AsyncMock()

    await cog.joinquest(interaction, "bad", "CHAR0001")

    cog._execute_join.assert_not_called()
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert interaction.followup.send.await_count == 1
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True



@pytest.mark.asyncio
async def test_leavequest_success_confirmation_ephemeral() -> None:
    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)
    interaction = _make_interaction()

    cog._execute_leave = AsyncMock(return_value="Signup removed.")

    await cog.leavequest(interaction, "QUES0001")

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    interaction.followup.send.assert_awaited_once_with("Signup removed.", ephemeral=True)


@pytest.mark.asyncio
async def test_leavequest_invalid_id_reply_ephemeral() -> None:
    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)
    interaction = _make_interaction()

    cog._execute_leave = AsyncMock()

    await cog.leavequest(interaction, "bad")

    cog._execute_leave.assert_not_called()
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    assert interaction.followup.send.await_count == 1
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_signup_view_handle_accept_ephemeral(monkeypatch) -> None:
    monkeypatch.setattr("app.bot.cogs.QuestCommandsCog.send_demo_log", AsyncMock())

    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)

    quest = _build_quest()
    signup = PlayerSignUp(user_id=UserID(number=111), character_id=CharacterID(number=222))
    quest.signups.append(signup)

    guild = SimpleNamespace(
        id=quest.guild_id,
        get_member=lambda *_: None,
        fetch_member=AsyncMock(return_value=None),
        get_channel=lambda *_: None,
        fetch_channel=AsyncMock(return_value=None),
    )
    reviewer = SimpleNamespace(id=777, mention="<@777>", display_name="Reviewer", guild=guild)

    view = SignupDecisionView(
        cog=cog,
        guild=guild,
        quest=quest,
        reviewer=reviewer,
        pending=[signup],
    )
    view.selected_user_id = str(signup.user_id)
    view._notify_player = AsyncMock()
    view._notify_channel = AsyncMock()

    interaction = SimpleNamespace(
        guild=guild,
        user=reviewer,
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        message=SimpleNamespace(edit=AsyncMock()),
    )

    cog._select_signup_via_api = AsyncMock(return_value=False)
    cog._persist_quest = lambda *_: None
    cog._fetch_quest = lambda *_: None
    cog._sync_quest_announcement = AsyncMock()
    cog._format_signup_label = lambda *_: "<@111> — CHAR0222"

    await view.handle_accept(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_signup_view_handle_decline_ephemeral(monkeypatch) -> None:
    monkeypatch.setattr("app.bot.cogs.QuestCommandsCog.send_demo_log", AsyncMock())

    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)

    quest = _build_quest()
    signup = PlayerSignUp(user_id=UserID(number=111), character_id=CharacterID(number=222))
    quest.signups.append(signup)

    guild = SimpleNamespace(
        id=quest.guild_id,
        get_member=lambda *_: None,
        fetch_member=AsyncMock(return_value=None),
        get_channel=lambda *_: None,
        fetch_channel=AsyncMock(return_value=None),
    )
    reviewer = SimpleNamespace(id=777, mention="<@777>", display_name="Reviewer", guild=guild)

    view = SignupDecisionView(
        cog=cog,
        guild=guild,
        quest=quest,
        reviewer=reviewer,
        pending=[signup],
    )
    view.selected_user_id = str(signup.user_id)
    view._notify_player = AsyncMock()
    view._notify_channel = AsyncMock()

    interaction = SimpleNamespace(
        guild=guild,
        user=reviewer,
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        message=SimpleNamespace(edit=AsyncMock()),
    )

    cog._remove_signup_via_api = AsyncMock(return_value=False)
    cog._persist_quest = lambda *_: None
    cog._fetch_quest = lambda *_: None
    cog._sync_quest_announcement = AsyncMock()
    cog._format_signup_label = lambda *_: "<@111> — CHAR0222"

    await view.handle_decline(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_signup_view_handle_close_ephemeral(monkeypatch) -> None:
    monkeypatch.setattr("app.bot.cogs.QuestCommandsCog.send_demo_log", AsyncMock())

    bot = SimpleNamespace(guild_data={})
    cog = QuestCommandsCog(bot)

    quest = _build_quest()
    quest.signups.append(
        PlayerSignUp(user_id=UserID(number=111), character_id=CharacterID(number=222))
    )

    guild = SimpleNamespace(
        id=quest.guild_id,
        get_member=lambda *_: None,
        fetch_member=AsyncMock(return_value=None),
        get_channel=lambda *_: None,
        fetch_channel=AsyncMock(return_value=None),
    )
    reviewer = SimpleNamespace(id=777, mention="<@777>", display_name="Reviewer", guild=guild)

    view = SignupDecisionView(
        cog=cog,
        guild=guild,
        quest=quest,
        reviewer=reviewer,
        pending=list(quest.signups),
    )
    view.selected_user_id = str(quest.signups[0].user_id)
    view._notify_channel_closed = AsyncMock()
    view._notify_channel = AsyncMock()
    view._notify_player = AsyncMock()

    interaction = SimpleNamespace(
        guild=guild,
        user=reviewer,
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        message=SimpleNamespace(edit=AsyncMock()),
    )

    cog._close_signups_via_api = AsyncMock(return_value=False)
    cog._persist_quest = lambda *_: None
    cog._fetch_quest = lambda *_: None
    cog._sync_quest_announcement = AsyncMock()
    cog._format_signup_label = lambda *_: "<@111> — CHAR0222"

    await view.handle_close(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
    assert interaction.followup.send.await_args.kwargs["ephemeral"] is True
