import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, Optional
import asyncio 
from .. import logembeds 

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

class ModerationListeners(commands.Cog):
    """
    Handles all listeners related to core moderation events.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None


    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        """Logs when a member is banned."""
        if not self.cog: return

        audit_entry = await self.cog._get_audit_log_entry(guild, user, discord.AuditLogAction.ban)
        moderator = audit_entry.user if audit_entry else "Unknown"
        reason = audit_entry.reason if audit_entry else "No reason provided."

        embed = await logembeds.member_banned(user, moderator, reason)
        await self.cog._send_log(guild, embed, "moderation", "ban")

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Logs when a member is unbanned."""
        if not self.cog: return

        audit_entry = await self.cog._get_audit_log_entry(guild, user, discord.AuditLogAction.unban)
        moderator = audit_entry.user if audit_entry else "Unknown"
        reason = audit_entry.reason if audit_entry else "No reason provided."

        embed = await logembeds.member_unbanned(user, moderator, reason)
        await self.cog._send_log(guild, embed, "moderation", "unban")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Differentiates between a kick and a normal leave."""
        if not self.cog: return

        kick_entry = await self.cog._get_audit_log_entry(member.guild, member, discord.AuditLogAction.kick)

        if kick_entry and (discord.utils.utcnow() - kick_entry.created_at).total_seconds() < 5:
            moderator = kick_entry.user
            reason = kick_entry.reason if kick_entry.reason else "No reason provided."

            embed = await logembeds.member_kicked(member, moderator, reason)
            await self.cog._send_log(member.guild, embed, "moderation", "kick")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Logs timeouts (communication mutes)."""
        if not self.cog or after.bot: return

        # Timeout (Mute) detection
        if not before.is_timed_out() and after.is_timed_out():
            audit_entry = await self.cog._get_audit_log_entry(after.guild, after, discord.AuditLogAction.member_update)
            moderator = audit_entry.user if audit_entry else "Unknown"
            reason = audit_entry.reason if audit_entry else "No reason provided."
            until = after.timed_out_until

            embed = await logembeds.member_timed_out(after, moderator, reason, until)
            await self.cog._send_log(after.guild, embed, "moderation", "timeout_add")

        # Timeout (Mute) removal detection
        elif before.is_timed_out() and not after.is_timed_out():
            audit_entry = await self.cog._get_audit_log_entry(after.guild, after, discord.AuditLogAction.member_update)
            moderator = audit_entry.user if audit_entry else "Unknown"
            reason = audit_entry.reason if audit_entry else "No reason provided."

            embed = await logembeds.member_timeout_removed(after, moderator, reason)
            await self.cog._send_log(after.guild, embed, "moderation", "timeout_remove")
