import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, List, Optional
import asyncio

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging
    from .. import logembeds

class MemberListeners(commands.Cog):
    """
    Contains all listeners related to member events, updates, and roles.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None

    async def _get_audit_log_entry(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction) -> Optional[discord.AuditLogEntry]:
        """A helper function to fetch the latest audit log entry for a specific action."""
        await asyncio.sleep(0.5) # Wait for audit log to populate
        entry = await guild.audit_logs(limit=1, action=action).find(lambda e: e.target.id == target_id)
        return entry

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Logs when a member joins the server."""
        if not self.cog: return

        embed = await logembeds.member_joined(member)
        await self.cog._send_log(member.guild, embed, "members", "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Logs when a member leaves, but ignores kicks to prevent duplicate logs."""
        if not self.cog: return

        # Check if this was a kick action; if so, the Moderation listener will handle it.
        kick_entry = await self._get_audit_log_entry(member.guild, member.id, discord.AuditLogAction.kick)
        if kick_entry and (discord.utils.utcnow() - kick_entry.created_at).total_seconds() < 5:
            return # This was a kick, do not log it as a leave.

        embed = await logembeds.member_left(member)
        await self.cog._send_log(member.guild, embed, "members", "leave")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Logs member nickname, role, and avatar changes."""
        if not self.cog or before.bot: return
        guild = after.guild

        # 1. Nickname Change
        if before.nick != after.nick:
            audit_entry = await self._get_audit_log_entry(guild, after.id, discord.AuditLogAction.member_update)
            moderator = audit_entry.user if audit_entry and audit_entry.before.nick != audit_entry.after.nick else after # If no moderator, user changed their own nick
            
            embed = await logembeds.member_nickname_changed(after, moderator, before.nick, after.nick)
            await self.cog._send_log(guild, embed, "members", "nick_change")

        # 2. Role Change
        if before.roles != after.roles:
            audit_entry = await self._get_audit_log_entry(guild, after.id, discord.AuditLogAction.member_role_update)
            moderator = audit_entry.user if audit_entry else "Unknown Moderator"

            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]

            if added_roles or removed_roles:
                embed = await logembeds.member_roles_updated(after, moderator, added_roles, removed_roles)
                await self.cog._send_log(guild, embed, "members", "role_change")
        
        # 3. Avatar Change (Server-specific)
        if before.display_avatar != after.display_avatar:
            embed = await logembeds.member_avatar_changed(after)
            await self.cog._send_log(guild, embed, "members", "avatar_change")