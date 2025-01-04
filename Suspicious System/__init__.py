from redbot.core import commands
from redbot.core.bot import Red
from .suspicious_user_monitor import SuspiciousUserMonitor

__red_end_user_data_statement__ = "This cog does not persistently store data or metadata about users."

async def setup(bot: Red):
    cog = SuspiciousUserMonitor(bot)
    await bot.add_cog(cog)
