from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from music.extractor import ExtractorError
from music.track import Track, format_duration
from utils.embeds import player_embed
from utils.permissions import can, in_same_voice
from utils.time import parse_timestamp
from views.search import SearchView

logger = logging.getLogger(__name__)


async def voice_player(interaction: discord.Interaction):
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        raise ValueError("Эта команда доступна только на сервере.")
    if interaction.user.voice is None or interaction.user.voice.channel is None:
        raise ValueError("Сначала зайдите в голосовой канал.")
    player = await interaction.client.manager.get(interaction.guild)  # type: ignore[attr-defined]
    settings = await interaction.client.settings_repo.get(interaction.guild.id)  # type: ignore[attr-defined]
    player.queue.max_size = settings.max_queue_size
    player.volume = settings.default_volume / 100 if player.current is None else player.volume
    player.autoplay = settings.autoplay
    player.auto_disconnect_timeout = settings.auto_disconnect_timeout
    await player.connect(interaction.user.voice.channel)
    return player, settings


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _search(self, interaction: discord.Interaction, query: str, connect: bool) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Команда доступна только на сервере.", ephemeral=True
            )
            return
        if query.strip().lower() == "favorites" and connect:
            await self._play_favorites(interaction)
            return
        if not self.bot.rate_limiter.allow(
            interaction.user.id, "search", self.bot.settings.search_rate_limit
        ):
            await interaction.response.send_message(
                "Слишком много запросов. Попробуйте через минуту.", ephemeral=True
            )
            return
        await interaction.response.defer()
        try:
            tracks = await self.bot.extractor.search(
                query,
                interaction.guild.id,
                interaction.user.id,
                interaction.user.display_name,
                10 if self.bot.extractor.is_url(query) else 5,
            )
        except Exception as exc:
            await interaction.followup.send(f"❌ Поиск не удался: {exc}", ephemeral=True)
            return
        if not tracks:
            await interaction.followup.send("Ничего не найдено.", ephemeral=True)
            return
        if connect:
            try:
                player, _ = await voice_player(interaction)
            except (ValueError, discord.ClientException, ConnectionError) as exc:
                await interaction.followup.send(f"❌ {exc}", ephemeral=True)
                return
        else:
            player = await self.bot.manager.get(interaction.guild)
        if self.bot.extractor.is_url(query) and connect:
            if not self.bot.rate_limiter.allow(
                interaction.user.id, "play", self.bot.settings.play_rate_limit
            ):
                await interaction.followup.send(
                    "Слишком много команд воспроизведения. Попробуйте позже.", ephemeral=True
                )
                return
            try:
                await player.enqueue(tracks)
                player.text_channel = interaction.channel
                await player.start(interaction.channel)
            except ValueError as exc:
                await interaction.followup.send(f"❌ {exc}", ephemeral=True)
                return
            description = (
                f"Добавлено треков: **{len(tracks)}**"
                if len(tracks) > 1
                else f"[{tracks[0].title}]({tracks[0].webpage_url})"
            )
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Добавлено в очередь",
                    description=description,
                    color=discord.Color.green(),
                )
            )
            return
        embed = discord.Embed(
            title="🔎 Результаты поиска",
            description="Выберите трек в меню ниже.",
            color=discord.Color.blurple(),
        )
        for index, track in enumerate(tracks, 1):
            embed.add_field(
                name=f"{index}. {track.title}",
                value=f"{track.artist} · `{format_duration(track.duration)}`",
                inline=False,
            )
        await interaction.followup.send(
            embed=embed,
            view=SearchView(tracks, interaction.user.id, self.bot.manager, interaction.channel),
        )

    @app_commands.command(
        name="play", description="Найти и воспроизвести музыку или добавить ссылку/плейлист"
    )
    @app_commands.describe(query="Название, исполнитель, URL или URL плейлиста")
    @app_commands.guild_only()
    async def play(
        self, interaction: discord.Interaction, query: app_commands.Range[str, 1, 500]
    ) -> None:
        await self._search(interaction, query, True)

    @app_commands.command(name="search", description="Показать интерактивные результаты поиска")
    @app_commands.describe(query="Название песни или исполнитель")
    @app_commands.guild_only()
    async def search(
        self, interaction: discord.Interaction, query: app_commands.Range[str, 1, 200]
    ) -> None:
        await self._search(interaction, query, False)

    @app_commands.command(name="join", description="Подключить бота к вашему голосовому каналу")
    @app_commands.guild_only()
    async def join(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            player, _ = await voice_player(interaction)
            player.text_channel = interaction.channel
            await interaction.followup.send(
                f"✅ Подключён к **{player.voice_client.channel.name}**", ephemeral=True
            )
        except (ValueError, discord.ClientException, ConnectionError) as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)

    @app_commands.command(name="leave", description="Остановить музыку и отключить бота")
    @app_commands.guild_only()
    async def leave(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        player = await self.bot.manager.get(interaction.guild)
        settings = await self.bot.settings_repo.get(interaction.guild.id)
        if not can(interaction.user, settings, "disconnect"):
            await interaction.response.send_message(
                "Только DJ может отключить бота.", ephemeral=True
            )
            return
        await interaction.response.defer()
        await player.leave()
        await interaction.followup.send("👋 Отключён.")

    @app_commands.command(name="pause", description="Поставить текущий трек на паузу")
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction) -> None:
        await self._control(interaction, lambda player, _: player.pause(), "⏸ Пауза")

    @app_commands.command(name="resume", description="Продолжить воспроизведение")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction) -> None:
        await self._control(interaction, lambda player, _: player.resume(), "▶ Продолжено")

    @app_commands.command(name="skip", description="Пропустить текущий трек")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction) -> None:
        await self._control(
            interaction,
            lambda player, settings: self._permission_control(
                player, settings, interaction, "skip"
            ),
            "⏭ Пропущено",
        )

    @app_commands.command(name="stop", description="Остановить проигрывание и очистить очередь")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction) -> None:
        await self._control(
            interaction,
            lambda player, settings: self._permission_control(
                player, settings, interaction, "stop"
            ),
            "⏹ Остановлено",
        )

    @app_commands.command(name="loop", description="Переключить повтор трека/очереди")
    @app_commands.guild_only()
    async def loop(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        player = await self.bot.manager.get(interaction.guild)
        mode = await player.toggle_loop()
        await interaction.response.send_message(f"🔁 Loop: **{mode.value}**")

    @app_commands.command(name="nowplaying", description="Показать текущий трек")
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            return
        player = await self.bot.manager.get(interaction.guild)
        await interaction.response.send_message(embed=player_embed(player))

    @app_commands.command(name="volume", description="Установить громкость от 0 до 100")
    @app_commands.describe(percent="Громкость, 0–100")
    @app_commands.guild_only()
    async def volume(
        self, interaction: discord.Interaction, percent: app_commands.Range[int, 0, 100]
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        settings = await self.bot.settings_repo.get(interaction.guild.id)
        if not can(interaction.user, settings, "volume"):
            await interaction.response.send_message(
                "Недостаточно прав для изменения громкости.", ephemeral=True
            )
            return
        if (
            percent == 100
            and not settings.allow_volume_100
            and not interaction.user.guild_permissions.administrator
        ):
            await interaction.response.send_message(
                "Громкость 100% запрещена настройками сервера.", ephemeral=True
            )
            return
        player = await self.bot.manager.get(interaction.guild)
        await player.set_volume(percent)
        await interaction.response.send_message(f"🔊 Громкость: **{percent}%**")

    @app_commands.command(name="seek", description="Перейти к позиции: секунды, M:SS или H:MM:SS")
    @app_commands.describe(position="Например 90 или 1:32")
    @app_commands.guild_only()
    async def seek(
        self, interaction: discord.Interaction, position: app_commands.Range[str, 1, 20]
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer()
        try:
            seconds = parse_timestamp(position)
            player, _ = await voice_player(interaction)
            if await player.seek(seconds):
                await interaction.followup.send(f"⏩ Позиция: `{format_duration(seconds)}`")
            else:
                await interaction.followup.send("Сейчас ничего не играет.", ephemeral=True)
        except (ValueError, ExtractorError, ConnectionError) as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)

    async def _play_favorites(self, interaction: discord.Interaction) -> None:
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
        if not values:
            await interaction.followup.send("Избранное пусто.", ephemeral=True)
            return
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
        try:
            await player.enqueue(tracks)
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        player.text_channel = interaction.channel
        await player.start(interaction.channel)
        await interaction.followup.send(f"⭐ Добавлено избранных треков: {len(tracks)}")

    async def _permission_control(self, player, settings, interaction, action: str) -> bool:
        if not can(
            interaction.user,
            settings,
            action,
            player.current.requester_id if player.current else None,
        ):
            return False
        return await player.skip() if action == "skip" else (await player.stop() or True)

    async def _control(self, interaction: discord.Interaction, action, message: str) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        player = await self.bot.manager.get(interaction.guild)
        if not in_same_voice(
            interaction.user, player.voice_client.channel if player.voice_client else None
        ):
            await interaction.response.send_message(
                "Зайдите в тот же голосовой канал, что и бот.", ephemeral=True
            )
            return
        settings = await self.bot.settings_repo.get(interaction.guild.id)
        await interaction.response.defer()
        result = await action(player, settings)
        if result:
            await interaction.followup.send(message)
        else:
            await interaction.followup.send(
                "Недостаточно прав или плеер не активен.", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))
