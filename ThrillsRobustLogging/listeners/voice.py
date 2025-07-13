import discord
from redbot.core import commands
from typing import TYPE_CHECKING

# This ensures type hints work for your main cog without circular imports
if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging
    from .. import logembeds

class VoiceListeners(commands.Cog):
    """
    Handles all voice state update events for professional logging.
    """
    def __init__(self, bot):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        Listener for all voice channel activities.
        """
        # Ignore bots to prevent log spam
        if member.bot or not self.cog:
            return

        guild = member.guild
        embed = None  # Initialize embed as None

        # Case 1: Member joins a voice channel
        if not before.channel and after.channel:
            embed = await logembeds.voice_joined(member, after.channel)
            await self.cog._send_log(guild, embed, "voice", "join")

        # Case 2: Member leaves a voice channel
        elif before.channel and not after.channel:
            embed = await logembeds.voice_left(member, before.channel)
            await self.cog._send_log(guild, embed, "voice", "leave")

        # Case 3: Member moves between voice channels
        elif before.channel and after.channel and before.channel != after.channel:
            embed = await logembeds.voice_moved(member, before.channel, after.channel)
            await self.cog._send_log(guild, embed, "voice", "move")

        # Case 4: Member is server-muted or unmuted
        elif before.mute != after.mute:
            embed = await logembeds.voice_server_muted(member, after.channel, after.mute)
            await self.cog._send_log(guild, embed, "voice", "mute")
            
        # Case 5: Member is server-deafened or undeafened
        elif before.deaf != after.deaf:
            embed = await logembeds.voice_server_deafened(member, after.channel, after.deaf)
            await self.cog._send_log(guild, embed, "voice", "deafen")