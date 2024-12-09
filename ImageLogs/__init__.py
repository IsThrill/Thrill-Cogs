from redbot.core import commands

from redbot.core.bot import Red

from .imagelogs import ImageLogs

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."

async def setup(bot: Red):
    cog = ImageLogs(bot)
    await bot.add_cog(cog)
