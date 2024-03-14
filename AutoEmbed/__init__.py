from redbot.core import commands

from .autoembed import AutoEmbed

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."

async def setup(bot: commands.Bot):
    cog = AutoEmbed(bot)
    await bot.add_cog(cog)
