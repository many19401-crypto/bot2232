from __future__ import annotations

import discord

from music.player import MusicPlayer


class QueuePagination(discord.ui.View):
    def __init__(self, player: MusicPlayer, owner_id: int, per_page: int = 10):
        super().__init__(timeout=120)
        self.player = player
        self.owner_id = owner_id
        self.per_page = per_page
        self.page = 1
        self.message: discord.Message | None = None

    def embed(self) -> discord.Embed:
        items, pages = self.player.queue.page(self.page, self.per_page)
        self.page = min(self.page, pages)
        description = (
            "\n".join(
                f"**{position}.** {track.title} — `{track.duration_text}` · {track.requester_name}"
                for position, track in items
            )
            or "Очередь пуста."
        )
        return discord.Embed(
            title="📜 Очередь", description=description, color=discord.Color.blurple()
        ).set_footer(text=f"Страница {self.page}/{pages} • Всего: {len(self.player.queue)}")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Эта пагинация принадлежит другому пользователю.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = 1
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = max(1, self.page - 1)
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page += 1
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = max(1, (len(self.player.queue) + self.per_page - 1) // self.per_page)
        await interaction.response.edit_message(embed=self.embed(), view=self)
