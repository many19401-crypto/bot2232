from __future__ import annotations

import asyncio
import logging

import discord

from config.settings import Settings
from database.repositories.library import HistoryRepository
from services.cache import Cache

from .extractor import MediaExtractor
from .ffmpeg import FFmpegFactory
from .player import MusicPlayer
from .voice import VoiceConnector

logger = logging.getLogger(__name__)


class MusicManager:
    def __init__(
        self,
        settings: Settings,
        extractor: MediaExtractor,
        history: HistoryRepository | None = None,
        cache: Cache | None = None,
    ):
        self.settings = settings
        self.extractor = extractor
        self.history = history
        self.cache = cache
        self.voice = VoiceConnector(settings)
        self.ffmpeg = FFmpegFactory(settings)
        self.players: dict[int, MusicPlayer] = {}
        self._lock = asyncio.Lock()
        self._bot: discord.Client | None = None

    def attach_bot(self, bot: discord.Client) -> None:
        self._bot = bot

    async def get(self, guild: discord.Guild) -> MusicPlayer:
        async with self._lock:
            player = self.players.get(guild.id)
            if player is None:
                player = MusicPlayer(
                    guild,
                    self.settings,
                    self.extractor,
                    self.voice,
                    self.ffmpeg,
                    self.history,
                    self.update_panel,
                    self.cache,
                )
                self.players[guild.id] = player
            return player

    async def remove(self, guild_id: int) -> None:
        async with self._lock:
            player = self.players.pop(guild_id, None)
        if player:
            await player.close()

    async def update_panel(self, player: MusicPlayer, stopped: bool = False) -> None:
        from views.player import MusicControlView, player_embed

        if player.text_channel is None:
            return
        embed = player_embed(player, stopped=stopped)
        view = None if stopped else MusicControlView(self, player.guild.id)
        try:
            if player.panel_message is not None:
                await player.panel_message.edit(embed=embed, view=view)
            else:
                player.panel_message = await player.text_channel.send(embed=embed, view=view)
        except discord.NotFound:
            player.panel_message = await player.text_channel.send(embed=embed, view=view)

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        player = self.players.get(member.guild.id)
        if player is None or self._bot is None or member.id != self._bot.user.id:  # type: ignore[union-attr]
            return
        await player.handle_voice_state(before.channel, after.channel)

    async def close(self) -> None:
        players = list(self.players.values())
        self.players.clear()
        await asyncio.gather(*(player.close() for player in players), return_exceptions=True)
