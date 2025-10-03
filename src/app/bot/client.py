from __future__ import annotations

import importlib
import inspect
import logging
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence

import discord
from discord.ext import commands

from .config import DiscordBotConfig, build_default_intents
from .services.adventure_summary_ingestion import AdventureSummaryIngestionService
from .services.bot_settings import BotSettingsService
from .services.character_creation import CharacterCreationService
from .services.guild_logging import GuildLoggingService
from .services.quest_ingestion import QuestIngestionService
from .services.quest_lookup import QuestLookupService
from .services.role_management import RoleManagementService
from .services.user_provisioning import UserProvisioningService


@dataclass(frozen=True)
class CogSpec:
    key: str
    module: str
    class_name: str


@dataclass(slots=True)
class CogReloadResult:
    key: str
    status: str
    detail: str | None = None


class IngestionBot(commands.Bot):
    def __init__(
        self,
        config: DiscordBotConfig,
        quest_service: QuestIngestionService,
        summary_service: AdventureSummaryIngestionService,
        user_service: UserProvisioningService,
        role_service: RoleManagementService,
        character_service: CharacterCreationService,
        settings_service: BotSettingsService,
        logging_service: GuildLoggingService,
        lookup_service: QuestLookupService,
    ) -> None:
        intents = build_default_intents()
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
        )
        self._config = config
        self._quest_service = quest_service
        self._summary_service = summary_service
        self._user_service = user_service
        self._role_service = role_service
        self._character_service = character_service
        self._settings_service = settings_service
        self._logging_service = logging_service
        self._lookup_service = lookup_service
        self._synced_guilds: set[int] = set()
        self._log = logging.getLogger(__name__)
        specs: tuple[CogSpec, ...] = (
            CogSpec("general", "app.bot.cogs.general", "GeneralCog"),
            CogSpec("bot-setup", "app.bot.cogs.bot_setup", "BotSetupCog"),
            CogSpec(
                "user-provisioning",
                "app.bot.cogs.user_provisioning",
                "UserProvisioningCog",
            ),
            CogSpec(
                "character-commands",
                "app.bot.cogs.character_commands",
                "CharacterCommandsCog",
            ),
            CogSpec(
                "quest-ingestion",
                "app.bot.cogs.quest_ingestion",
                "QuestIngestionCog",
            ),
            CogSpec(
                "summary-ingestion",
                "app.bot.cogs.adventure_summary_ingestion",
                "AdventureSummaryIngestionCog",
            ),
            CogSpec(
                "role-management",
                "app.bot.cogs.role_management",
                "RoleManagementCog",
            ),
        )
        self._cog_specs = {spec.key: spec for spec in specs}
        self._cog_order = tuple(spec.key for spec in specs)

    async def setup_hook(self) -> None:
        """Register cogs and sync application commands."""
        self._logging_service.attach_bot(self)
        await self._load_all_cogs()
        # Ensure guild settings exist before syncing commands.
        # This is necessary because syncing application commands may rely on guild-specific configuration,
        # and missing settings could cause errors or incomplete command registration.
        if self._config.guild_id is not None:
            try:
                await self._settings_service.ensure_settings(self._config.guild_id)
            except Exception as exc:
                self._log.warning(
                    "Failed to ensure guild settings exist",
                    exc_info=exc,
                    extra={"guild_id": self._config.guild_id},
                )
        await self._sync_app_commands()

    async def on_ready(self) -> None:
        if self.user is not None:
            bot_id = self.user.id
            bot_name = self.user.name
            self._log.info(
                f"Quest ingestion bot ready ({bot_name})",
                extra={"bot_id": bot_id, "bot_name": bot_name},
            )
        else:
            self._log.warning("Bot ready event fired but bot user is None")
            await self.close()
            return

        for guild in self.guilds:
            if guild.id in self._synced_guilds:
                continue
            try:
                await self.tree.sync(guild=guild)
            except Exception as exc:  # pragma: no cover - defensive
                self._log.warning(
                    "Failed to sync application commands for guild",
                    exc_info=exc,
                    extra={"scope": "guild", "guild_id": guild.id},
                )
            else:
                self._synced_guilds.add(guild.id)

    async def _sync_app_commands(self) -> None:
        """Sync application commands against Discord."""
        try:
            if self._config.guild_id is not None:
                guild_commands = await self.tree.sync(
                    guild=discord.Object(id=self._config.guild_id)
                )
                self._log.info(
                    "Synced guild application commands",
                    extra={
                        "scope": "guild",
                        "guild_id": self._config.guild_id,
                        "commands": self._command_names(guild_commands),
                    },
                )
            else:
                global_commands = await self.tree.sync()
                self._log.info(
                    "Synced global application commands",
                    extra={
                        "scope": "global",
                        "commands": self._command_names(global_commands),
                    },
                )
        except Exception as exc:  # pragma: no cover
            self._log.warning("Failed to sync application commands", exc_info=exc)

    def _command_names(self, commands: Sequence[object]) -> list[str]:
        names: list[str] = []
        for command in commands:
            qualified = getattr(command, "qualified_name", None)
            if isinstance(qualified, str):
                names.append(qualified)
                continue
            name = getattr(command, "name", None)
            if isinstance(name, str):
                names.append(name)
            else:  # pragma: no cover - defensive
                names.append("<unknown>")
        return sorted(names)

    async def reload_cogs(
        self, targets: Sequence[str] | None = None
    ) -> list[CogReloadResult]:
        """Reload selected cogs in-place without restarting the bot."""
        normalized = self._normalize_targets(targets)
        results: list[CogReloadResult] = []
        changed = False
        for key in normalized:
            spec = self._cog_specs.get(key)
            if spec is None:
                results.append(
                    CogReloadResult(
                        key=key,
                        status="unknown",
                        detail="No cog registered with this name.",
                    )
                )
                continue
            try:
                await self._reload_single_cog(spec)
            except Exception as exc:  # pragma: no cover - defensive logging
                self._log.exception("Failed to reload cog", extra={"cog": key})
                detail = str(exc)
                if len(detail) > 300:
                    detail = detail[:297] + "…"
                results.append(CogReloadResult(key=key, status="error", detail=detail))
            else:
                changed = True
                results.append(CogReloadResult(key=key, status="ok", detail="Reloaded"))
        if changed:
            await self._sync_app_commands()
        return results

    def list_cogs(self) -> tuple[str, ...]:
        return self._cog_order

    def _normalize_targets(self, targets: Sequence[str] | None) -> Iterable[str]:
        if not targets:
            return self._cog_order
        expanded: list[str] = []
        for token in targets:
            token = token.strip()
            if not token:
                continue
            lowered = token.lower()
            if lowered in {"all", "*"}:
                expanded.extend(self._cog_order)
                continue
            expanded.append(lowered)
        if not expanded:
            return self._cog_order
        seen: set[str] = set()
        ordered: list[str] = []
        for key in expanded:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        return ordered

    async def _load_all_cogs(self) -> None:
        for key in self._cog_order:
            spec = self._cog_specs[key]
            await self._load_cog(spec)

    async def _reload_single_cog(self, spec: CogSpec) -> None:
        cog_name = spec.class_name
        existing = self.get_cog(cog_name)
        if existing is not None:
            removal = self.remove_cog(cog_name)
            if inspect.isawaitable(removal):  # pragma: no cover - defensive for stubs
                await removal
            self._log.debug("Removed cog before reload", extra={"cog": spec.key})
        module = self._import_cog_module(spec, reload_module=True)
        cog = self._construct_cog(spec, module)
        await self.add_cog(cog, override=True)

    async def _load_cog(self, spec: CogSpec) -> None:
        module = self._import_cog_module(spec, reload_module=False)
        cog = self._construct_cog(spec, module)
        await self.add_cog(cog)

    def _import_cog_module(self, spec: CogSpec, *, reload_module: bool) -> object:
        if reload_module and spec.module in sys.modules:
            return importlib.reload(sys.modules[spec.module])
        return importlib.import_module(spec.module)

    def _construct_cog(self, spec: CogSpec, module: object) -> commands.Cog:
        cog_cls = getattr(module, spec.class_name)
        kwargs = self._cog_kwargs(spec.key)
        return cog_cls(**kwargs)

    def _cog_kwargs(self, key: str) -> dict[str, object]:
        if key == "general":
            return {
                "bot": self,
                "logging_service": self._logging_service,
                "lookup_service": self._lookup_service,
            }
        if key == "bot-setup":
            return {
                "bot": self,
                "config": self._config,
                "settings_service": self._settings_service,
                "logging_service": self._logging_service,
            }
        if key == "user-provisioning":
            return {"service": self._user_service}
        if key == "character-commands":
            return {
                "service": self._character_service,
                "config": self._config,
            }
        if key == "quest-ingestion":
            return {"service": self._quest_service}
        if key == "summary-ingestion":
            return {"service": self._summary_service}
        if key == "role-management":
            return {
                "service": self._role_service,
                "config": self._config,
                "logging_service": self._logging_service,
            }
        raise ValueError(f"Unsupported cog key: {key}")


def build_bot(
    config: DiscordBotConfig,
    quest_service: QuestIngestionService,
    summary_service: AdventureSummaryIngestionService,
    user_service: UserProvisioningService,
    role_service: RoleManagementService,
    character_service: CharacterCreationService,
    settings_service: BotSettingsService,
    logging_service: GuildLoggingService,
    lookup_service: QuestLookupService,
) -> IngestionBot:
    return IngestionBot(
        config,
        quest_service,
        summary_service,
        user_service,
        role_service,
        character_service,
        settings_service,
        logging_service,
        lookup_service,
    )
