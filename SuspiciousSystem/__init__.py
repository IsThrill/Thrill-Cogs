from redbot.core import commands
from redbot.core.bot import Red
from .suspicioususermonitor import SuspiciousUserMonitor

__red_end_user_data_statement__ = (
    "This cog stores the following user data:\n"
    "- User IDs and timestamps for pending questionnaires\n"
    "- Saved role IDs when users are marked suspicious\n"
    "- Optional ticket channel IDs for questionnaire delivery\n\n"
    "Data is automatically cleaned up when:\n"
    "- Users complete questionnaires\n"
    "- Users are verified as safe by staff\n"
    "- Users are kicked/banned from the server\n"
    "- The 24-hour questionnaire timeout expires\n\n"
    "Server administrators can clear all data by unloading the cog."
)

async def setup(bot: Red):
    cog = SuspiciousUserMonitor(bot)
    await bot.add_cog(cog)
