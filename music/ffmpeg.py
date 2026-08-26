from __future__ import annotations

import discord

from config.settings import Settings

from .track import Track


class FFmpegFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create(
        self, track: Track, stream_url: str, volume: float, start_seconds: float = 0
    ) -> discord.AudioSource:
        before = "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        if start_seconds > 0:
            before = f"-ss {max(0.0, start_seconds):.3f} " + before
        source = discord.FFmpegPCMAudio(
            stream_url,
            executable=self.settings.ffmpeg_bin,
            before_options=before,
            options="-vn -loglevel warning -bufsize 64k",
        )
        return discord.PCMVolumeTransformer(source, volume=max(0.0, min(1.0, volume)))
