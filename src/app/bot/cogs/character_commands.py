from __future__ import annotations

import logging
from typing import Optional

import discord
from discord.ext import commands

from app.bot.config import DiscordBotConfig
from app.bot.services.character_creation import (
    CharacterCreatePayload,
    CharacterCreationResult,
    CharacterCreationService,
    PlayerRoleRequiredError,
)


class CharacterCommandsCog(commands.Cog):
    """Player-facing commands for managing characters."""

    def __init__(
        self,
        *,
        service: CharacterCreationService,
        config: DiscordBotConfig,
    ) -> None:
        """Store dependencies for creating characters through Discord commands."""
        self._service = service
        self._config = config
        self._log = logging.getLogger(__name__)

    @commands.hybrid_command(
        name="character-create", description="Create a new character for yourself."
    )
    @commands.guild_only()
    async def character_create(
        self,
        ctx: commands.Context[commands.Bot],
        name: str,
        ddb_link: str,
        character_thread_link: str,
        token_link: str,
        art_link: str,
        description: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> None:
        """Create a character for the invoking member and respond with an embed summarizing the result."""
        guild = ctx.guild
        if guild is None:
            await self._send_embed(
                ctx,
                self._error_embed(
                    "Guild only", "This command must be used inside a server."
                ),
            )
            return
        author = ctx.author
        if not isinstance(author, discord.Member):
            await self._send_embed(
                ctx,
                self._error_embed(
                    "Unsupported context", "Unable to resolve your guild member record."
                ),
            )
            return

        safe_links = {
            "ddb_link": ddb_link.strip(),
            "character_thread_link": character_thread_link.strip(),
            "token_link": token_link.strip(),
            "art_link": art_link.strip(),
        }
        payload = CharacterCreatePayload(
            name=name,
            ddb_link=safe_links["ddb_link"],
            character_thread_link=safe_links["character_thread_link"],
            token_link=safe_links["token_link"],
            art_link=safe_links["art_link"],
            description=self._clean_optional(description),
            notes=self._clean_optional(notes),
            tags=self._parse_tags(tags),
        )

        try:
            await self._maybe_defer(ctx)
            result = await self._service.create_for_member(author, payload)
        except PlayerRoleRequiredError:
            player_role_id = self._config.player_role_id
            role = (
                guild.get_role(player_role_id) if player_role_id is not None else None
            )
            role_hint = f" ({role.mention})" if role else ""
            embed = self._error_embed(
                "Player role required",
                f"You need the player role{role_hint} before you can create characters. Ask an admin to grant it.",
            )
            await self._send_embed(ctx, embed)
            return
        except ValueError as exc:
            embed = self._error_embed("Character creation failed", str(exc))
            await self._send_embed(ctx, embed)
            return
        except Exception as exc:  # pragma: no cover - defensive logging
            self._log.exception("Character creation command failed", exc_info=exc)
            embed = self._error_embed(
                "Unexpected error",
                "Something went wrong while creating the character. Please try again or contact an admin.",
            )
            await self._send_embed(ctx, embed)
            return

        embed = self._success_embed(result, author)
        await self._send_embed(ctx, embed)

    async def _maybe_defer(self, ctx: commands.Context[commands.Bot]) -> None:
        """Defer the interaction backing a command, preserving support for prefix usage."""
        interaction = getattr(ctx, "interaction", None)
        if interaction is None:
            return
        if interaction.response.is_done():
            return
        await ctx.defer()

    def _parse_tags(self, tags: Optional[str]) -> list[str]:
        """Split a comma-delimited tag string into a normalized list."""
        if not tags:
            return []
        parts = [part.strip() for part in tags.split(",")]
        return [part for part in parts if part]

    def _clean_optional(self, value: Optional[str]) -> Optional[str]:
        """Strip optional string inputs, returning None when only whitespace is provided."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    def _success_embed(
        self,
        result: CharacterCreationResult,
        member: discord.Member,
    ) -> discord.Embed:
        """Produce a success embed describing the newly created character."""
        character = result.character
        user = result.user

        embed = discord.Embed(
            title="Character created",
            description=f"{member.mention} created **{character.name}**.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Character ID", value=character.character_id, inline=False)

        resources = [
            f"• [D&D Beyond]({character.ddb_link})",
            f"• [Character Thread]({character.character_thread_link})",
            f"• [Token]({character.token_link})",
            f"• [Art]({character.art_link})",
        ]
        embed.add_field(name="Resources", value="\n".join(resources), inline=False)

        if character.description:
            embed.add_field(
                name="Description",
                value=character.description[:1024],
                inline=False,
            )
        if character.notes:
            embed.add_field(
                name="Notes",
                value=character.notes[:1024],
                inline=False,
            )
        if character.tags:
            embed.add_field(
                name="Tags",
                value=", ".join(character.tags)[:1024],
                inline=False,
            )
        if user.player and user.player.characters:
            embed.add_field(
                name="Total characters",
                value=str(len(user.player.characters)),
                inline=True,
            )
        embed.add_field(name="Owner", value=str(user.user_id), inline=True)
        embed.set_thumbnail(url=character.art_link)
        embed.set_footer(text=f"Requested by {member.display_name}")
        return embed

    def _error_embed(self, title: str, description: str) -> discord.Embed:
        """Return a red embed conveying character command errors."""
        return discord.Embed(
            title=title, description=description, color=discord.Color.red()
        )

    async def _send_embed(
        self, ctx: commands.Context[commands.Bot], embed: discord.Embed
    ) -> None:
        """Send an embed response while logging Discord delivery failures."""
        try:
            await ctx.send(embed=embed)
        except discord.HTTPException as exc:  # pragma: no cover - defensive
            self._log.error("Failed to send embed", exc_info=exc)
