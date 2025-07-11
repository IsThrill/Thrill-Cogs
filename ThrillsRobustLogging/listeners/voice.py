import discord
from redbot.core import commands

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

class VoiceListeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # This cog instance is passed in from core.py
        self.cog: "ThrillsRobustLogging" = None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Listener for voice channel joins, leaves, and moves."""
        if member.bot or not self.cog: return
        
        # Joined a voice channel
        if not before.channel and after.channel:
            # embed = await logembeds.voice_joined(member, after.channel)
            await self.cog._send_log(member.guild, embed, "voice", "join")
            pass
        # Left a voice channel
        elif before.channel and not after.channel:
            # embed = await logembeds.voice_left(member, before.channel)
            await self.cog._send_log(member.guild, embed, "voice", "leave")
            pass
        # Moved between voice channels
        elif before.channel and after.channel and before.channel != after.channel:
            # embed = await logembeds.voice_moved(member, before.channel, after.channel)
            await self.cog._send_log(member.guild, embed, "voice", "move")
            pass