from __future__ import annotations

import os
import time

import discord
import psutil
from discord import app_commands
from discord.ext import commands


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="settings", description="Настроить DJ и поведение музыкальной сессии"
    )
    @app_commands.describe(
        dj_role="DJ role",
        autoplay="Включить autoplay",
        max_queue="Лимит очереди",
        auto_disconnect="Таймаут отключения в секундах",
        allow_volume_100="Разрешить громкость 100%",
    )
    @app_commands.guild_only()
    async def settings(
        self,
        interaction: discord.Interaction,
        dj_role: discord.Role | None = None,
        autoplay: bool | None = None,
        max_queue: app_commands.Range[int, 1, 500] | None = None,
        auto_disconnect: app_commands.Range[int, 60, 3600] | None = None,
        allow_volume_100: bool | None = None,
    ) -> None:
        if (
            interaction.guild is None
            or not isinstance(interaction.user, discord.Member)
            or not interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message("Нужно право Manage Server.", ephemeral=True)
            return
        values = {}
        if dj_role is not None:
            values["dj_role_id"] = dj_role.id
        if autoplay is not None:
            values["autoplay"] = autoplay
        if max_queue is not None:
            values["max_queue_size"] = max_queue
        if auto_disconnect is not None:
            values["auto_disconnect_timeout"] = auto_disconnect
        if allow_volume_100 is not None:
            values["allow_volume_100"] = allow_volume_100
        updated = (
            await self.bot.settings_repo.update(interaction.guild.id, **values)
            if values
            else await self.bot.settings_repo.get(interaction.guild.id)
        )
        player = await self.bot.manager.get(interaction.guild)
        player.queue.max_size = updated.max_queue_size
        player.autoplay = updated.autoplay
        player.auto_disconnect_timeout = updated.auto_disconnect_timeout
        summary = (
            f"✅ Настройки сохранены. DJ: `{updated.dj_role_id or 'not set'}`, "
            f"autoplay: `{updated.autoplay}`, queue: `{updated.max_queue_size}`"
        )
        await interaction.response.send_message(summary, ephemeral=True)

    @app_commands.command(name="status", description="Состояние бота и музыкальных сессий")
    async def status(self, interaction: discord.Interaction) -> None:
        process = psutil.Process(os.getpid())
        active = [
            player for player in self.bot.manager.players.values() if player.current is not None
        ]
        voice = [
            player
            for player in self.bot.manager.players.values()
            if player.voice_client and player.voice_client.is_connected()
        ]
        embed = discord.Embed(title="📊 Bot status", color=discord.Color.green())
        embed.add_field(name="Uptime", value=f"{int(time.monotonic() - self.bot.started_at)} sec")
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)))
        embed.add_field(name="Players / voice", value=f"{len(active)} / {len(voice)}")
        embed.add_field(
            name="Queued tracks",
            value=str(sum(len(player.queue) for player in self.bot.manager.players.values())),
        )
        errors = sum(1 for player in self.bot.manager.players.values() if player._last_error)
        ffmpeg = sum(
            1
            for player in self.bot.manager.players.values()
            if player.voice_client
            and player.voice_client.source
            and getattr(getattr(player.voice_client.source, "original", None), "_process", None)
        )
        embed.add_field(name="Errors / FFmpeg", value=f"{errors} / {ffmpeg}")
        embed.add_field(
            name="CPU / RAM",
            value=(
                f"{process.cpu_percent():.1f}% / {process.memory_info().rss / 1024 / 1024:.1f} MiB"
            ),
        )
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.0f} ms")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
