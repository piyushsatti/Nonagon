from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.domain.models.LookupModel import LookupEntry
from app.domain.models.UserModel import User
from app.infra.mongo.lookup_repo import LookupRepoMongo


class LookupCommandsCog(commands.Cog):
    """Slash commands for managing quick reference lookups."""

    lookup = app_commands.Group(name="lookup", description="Manage lookup references")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.repo = LookupRepoMongo()


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

    async def _is_staff(self, member: discord.Member) -> bool:
        perms = member.guild_permissions
        if perms.manage_guild or perms.manage_messages or perms.administrator:
            return True

        try:
            user = await self._get_cached_user(member)
        except Exception:
            return False
        return user.is_referee

    async def _resolve_staff_member(self, interaction: discord.Interaction) -> Optional[discord.Member]:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return None

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can run lookup commands.", ephemeral=True
            )
            return None

        if not await self._is_staff(member):
            await interaction.response.send_message(
                "You need staff permissions (REFEREE or Manage Server) to use lookup commands.",
                ephemeral=True,
            )
            return None

        return member

    @lookup.command(name="add", description="Add or update a lookup entry")
    @app_commands.describe(name="Friendly identifier", url="Destination URL", description="Optional note shown in listings")
    async def lookup_add(
        self,
        interaction: discord.Interaction,
        name: str,
        url: str,
        description: Optional[str] = None,
    ) -> None:
        member = await self._resolve_staff_member(interaction)
        if member is None:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild_id = interaction.guild.id  # type: ignore[union-attr]
        existing = await self.repo.get_by_name(guild_id, name)

        now = datetime.now(timezone.utc)
        if existing is None:
            entry = LookupEntry(
                guild_id=guild_id,
                name=name.strip(),
                url=url.strip(),
                created_by=member.id,
                created_at=now,
                description=description.strip() if description else None,
            )
        else:
            entry = LookupEntry(
                guild_id=guild_id,
                name=name.strip(),
                url=url.strip(),
                created_by=existing.created_by,
                created_at=existing.created_at,
                description=description.strip() if description else existing.description,
            )

        entry.touch_updated(member.id, at=now)
        saved = await self.repo.upsert(entry)

        logging.info(
            "Lookup entry saved (guild=%s staff=%s name=%s)",
            guild_id,
            member.id,
            saved.name,
        )

        action = "Updated" if existing else "Stored"
        await interaction.followup.send(
            f"{action} lookup `{saved.name}` → {saved.url}", ephemeral=True
        )

    @lookup.command(name="get", description="Retrieve a lookup entry")
    @app_commands.describe(query="Name to search for")
    async def lookup_get(self, interaction: discord.Interaction, query: str) -> None:
        member = await self._resolve_staff_member(interaction)
        if member is None:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        match = await self.repo.find_best_match(interaction.guild.id, query)  # type: ignore[union-attr]
        if match is None:
            await interaction.followup.send("No lookup entry matched that query.", ephemeral=True)
            return

        embed = _build_lookup_embed(match)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @lookup.command(name="list", description="List lookup entries")
    async def lookup_list(self, interaction: discord.Interaction) -> None:
        member = await self._resolve_staff_member(interaction)
        if member is None:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        entries = await self.repo.list_all(interaction.guild.id)  # type: ignore[union-attr]

        if not entries:
            await interaction.followup.send("No lookup entries stored yet.", ephemeral=True)
            return

        view = LookupListView(entries, interaction.guild.name)  # type: ignore[union-attr]
        embed = view.render_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @lookup.command(name="remove", description="Remove a lookup entry")
    @app_commands.describe(name="Name to delete")
    async def lookup_remove(self, interaction: discord.Interaction, name: str) -> None:
        member = await self._resolve_staff_member(interaction)
        if member is None:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await self.repo.delete(interaction.guild.id, name)  # type: ignore[union-attr]

        if deleted:
            logging.info(
                "Lookup entry removed (guild=%s staff=%s name=%s)",
                interaction.guild.id,
                member.id,
                name,
            )
            await interaction.followup.send(f"Removed lookup `{name}`.", ephemeral=True)
        else:
            await interaction.followup.send(f"No lookup named `{name}` found.", ephemeral=True)


def _build_lookup_embed(entry: LookupEntry) -> discord.Embed:
    embed = discord.Embed(
        title=entry.name,
        description=entry.description or "",
        colour=discord.Color.teal(),
        url=entry.url,
    )
    embed.add_field(name="Link", value=entry.url, inline=False)

    timestamps = []
    last_updated = entry.updated_at or entry.created_at
    if last_updated:
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        epoch = int(last_updated.timestamp())
        actor = entry.updated_by or entry.created_by
        actor_display = f"<@{actor}>" if actor else "Unknown"
        timestamps.append(f"Updated by {actor_display} <t:{epoch}:R>")

    if timestamps:
        embed.add_field(name="Activity", value="\n".join(timestamps), inline=False)

    return embed


class LookupListView(discord.ui.View):
    def __init__(self, entries: List[LookupEntry], guild_name: str, *, per_page: int = 10):
        super().__init__(timeout=120)
        self.entries = entries
        self.guild_name = guild_name
        self.per_page = max(1, per_page)
        self.page = 0
        self._sync_button_states()

    def render_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.guild_name} Lookup Entries",
            colour=discord.Color.dark_teal(),
        )
        total = len(self.entries)
        embed.description = f"{total} entr{'y' if total == 1 else 'ies'}"

        start = self.page * self.per_page
        end = start + self.per_page
        slice_entries = self.entries[start:end]
        for entry in slice_entries:
            lines: List[str] = [entry.url]
            stamp = entry.updated_at or entry.created_at
            if stamp is not None:
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                epoch = int(stamp.timestamp())
                actor = entry.updated_by or entry.created_by
                actor_display = f"<@{actor}>" if actor else "Unknown"
                lines.append(f"Updated by {actor_display} <t:{epoch}:R>")
            if entry.description:
                lines.append(entry.description)
            embed.add_field(name=entry.name, value="\n".join(lines), inline=False)

        embed.set_footer(text=f"Page {self.page + 1} of {self._total_pages}")
        return embed

    @property
    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self.entries) / self.per_page))

    def _sync_button_states(self) -> None:
        total = self._total_pages
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "lookup:list:prev":
                child.disabled = self.page <= 0
            if child.custom_id == "lookup:list:next":
                child.disabled = self.page >= total - 1

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, custom_id="lookup:list:prev")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.page > 0:
            self.page -= 1
        self._sync_button_states()
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="lookup:list:next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.page < self._total_pages - 1:
            self.page += 1
        self._sync_button_states()
        await interaction.response.edit_message(embed=self.render_embed(), view=self)


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - extension entry point
    # Use override=True to replace any previously-registered /lookup command
    # This prevents CommandAlreadyRegistered when an older registration exists.
    await bot.add_cog(LookupCommandsCog(bot), override=True)
