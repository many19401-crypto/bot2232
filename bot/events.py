from __future__ import annotations

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


class ErrorEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErrorEvents(bot))
