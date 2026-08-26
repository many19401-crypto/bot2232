from __future__ import annotations

import discord

from music.manager import MusicManager
from music.player import MusicPlayer
from utils.permissions import can, in_same_voice


class MusicControlView(discord.ui.View):
    """Persistent, guild-scoped controls. Every callback validates guild and voice context."""

    def __init__(self, manager: MusicManager, guild_id: int):
        super().__init__(timeout=None)
        self.manager = manager
        self.guild_id = guild_id
        controls = (
            ("⏮", "Previous", discord.ButtonStyle.secondary, "previous"),
            ("⏯", "Pause/Resume", discord.ButtonStyle.primary, "pause"),
            ("⏭", "Skip", discord.ButtonStyle.primary, "skip"),
            ("🔀", "Shuffle", discord.ButtonStyle.secondary, "shuffle"),
            ("🔁", "Loop", discord.ButtonStyle.secondary, "loop"),
            ("⏹", "Stop", discord.ButtonStyle.danger, "stop"),
            ("📜", "Queue", discord.ButtonStyle.secondary, "queue"),
            ("🔊", "Volume", discord.ButtonStyle.secondary, "volume"),
        )
        for emoji, label, style, action in controls:
            button = discord.ui.Button(
                emoji=emoji, label=label, style=style, custom_id=f"music:{guild_id}:{action}"
            )
            button.callback = self._callback(action)
            self.add_item(button)

    def _callback(self, action: str):
        async def callback(interaction: discord.Interaction) -> None:
            if (
                interaction.guild_id != self.guild_id
                or interaction.guild is None
                or not isinstance(interaction.user, discord.Member)
            ):
                await interaction.response.send_message(
                    "Эта панель принадлежит другому серверу.", ephemeral=True
                )
                return
            player = await self.manager.get(interaction.guild)
            if not in_same_voice(
                interaction.user, player.voice_client.channel if player.voice_client else None
            ):
                await interaction.response.send_message(
                    "Зайдите в тот же голосовой канал, что и бот.", ephemeral=True
                )
                return
            settings = await interaction.client.settings_repo.get(interaction.guild.id)  # type: ignore[attr-defined]
            if action in {"stop", "shuffle"} and not can(
                interaction.user,
                settings,
                "stop" if action == "stop" else "move",
                player.current.requester_id if player.current else None,
            ):
                await interaction.response.send_message(
                    "Недостаточно прав для этого действия.", ephemeral=True
                )
                return
            if action == "volume":
                if not can(interaction.user, settings, "volume"):
                    await interaction.response.send_message(
                        "Недостаточно прав для изменения громкости.", ephemeral=True
                    )
                    return
                await interaction.response.send_modal(VolumeModal(player, settings))
                return
            await interaction.response.defer()
            if action == "pause":
                if not await player.resume():
                    await player.pause()
            elif action == "skip":
                if not can(
                    interaction.user,
                    settings,
                    "skip",
                    player.current.requester_id if player.current else None,
                ):
                    await interaction.followup.send("Недостаточно прав для skip.", ephemeral=True)
                    return
                await player.skip()
            elif action == "stop":
                await player.stop(disconnect=False)
            elif action == "shuffle":
                await player.shuffle()
            elif action == "loop":
                await player.toggle_loop()
            elif action == "previous":
                if not await player.previous():
                    await interaction.followup.send("История текущей сессии пуста.", ephemeral=True)
                    return
            elif action == "queue":
                await interaction.followup.send(_queue_text(player), ephemeral=True)
                return
            await interaction.followup.send("Готово.", ephemeral=True)

        return callback


def _queue_text(player: MusicPlayer) -> str:
    page, pages = player.queue.page(1)
    if not page:
        return "Очередь пуста."
    return (
        "\n".join(
            f"{position}. {track.title} — `{track.duration_text}`" for position, track in page
        )
        + f"\nСтраница 1/{pages}"
    )


class VolumeModal(discord.ui.Modal, title="Громкость"):
    percent = discord.ui.TextInput(
        label="Процент от 0 до 100",
        placeholder="65",
        min_length=1,
        max_length=3,
        required=True,
    )

    def __init__(self, player: MusicPlayer, settings) -> None:
        super().__init__()
        self.player = player
        self.settings = settings

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            value = int(str(self.percent.value))
            if (
                value == 100
                and not self.settings.allow_volume_100
                and not interaction.user.guild_permissions.administrator
            ):
                raise ValueError("Громкость 100% запрещена настройками сервера")
            await self.player.set_volume(value)
        except (ValueError, TypeError) as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        await interaction.response.send_message(f"🔊 Громкость: **{value}%**", ephemeral=True)
