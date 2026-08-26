from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from music.track import Track


class PlaylistCog(
    commands.GroupCog, group_name="playlist", group_description="Сохранённые плейлисты"
):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="create", description="Создать плейлист")
    @app_commands.describe(name="Название", visibility="private или public")
    async def create(
        self,
        interaction: discord.Interaction,
        name: app_commands.Range[str, 1, 100],
        visibility: str = "private",
    ) -> None:
        if not self.bot.rate_limiter.allow(
            interaction.user.id, "playlist", self.bot.settings.playlist_rate_limit
        ):
            await interaction.response.send_message(
                "Слишком много операций с плейлистами.", ephemeral=True
            )
            return
        try:
            playlist = await self.bot.playlist_repo.create(interaction.user.id, name, visibility)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Создан плейлист **{playlist.name}** (`{playlist.id}`)", ephemeral=True
        )

    @app_commands.command(name="list", description="Показать ваши плейлисты")
    async def list(self, interaction: discord.Interaction) -> None:
        playlists = await self.bot.playlist_repo.by_owner(interaction.user.id)
        description = (
            "\n".join(f"`{item.id}` · **{item.name}** ({item.visibility})" for item in playlists)
            or "Плейлистов нет."
        )
        await interaction.response.send_message(
            embed=discord.Embed(title="🎼 Мои плейлисты", description=description), ephemeral=True
        )

    @app_commands.command(name="add", description="Добавить URL в плейлист")
    @app_commands.describe(playlist_id="ID плейлиста", query="URL или название трека")
    async def add(
        self,
        interaction: discord.Interaction,
        playlist_id: str,
        query: app_commands.Range[str, 1, 500],
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        tracks = await self.bot.extractor.search(
            query, interaction.guild_id or 0, interaction.user.id, interaction.user.display_name, 1
        )
        if not tracks:
            await interaction.followup.send("Ничего не найдено.", ephemeral=True)
            return
        track = tracks[0]
        try:
            await self.bot.playlist_repo.add_track(
                playlist_id,
                interaction.user.id,
                {
                    "url": track.webpage_url,
                    "title": track.title,
                    "artist": track.artist,
                    "duration": track.duration,
                    "thumbnail": track.thumbnail,
                },
            )
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        await interaction.followup.send(f"✅ Добавлено: **{track.title}**", ephemeral=True)

    @app_commands.command(name="remove", description="Удалить позицию из плейлиста")
    @app_commands.describe(playlist_id="ID плейлиста", position="Позиция")
    async def remove(
        self,
        interaction: discord.Interaction,
        playlist_id: str,
        position: app_commands.Range[int, 1, 500],
    ) -> None:
        try:
            removed = await self.bot.playlist_repo.remove_track(
                playlist_id, interaction.user.id, position
            )
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_message(
            "✅ Удалено." if removed else "Позиция не найдена.", ephemeral=True
        )

    @app_commands.command(name="play", description="Воспроизвести плейлист")
    @app_commands.describe(playlist_id="ID плейлиста")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, playlist_id: str) -> None:
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
        playlist = await self.bot.playlist_repo.get(playlist_id, interaction.user.id)
        if playlist is None:
            await interaction.followup.send("Плейлист не найден или он приватный.", ephemeral=True)
            return
        player = await self.bot.manager.get(interaction.guild)
        await player.connect(interaction.user.voice.channel)
        tracks = [
            Track(
                guild_id=interaction.guild.id,
                webpage_url=item.url,
                title=item.title,
                artist=item.artist,
                duration=item.duration,
                thumbnail=item.thumbnail,
                requester_id=interaction.user.id,
                requester_name=interaction.user.display_name,
                source="playlist",
            )
            for item in playlist.tracks
        ]
        try:
            await player.enqueue(tracks)
            player.text_channel = interaction.channel
            await player.start(interaction.channel)
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        await interaction.followup.send(
            f"🎼 Добавлен плейлист **{playlist.name}**: {len(tracks)} треков"
        )

    @app_commands.command(name="delete", description="Удалить ваш плейлист")
    @app_commands.describe(playlist_id="ID плейлиста")
    async def delete(self, interaction: discord.Interaction, playlist_id: str) -> None:
        removed = await self.bot.playlist_repo.delete(playlist_id, interaction.user.id)
        await interaction.response.send_message(
            "🗑 Плейлист удалён." if removed else "Плейлист не найден.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PlaylistCog(bot))
