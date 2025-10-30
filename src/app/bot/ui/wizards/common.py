from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Generic, Optional, TypeVar

import discord

TModel = TypeVar("TModel")
TResult = TypeVar("TResult")


async def send_ephemeral_message(
    interaction: discord.Interaction,
    message: str,
    *,
    ephemeral: bool = True,
) -> Optional[discord.Message]:
    """Send an ephemeral message, handling initial responses and followups."""
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(message, ephemeral=ephemeral)
        return await interaction.response.send_message(message, ephemeral=ephemeral)
    except Exception:
        return None


class WizardSessionBase:
    """Shared helpers for DM-based wizard sessions."""

    def __init__(
        self,
        *,
        bot: discord.Client,
        guild: discord.Guild,
        member: discord.Member,
        dm_channel: discord.DMChannel,
        timeout: int,
    ) -> None:
        self.bot = bot
        self.guild = guild
        self.member = member
        self.dm = dm_channel
        self.timeout = timeout
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

    async def _flash_message(
        self,
        interaction: discord.Interaction,
        message: str,
        *,
        delay: float = 5.0,
    ) -> None:
        delivered = await send_ephemeral_message(interaction, message)
        if delivered is None:
            with suppress(Exception):
                await self._safe_send(message)
            return
        if delay <= 0:
            return
        try:
            await asyncio.sleep(delay)
            await interaction.delete_original_response()
        except Exception:
            pass

    async def _update_preview(
        self,
        model: TModel,
        *,
        header: Optional[str] = None,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        embed = self._build_preview_embed(model)
        content = header or "**Current preview:**"
        if self._preview_message is None:
            self._preview_message = await self._safe_send(
                content,
                embed=embed,
                view=view,
            )
            return
        try:
            await self._preview_message.edit(content=content, embed=embed, view=view)
        except discord.HTTPException:
            self._preview_message = await self._safe_send(
                content,
                embed=embed,
                view=view,
            )

    def _build_preview_embed(self, model: TModel) -> discord.Embed:  # pragma: no cover - abstract
        raise NotImplementedError


class PreviewWizardContext(Generic[TModel, TResult]):
    def __init__(
        self,
        session: WizardSessionBase,
        payload: TModel,
        *,
        mode: str,
        timeout: Optional[int] = None,
    ) -> None:
        self.session = session
        self.payload = payload
        self.mode = mode
        self.timeout = timeout or session.timeout
        self.future: asyncio.Future[TResult] = session.bot.loop.create_future()

    def resolve(self, result: TResult) -> None:
        if not self.future.done():
            self.future.set_result(result)


class PreviewWizardView(discord.ui.View, Generic[TModel, TResult]):
    def __init__(self, context: PreviewWizardContext[TModel, TResult]) -> None:
        super().__init__(timeout=context.timeout)
        self.context = context
        self._all_items: list[discord.ui.Item] = list(self.children)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.context.session.member.id:
            await send_ephemeral_message(
                interaction,
                "This wizard is controlled by someone else.",
            )
            return False
        return True

    async def on_timeout(self) -> None:
        result = self.build_result(
            False,
            error="Wizard timed out. Start again when you're ready.",
        )
        self.context.resolve(result)
        try:
            await self.context.session._update_preview(self.context.payload, view=None)
        except Exception:
            pass
        self.stop()

    def build_result(
        self,
        success: bool,
        *,
        error: Optional[str] = None,
    ) -> TResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def _set_disabled(self, value: bool) -> None:
        for item in self._all_items:
            item.disabled = value


class ContextAwareModal(discord.ui.Modal):
    def __init__(
        self,
        context: PreviewWizardContext[TModel, TResult],
        view: PreviewWizardView[TModel, TResult],
        *,
        title: str,
    ) -> None:
        super().__init__(title=title)
        self.context = context
        self.view = view


def parse_epoch_seconds(value: str) -> Optional[datetime]:
    text = value.strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    try:
        return datetime.fromtimestamp(int(text), tz=timezone.utc)
    except (OverflowError, ValueError):
        return None


def parse_positive_hours(value: str) -> Optional[timedelta]:
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


def validate_length(value: str, *, minimum: int = 0, maximum: int, field: str) -> str:
    text = value.strip()
    if len(text) < minimum:
        raise ValueError(f"{field} must be at least {minimum} characters long.")
    if len(text) > maximum:
        raise ValueError(f"{field} must be {maximum} characters or fewer.")
    return text


def validate_http_url(value: str) -> str:
    from urllib.parse import urlparse

    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Please provide a valid URL (http/https).")
    return url


def sanitize_comma_separated(value: str, *, max_items: int) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if len(items) > max_items:
        raise ValueError(f"Please provide {max_items} or fewer entries.")
    return items
