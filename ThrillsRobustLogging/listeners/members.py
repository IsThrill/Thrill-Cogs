import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, List, Optional
import asyncio
from datetime import datetime, timezone
from .. import logembeds

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

class MemberListeners(commands.Cog):
    """
    Contains all listeners related to member events, updates, and roles.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None
        self.invite_cache = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Caches all invites when the bot is ready."""
        for guild in self.bot.guilds:
            await self._cache_invites(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Caches invites when the bot joins a new guild."""
        await self._cache_invites(guild)
        
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Updates cache when an invite is created."""
        await self._cache_invites(invite.guild)
        
    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Updates cache when an invite is deleted."""
        await self._cache_invites(invite.guild)

    async def _cache_invites(self, guild: discord.Guild):
        """Helper to fetch and store a guild's invites and their uses."""
        try:
            self.invite_cache[guild.id] = {invite.code: invite.uses for invite in await guild.invites()}
        except discord.Forbidden:
            self.invite_cache[guild.id] = {}

    async def _find_used_invite(self, member: discord.Member) -> Optional[discord.Invite]:
        """Compares cached invites with current ones to find the used invite."""
        guild = member.guild
        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return None 

        cached_invites = self.invite_cache.get(guild.id, {})
        
        for invite in current_invites:
            if invite.code not in cached_invites or invite.uses > cached_invites.get(invite.code, 0):
                self.invite_cache[guild.id] = {i.code: i.uses for i in current_invites}
                return invite
        return None

    # --- Main Listeners ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Logs when a member joins the server with detailed invite info."""
        if not self.cog: return

        used_invite = await self._find_used_invite(member)
        is_new = (datetime.now(timezone.utc) - member.created_at).days <= 2

        embed = await logembeds.member_joined(member, used_invite, is_new)
        await self.cog._send_log(member.guild, embed, "members", "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Logs when a member leaves, but ignores kicks to prevent duplicate logs."""
        if not self.cog: return
        kick_entry = await self.cog._get_audit_log_entry(member.guild, member, discord.AuditLogAction.kick)
        if kick_entry and (discord.utils.utcnow() - kick_entry.created_at).total_seconds() < 5:
            return
        embed = await logembeds.member_left(member)
        await self.cog._send_log(member.guild, embed, "members", "leave")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Logs member nickname, role, and avatar changes."""
        if not self.cog or before.bot: return
        guild = after.guild

        if before.nick != after.nick:
            audit_entry = await self.cog._get_audit_log_entry(guild, after, discord.AuditLogAction.member_update)
            moderator = audit_entry.user if audit_entry and audit_entry.before.nick != audit_entry.after.nick else after
            embed = await logembeds.member_nickname_changed(after, moderator, before.nick, after.nick)
            await self.cog._send_log(guild, embed, "members", "nick_change")

        if before.roles != after.roles:
            audit_entry = await self.cog._get_audit_log_entry(guild, after, discord.AuditLogAction.member_role_update)
            moderator = audit_entry.user if audit_entry else "Unknown Moderator"
            added_roles = [r for r in after.roles if r not in before.roles]
            removed_roles = [r for r in before.roles if r not in after.roles]
            if added_roles or removed_roles:
                embed = await logembeds.member_roles_updated(after, moderator, added_roles, removed_roles)
                await self.cog._send_log(guild, embed, "members", "role_change")
        
        if before.display_avatar != after.display_avatar:
            embed = await logembeds.member_avatar_changed(after)
            await self.cog._send_log(guild, embed, "members", "avatar_change")
