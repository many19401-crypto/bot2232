from __future__ import annotations

import asyncio
import logging

import discord

from config.settings import Settings

logger = logging.getLogger(__name__)


class VoiceConnector:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def connect(
        self, channel: discord.VoiceChannel | discord.StageChannel
    ) -> discord.VoiceClient:
        delays = (2, 5, 10, 30)
        last_error: Exception | None = None
        for attempt in range(self.settings.voice_reconnect_attempts):
            try:
                client = channel.guild.voice_client
                if client and client.is_connected():
                    if client.channel != channel:
                        await client.move_to(channel)
                    return client
                if client:
                    await client.disconnect(force=True)
                logger.info(
                    "Connecting to voice channel guild=%s attempt=%s", channel.guild.id, attempt + 1
                )
                return await channel.connect(
                    timeout=self.settings.voice_connect_timeout, reconnect=True, self_deaf=True
                )
            except (TimeoutError, discord.ClientException, discord.ConnectionClosed) as exc:
                last_error = exc
                logger.warning("Voice connection failed guild=%s: %s", channel.guild.id, exc)
                if attempt + 1 < self.settings.voice_reconnect_attempts:
                    await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
        raise ConnectionError("Could not connect to the voice channel") from last_error

    async def disconnect(self, guild: discord.Guild) -> None:
        client = guild.voice_client
        if client:
            await client.disconnect(force=True)
