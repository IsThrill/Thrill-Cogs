import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, Optional
import asyncio
from .. import logembeds 

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

class RoleListeners(commands.Cog):
    """
    Handles all listeners related to guild role events.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None

    async def _get_audit_log_entry(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction) -> Optional[discord.AuditLogEntry]:
        """A helper function to fetch the latest audit log entry for a specific action."""
        await asyncio.sleep(0.5)
        entry = await guild.audit_logs(limit=5, action=action).find(lambda e: e.target.id == target_id)
        return entry

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Logs when a new role is created."""
        if not self.cog: return
        
        entry = await self._get_audit_log_entry(role.guild, role.id, discord.AuditLogAction.role_create)
        moderator = entry.user if entry else "Unknown Moderator"
        
        embed = await logembeds.role_created(role, moderator)
        await self.cog._send_log(role.guild, embed, "roles", "create")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Logs when a role is deleted."""
        if not self.cog: return
        
        entry = await self._get_audit_log_entry(role.guild, role.id, discord.AuditLogAction.role_delete)
        moderator = entry.user if entry else "Unknown Moderator"

        embed = await logembeds.role_deleted(role, moderator)
        await self.cog._send_log(role.guild, embed, "roles", "delete")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Logs when a role's name, color, or permissions are updated."""
        if not self.cog: return

        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.permissions != after.permissions:
            added_perms = [perm for perm, value in after.permissions if value and not getattr(before.permissions, perm)]
            if added_perms:
                changes.append(f"**Permissions Added:** `{'`, `'.join(p.replace('_', ' ').title() for p in added_perms)}`")
            
            removed_perms = [perm for perm, value in before.permissions if value and not getattr(after.permissions, perm)]
            if removed_perms:
                changes.append(f"**Permissions Removed:** `{'`, `'.join(p.replace('_', ' ').title() for p in removed_perms)}`")
        
        if changes:
            entry = await self._get_audit_log_entry(after.guild, after.id, discord.AuditLogAction.role_update)
            moderator = entry.user if entry else "Unknown Moderator"
            
            embed = await logembeds.role_updated(after, moderator, changes)
            await self.cog._send_log(after.guild, embed, "roles", "update")
