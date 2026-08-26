from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from music.track import Track


class FavoriteGroup(app_commands.Group):
    def __init__(self, cog: LibraryCog):
        super().__init__(name="favorite", description="Управление избранными треками")
        self.cog = cog

    @app_commands.command(name="add", description="Добавить трек в избранное")
    async def add(
        self, interaction: discord.Interaction, query: app_commands.Range[str, 1, 500]
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        tracks = await self.cog.bot.extractor.search(
            query, interaction.guild_id or 0, interaction.user.id, interaction.user.display_name, 1
        )
        if not tracks:
            await interaction.followup.send("Ничего не найдено.", ephemeral=True)
            return
        track = tracks[0]
        added = await self.cog.bot.favorite_repo.add(
            interaction.user.id,
            {
                "source_url": track.webpage_url,
                "title": track.title,
                "artist": track.artist,
                "duration": track.duration,
                "thumbnail": track.thumbnail,
            },
        )
        await interaction.followup.send(
            "⭐ Добавлено." if added else "Этот трек уже в избранном.", ephemeral=True
        )

    @app_commands.command(name="remove", description="Удалить URL из избранного")
    async def remove(self, interaction: discord.Interaction, url: str) -> None:
        removed = await self.cog.bot.favorite_repo.remove(interaction.user.id, url)
        await interaction.response.send_message(
            "Удалено." if removed else "Трек не найден.", ephemeral=True
        )


class LibraryCog(commands.Cog):
    favorite = FavoriteGroup(None)  # replaced in __init__

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.favorite.cog = self

    @app_commands.command(name="favorites", description="Показать избранные треки")
    async def favorites(self, interaction: discord.Interaction) -> None:
        values = await self.bot.favorite_repo.list(interaction.user.id)
        description = (
            "\n".join(
                f"{index}. [{item.title}]({item.source_url}) — {item.artist}"
                for index, item in enumerate(values, 1)
            )
            or "Избранное пусто."
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="⭐ Избранное", description=description), ephemeral=True
        )

    @app_commands.command(name="history", description="История прослушивания на сервере")
    @app_commands.guild_only()
    async def history(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        values = await self.bot.history_repo.recent(interaction.guild.id, interaction.user.id)
        description = (
            "\n".join(
                f"{index}. [{item.title}]({item.source_url})"
                for index, item in enumerate(values, 1)
            )
            or "История пуста."
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="🕘 История", description=description), ephemeral=True
        )

    @app_commands.command(name="recent", description="Последние треки сервера")
    @app_commands.guild_only()
    async def recent(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        values = await self.bot.history_repo.recent(interaction.guild.id)
        description = (
            "\n".join(
                f"{index}. **{item.title}** — {item.artist}" for index, item in enumerate(values, 1)
            )
            or "История пуста."
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="🕘 Recent", description=description)
        )

    @app_commands.command(name="play_favorites", description="Добавить избранное в очередь")
    @app_commands.guild_only()
    async def play_favorites(self, interaction: discord.Interaction) -> None:
        if (
            interaction.guild is None
            or not isinstance(interaction.user, discord.Member)
            or interaction.user.voice is None
        ):
            await interaction.response.send_message(
                "Сначала зайдите в голосовой канал.", ephemeral=True
            )
            return
        await interaction.response.defer()
        values = await self.bot.favorite_repo.list(interaction.user.id)
        player = await self.bot.manager.get(interaction.guild)
        await player.connect(interaction.user.voice.channel)
        tracks = [
            Track(
                guild_id=interaction.guild.id,
                webpage_url=item.source_url,
                title=item.title,
                artist=item.artist,
                duration=item.duration,
                thumbnail=item.thumbnail,
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
                source="favorite",
            )
            for item in values
        ]
        await player.enqueue(tracks)
        player.text_channel = interaction.channel
        await player.start(interaction.channel)
        await interaction.followup.send(f"⭐ Добавлено избранных треков: {len(tracks)}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LibraryCog(bot))
