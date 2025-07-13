import discord
from redbot.core import commands
from typing import TYPE_CHECKING
from .. import logembeds

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

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
        if member.bot or not self.cog:
            return

        guild = member.guild
        embed = None

        # Member joins a voice channel
        if not before.channel and after.channel:
            embed = await logembeds.voice_joined(member, after.channel)
            await self.cog._send_log(guild, embed, "voice", "join")

        # Member leaves a voice channel
        elif before.channel and not after.channel:
            embed = await logembeds.voice_left(member, before.channel)
            await self.cog._send_log(guild, embed, "voice", "leave")

        # Member moves between voice channels
        elif before.channel and after.channel and before.channel != after.channel:
            embed = await logembeds.voice_moved(member, before.channel, after.channel)
            await self.cog._send_log(guild, embed, "voice", "move")

        # Member is server-muted or unmuted
        elif before.mute != after.mute:
            channel = after.channel or before.channel
            if channel:
                entry = await self.cog._get_audit_log_entry(guild, member, discord.AuditLogAction.member_update)
                moderator = "Unknown"
                if entry and entry.before.mute != entry.after.mute:
                    moderator = entry.user

                embed = await logembeds.voice_server_muted(member, channel, moderator, after.mute)
                await self.cog._send_log(guild, embed, "voice", "mute")
            
        # Member is server-deafened or undeafened
        elif before.deaf != after.deaf:
            channel = after.channel or before.channel
            if channel:
                entry = await self.cog._get_audit_log_entry(guild, member, discord.AuditLogAction.member_update)
                moderator = "Unknown"
                if entry and entry.before.deaf != entry.after.deaf:
                    moderator = entry.user
                
                embed = await logembeds.voice_server_deafened(member, channel, moderator, after.deaf)
                await self.cog._send_log(guild, embed, "voice", "deafen")
