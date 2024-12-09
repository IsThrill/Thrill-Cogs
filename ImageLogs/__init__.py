from redbot.core import commands

from .imagedeletionlogger import ImageDeletionLogger

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."

async def setup(bot: commands.Bot):
    cog = ImageDeletionLogger(bot)
    await bot.add_cog(cog)
