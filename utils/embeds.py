from __future__ import annotations

import discord

from music.player import MusicPlayer
from music.track import format_duration
from utils.time import progress_bar


def player_embed(player: MusicPlayer, stopped: bool = False) -> discord.Embed:
    if stopped or player.current is None:
        return discord.Embed(
            title="🎵 Music player",
            description="Очередь пуста — добавьте трек через `/play`.",
            color=discord.Color.dark_grey(),
        )
    track = player.current
    embed = discord.Embed(
        title="▶ Сейчас играет",
        description=f"[{track.title}]({track.webpage_url})",
        color=discord.Color.blurple(),
    )
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    embed.add_field(name="Исполнитель", value=track.artist, inline=True)
    embed.add_field(name="Длительность", value=f"`{format_duration(track.duration)}`", inline=True)
    embed.add_field(name="Запросил", value=track.requester_name, inline=True)
    embed.add_field(
        name="Прогресс",
        value=(
            f"`{progress_bar(player.position, track.duration)}`\n"
            f"`{format_duration(player.position)} / {format_duration(track.duration)}`"
        ),
        inline=False,
    )
    embed.set_footer(
        text=(
            f"Громкость {round(player.volume * 100)}% • Loop: {player.loop_mode.value} • "
            f"Autoplay: {'on' if player.autoplay else 'off'} • В очереди: {len(player.queue)}"
        )
    )
    return embed
