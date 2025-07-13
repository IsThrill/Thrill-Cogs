import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, List, Optional
import asyncio

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging
    from .. import logembeds

class ChannelListeners(commands.Cog):
    """
    Handles all listeners related to channel, category, and thread events.
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
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Logs when a channel, category, or voice channel is created."""
        if not self.cog or isinstance(channel, discord.Thread): return

        entry = await self._get_audit_log_entry(channel.guild, channel.id, discord.AuditLogAction.channel_create)
        moderator = entry.user if entry else "Unknown Moderator"
        
        embed = await logembeds.channel_created(channel, moderator)
        await self.cog._send_log(channel.guild, embed, "channels", "create")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Logs when a channel, category, or voice channel is deleted."""
        if not self.cog or isinstance(channel, discord.Thread): return

        entry = await self._get_audit_log_entry(channel.guild, channel.id, discord.AuditLogAction.channel_delete)
        moderator = entry.user if entry else "Unknown Moderator"

        embed = await logembeds.channel_deleted(channel, moderator)
        await self.cog._send_log(channel.guild, embed, "channels", "delete")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Logs detailed updates to a channel."""
        if not self.cog or isinstance(after, discord.Thread): return
        
        changes: List[str] = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.category != after.category:
            b_cat = f"`{before.category.name}`" if before.category else "None"
            a_cat = f"`{after.category.name}`" if after.category else "None"
            changes.append(f"**Category:** {b_cat} → {a_cat}")
            
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                b_topic = f"```{before.topic}```" if before.topic else "Not Set"
                a_topic = f"```{after.topic}```" if after.topic else "Not Set"
                changes.append(f"**Topic Changed**\n**Before:** {b_topic}\n**After:** {a_topic}")
            if before.slowmode_delay != after.slowmode_delay:
                changes.append(f"**Slowmode:** `{before.slowmode_delay}s` → `{after.slowmode_delay}s`")

        if changes:
            entry = await self._get_audit_log_entry(after.guild, after.id, discord.AuditLogAction.channel_update)
            moderator = entry.user if entry else "Unknown Moderator"
            embed = await logembeds.channel_updated(after, moderator, changes)
            await self.cog._send_log(after.guild, embed, "channels", "update")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """Logs when a new thread is created."""
        if not self.cog or not thread.owner: return

        embed = await logembeds.thread_created(thread)
        await self.cog._send_log(thread.guild, embed, "channels", "thread_create")

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        """Logs when a thread is deleted."""
        if not self.cog: return
        
        entry = await self._get_audit_log_entry(thread.guild, thread.id, discord.AuditLogAction.thread_delete)
        moderator = entry.user if entry else "Unknown"

        embed = await logembeds.thread_deleted(thread, moderator)
        await self.cog._send_log(thread.guild, embed, "channels", "thread_delete")

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        """Logs when a thread is archived, locked, or has its name changed."""
        if not self.cog: return
        
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.archived != after.archived:
            action = "archived" if after.archived else "unarchived"
            changes.append(f"**Thread was {action}**")
        if before.locked != after.locked:
            action = "locked" if after.locked else "unlocked"
            changes.append(f"**Thread was {action}**")
            
        if changes:
            embed = await logembeds.thread_updated(after, changes)
            await self.cog._send_log(after.guild, embed, "channels", "thread_update")