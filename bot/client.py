from __future__ import annotations

import logging
import time

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import Settings
from database.repositories.guild import GuildSettingsRepository
from database.repositories.library import FavoriteRepository, HistoryRepository
from database.repositories.playlist import PlaylistRepository
from music.extractor import MediaExtractor
from music.manager import MusicManager
from services.cache import Cache
from services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


class MusicBot(commands.AutoShardedBot):
    def __init__(
        self,
        settings: Settings,
        settings_repo: GuildSettingsRepository,
        playlist_repo: PlaylistRepository,
        favorite_repo: FavoriteRepository,
        history_repo: HistoryRepository,
        cache: Cache,
    ):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.settings = settings
        self.settings_repo = settings_repo
        self.playlist_repo = playlist_repo
        self.favorite_repo = favorite_repo
        self.history_repo = history_repo
        self.cache = cache
        self.rate_limiter = RateLimiter()
        self.extractor = MediaExtractor(settings, cache)
        self.manager = MusicManager(settings, self.extractor, history_repo, cache)
        self.manager.attach_bot(self)
        self.started_at = time.monotonic()
        self._synced = False
        self._views_registered = False
        self._gateway_started = False

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        self._gateway_started = True
        await super().start(token, reconnect=reconnect)

    async def setup_hook(self) -> None:
        from bot.extensions import EXTENSIONS

        for extension in EXTENSIONS:
            await self.load_extension(extension)
        if self.settings.dev_guild_id:
            guild = discord.Object(id=self.settings.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands synced to development guild %s", guild.id)
        else:
            await self.tree.sync()
            logger.info("Global slash commands synced")
        self._synced = True

    async def on_ready(self) -> None:
        logger.info(
            "Logged in as %s; guilds=%d; discord.py=%s",
            self.user,
            len(self.guilds),
            discord.__version__,
        )
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="/play")
        )
        if not self._views_registered:
            from views.player import MusicControlView

            for guild in self.guilds:
                self.add_view(MusicControlView(self.manager, guild.id))
            self._views_registered = True

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        await self.manager.on_voice_state_update(member, before, after)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        logger.error(
            "Slash command failed command=%s guild=%s",
            interaction.command.name if interaction.command else "unknown",
            interaction.guild_id,
            exc_info=original,
        )
        message = "Произошла внутренняя ошибка. Попробуйте ещё раз."
        if isinstance(original, app_commands.CommandOnCooldown):
            message = f"Подождите {original.retry_after:.1f} сек."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def close(self) -> None:
        await self.manager.close()
        await self.cache.close()
        if self._gateway_started:
            await super().close()
