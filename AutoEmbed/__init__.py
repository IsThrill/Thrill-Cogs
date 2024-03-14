from redbot.core import commands

from .autoembeder import AutoEmbeder

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."

async def setup(bot: commands.Bot):
    cog = AutoEmbeder(bot)
    bot.add_cog(cog)
