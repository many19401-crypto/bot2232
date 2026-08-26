from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import can, in_same_voice
from views.queue import QueuePagination


class QueueCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _player_and_settings(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            raise ValueError("Команда доступна только на сервере.")
        player = await self.bot.manager.get(interaction.guild)
        settings = await self.bot.settings_repo.get(interaction.guild.id)
        if player.voice_client and not in_same_voice(interaction.user, player.voice_client.channel):
            raise ValueError("Зайдите в голосовой канал бота.")
        return player, settings

    @app_commands.command(name="queue", description="Показать очередь с пагинацией")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction) -> None:
        try:
            player, _ = await self._player_and_settings(interaction)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        view = QueuePagination(player, interaction.user.id)
        await interaction.response.send_message(embed=view.embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="remove", description="Удалить трек из очереди")
    @app_commands.describe(position="Позиция трека в очереди")
    @app_commands.guild_only()
    async def remove(
        self, interaction: discord.Interaction, position: app_commands.Range[int, 1, 10000]
    ) -> None:
        try:
            player, settings = await self._player_and_settings(interaction)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        requester = None
        values, _ = player.queue.page((position - 1) // 10 + 1, 10)
        for item_position, track in values:
            if item_position == position:
                requester = track.requester_id
                break
        if not can(interaction.user, settings, "move", requester):
            await interaction.response.send_message(
                "Только DJ или requester может менять очередь.", ephemeral=True
            )
            return
        try:
            track = await player.remove(position)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_message(f"🗑 Удалён: **{track.title}**")

    @app_commands.command(name="move", description="Переместить трек в очереди")
    @app_commands.describe(from_position="Текущая позиция", to_position="Новая позиция")
    @app_commands.guild_only()
    async def move(
        self,
        interaction: discord.Interaction,
        from_position: app_commands.Range[int, 1, 10000],
        to_position: app_commands.Range[int, 1, 10000],
    ) -> None:
        try:
            player, settings = await self._player_and_settings(interaction)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        if not can(interaction.user, settings, "move"):
            await interaction.response.send_message(
                "Только DJ может перемещать треки.", ephemeral=True
            )
            return
        try:
            async with player._lock:
                player.queue.move(from_position, to_position)
                await player._update_panel()
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_message("↕️ Очередь обновлена.")

    @app_commands.command(name="clear", description="Очистить очередь")
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction) -> None:
        try:
            player, settings = await self._player_and_settings(interaction)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        if not can(interaction.user, settings, "clear"):
            await interaction.response.send_message(
                "Только DJ может очищать очередь.", ephemeral=True
            )
            return
        count = await player.clear_queue()
        await interaction.response.send_message(f"🧹 Удалено треков: **{count}**")

    @app_commands.command(name="shuffle", description="Перемешать очередь")
    @app_commands.guild_only()
    async def shuffle(self, interaction: discord.Interaction) -> None:
        try:
            player, settings = await self._player_and_settings(interaction)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        if not can(interaction.user, settings, "move"):
            await interaction.response.send_message(
                "Только DJ может перемешивать очередь.", ephemeral=True
            )
            return
        await player.shuffle()
        await interaction.response.send_message("🔀 Очередь перемешана.")

    @app_commands.command(name="playnext", description="Добавить ссылку в начало очереди")
    @app_commands.describe(query="URL или название трека")
    @app_commands.guild_only()
    async def playnext(
        self, interaction: discord.Interaction, query: app_commands.Range[str, 1, 500]
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        player, settings = await self._player_and_settings(interaction)
        if not can(interaction.user, settings, "move"):
            await interaction.response.send_message(
                "Только DJ может добавлять priority tracks.", ephemeral=True
            )
            return
        await interaction.response.defer()
        tracks = await self.bot.extractor.search(
            query, interaction.guild.id, interaction.user.id, interaction.user.display_name, 1
        )
        if not tracks:
            await interaction.followup.send("Ничего не найдено.", ephemeral=True)
            return
        try:
            await player.enqueue([tracks[0]], priority=True)
            player.text_channel = interaction.channel
            await player.start(interaction.channel)
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        await interaction.followup.send(f"⏭️ Следующим будет: **{tracks[0].title}**")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QueueCog(bot))
