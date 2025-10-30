from __future__ import annotations

from typing import Iterable, Optional

import discord
from discord.ext import commands

from app.bot.services import guild_settings_store


def _member_has_admin_perms(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return perms.manage_guild or perms.manage_messages or perms.administrator


def _normalize_role_ids(raw_ids: Optional[Iterable[object]]) -> set[int]:
    role_ids: set[int] = set()
    if not raw_ids:
        return role_ids
    for raw in raw_ids:
        try:
            role_ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    return role_ids


def is_allowed_staff(bot: commands.Bot, member: discord.Member) -> bool:
    """Return True if the member should be treated as Nonagon staff.

    A member is considered staff if they have standard moderation permissions
    or if they possess any of the roles saved in the setup settings (legacy `/guild setup`).
    """
    if not isinstance(member, discord.Member):
        return False

    if _member_has_admin_perms(member):
        return True

    settings = guild_settings_store.fetch_settings(member.guild.id) or {}
    allowed_roles = _normalize_role_ids(settings.get("allowed_role_ids"))
    if not allowed_roles:
        return False

    for role in member.roles:
        if role.id in allowed_roles:
            return True

    return False
