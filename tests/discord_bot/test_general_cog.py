from types import SimpleNamespace

import discord

from app.bot.cogs.general import GeneralCog


class DummyBot:
    def __init__(self, latency: float, ready: bool = True) -> None:
        self._latency = latency
        self._ready = ready
        self._user = SimpleNamespace(name="TestBot", id=123456789012345678)

    @property
    def latency(self) -> float:
        return self._latency

    def is_ready(self) -> bool:
        return self._ready

    @property
    def user(self) -> SimpleNamespace:
        return self._user

    def __str__(self) -> str:  # pragma: no cover - best effort repr
        return f"{self.user.name}#{self.user.id}"


class FaultyReadyBot(DummyBot):
    def __init__(self, latency: float) -> None:
        super().__init__(latency)

    def is_ready(self) -> bool:  # type: ignore[override]
        raise RuntimeError("ready state unavailable")


def test_latency_message_formats_latency_ms() -> None:
    bot = DummyBot(latency=0.321)
    cog = GeneralCog(bot)

    message = cog.build_latency_message()

    assert message.startswith("Pong!")
    assert "321" in message  # latency formatted in milliseconds


def test_status_embed_reflects_ready_state() -> None:
    bot = DummyBot(latency=0.045, ready=True)
    cog = GeneralCog(bot)

    embed = cog.build_status_embed()

    assert embed.title == "Bot status"
    assert embed.fields[0].name == "Websocket latency"
    assert embed.fields[0].value == "45 ms"
    assert embed.fields[1].value == "Ready ✅"
    assert embed.colour == discord.Color.green()


def test_status_embed_handles_not_ready_and_exceptions() -> None:
    bot = DummyBot(latency=0.1, ready=False)
    cog = GeneralCog(bot)
    embed = cog.build_status_embed()
    assert embed.fields[1].value == "Starting ⏳"
    assert embed.colour == discord.Color.orange()

    faulty_bot = FaultyReadyBot(latency=0.2)
    faulty_cog = GeneralCog(faulty_bot)
    embed_faulty = faulty_cog.build_status_embed()
    assert embed_faulty.fields[1].value == "Starting ⏳"
