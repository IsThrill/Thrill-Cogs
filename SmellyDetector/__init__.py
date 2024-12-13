from redbot.core import commands

from .smelly import Smelly

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."


async def setup(bot: commands.Bot):
    smelly_cog = Smelly(bot)
    await bot.add_cog(smelly_cog)
