from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import discord

from app.domain.models.CharacterModel import Character, CharacterRole


def status_label(status: CharacterRole) -> str:
    return "Active" if status is CharacterRole.ACTIVE else "Retired"


def build_character_embed(
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
    colour = (
        discord.Color.blurple()
        if status is CharacterRole.ACTIVE
        else discord.Color.dark_grey()
    )
    embed = discord.Embed(
        title=name or "Unnamed Character",
        description=description or "No description provided.",
        colour=colour,
        timestamp=updated_at or datetime.now(timezone.utc),
    )
    embed.add_field(
        name="Sheet",
        value=ddb_link or "Not set",
        inline=False,
    )
    embed.add_field(
        name="Character Thread",
        value=character_thread_link or "Not set",
        inline=False,
    )
    embed.add_field(
        name="Token",
        value=token_link or "Not set",
        inline=False,
    )
    embed.add_field(
        name="Status",
        value=status_label(status),
        inline=False,
    )
    if tags:
        embed.add_field(
            name="Tags",
            value=", ".join(f"`{tag}`" for tag in tags),
            inline=False,
        )
    if art_link:
        embed.set_image(url=art_link)
    return embed


def build_character_embed_from_model(
    character: Character,
    *,
    updated_at: Optional[datetime] = None,
) -> discord.Embed:
    return build_character_embed(
        name=character.name,
        ddb_link=character.ddb_link,
        character_thread_link=character.character_thread_link,
        token_link=character.token_link,
        art_link=character.art_link,
        description=character.description,
        tags=character.tags or [],
        status=character.status,
        updated_at=updated_at or datetime.now(timezone.utc),
    )
