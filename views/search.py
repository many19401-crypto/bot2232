from __future__ import annotations

import discord

from music.manager import MusicManager
from music.track import Track


class SearchSelect(discord.ui.Select):
    def __init__(
        self,
        tracks: list[Track],
        owner_id: int,
        manager: MusicManager,
        source_channel: discord.abc.Messageable,
    ):
        options = [
            discord.SelectOption(
                label=track.title[:100],
                description=f"{track.artist} • {track.duration_text}"[:100],
                value=str(index),
            )
            for index, track in enumerate(tracks)
        ]
        super().__init__(placeholder="Выберите трек…", min_values=1, max_values=1, options=options)
        self.tracks = tracks
        self.owner_id = owner_id
        self.manager = manager
        self.source_channel = source_channel

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id or interaction.guild is None:
            await interaction.response.send_message(
                "Этот поиск принадлежит другому пользователю.", ephemeral=True
            )
            return
        await interaction.response.defer()
        track = self.tracks[int(self.values[0])]
        player = await self.manager.get(interaction.guild)
        if not isinstance(interaction.user, discord.Member) or interaction.user.voice is None:
            await interaction.followup.send("Сначала зайдите в голосовой канал.", ephemeral=True)
            return
        settings = await interaction.client.settings_repo.get(interaction.guild.id)  # type: ignore[attr-defined]
        player.queue.max_size = settings.max_queue_size
        player.autoplay = settings.autoplay
        player.auto_disconnect_timeout = settings.auto_disconnect_timeout
        try:
            await player.connect(interaction.user.voice.channel)
            position = await player.add_track(track)
        except (ValueError, ConnectionError, discord.ClientException) as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        await player.start(self.source_channel)
        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Добавлено в очередь",
                description=f"[{track.title}]({track.webpage_url})\nПозиция: **{position}**",
                color=discord.Color.green(),
            )
        )
        if isinstance(self.view, SearchView):
            self.view.stop()


class SearchView(discord.ui.View):
    def __init__(
        self,
        tracks: list[Track],
        owner_id: int,
        manager: MusicManager,
        source_channel: discord.abc.Messageable,
    ):
        super().__init__(timeout=60)
        self.add_item(SearchSelect(tracks, owner_id, manager, source_channel))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
