import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging
    from .. import logembeds

class AutoModListeners(commands.Cog):
    """
    Handles all listeners related to Discord's built-in AutoMod.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None

    @commands.Cog.listener()
    async def on_automod_action(self, execution: discord.AutoModAction):
        """Logs when an AutoMod rule is triggered and an action is taken."""
        if not self.cog or not execution.guild:
            return

        embed = await logembeds.automod_action_triggered(execution)
        if embed:
            await self.cog._send_log(execution.guild, embed, "automod", "trigger")