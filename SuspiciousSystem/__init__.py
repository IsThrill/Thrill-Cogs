from redbot.core.bot import Red
from .suspicioususermonitor import SuspiciousUserMonitor

__red_end_user_data_statement__ = (
    "This cog stores the following user data per guild:\n"
    "- User IDs and timestamps for pending verifications\n"
    "- User IDs in the whitelist (bypasses account-age check)\n"
    "- User IDs and strike counts for DM-failure tracking\n\n"
    "Data is automatically cleaned up when:\n"
    "- A user completes or abandons their verification\n"
    "- A user is approved, denied, kicked, or banned\n"
    "- A server administrator calls `sus resetfails` or `sus unwhitelist`\n\n"
    "Server owners and bot owners can request full user data deletion "
    "via Red's standard `[p]mydata` flow, which invokes "
    "`red_delete_data_for_user` on this cog."
)


async def setup(bot: Red) -> None:
    cog = SuspiciousUserMonitor(bot)
    await bot.add_cog(cog)
