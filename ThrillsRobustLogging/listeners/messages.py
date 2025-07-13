import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, List, Optional
import asyncio
from io import StringIO

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging
    from .. import logembeds

class MessageListeners(commands.Cog):
    """
    Handles all listeners related to message events.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Handler for the on_message_delete event, with audit log support."""
        if not message.guild or message.author.bot or not self.cog:
            return

        await asyncio.sleep(0.7) # Slightly increased delay for this specific event
        
        audit_entry = await message.guild.audit_logs(
            action=discord.AuditLogAction.message_delete, limit=1
        ).find(
            lambda e: e.target.id == message.author.id 
            and e.extra.channel.id == message.channel.id
            and e.extra.count == 1 # Ensures it was a single message deletion
        )

        embed = None
        if audit_entry and (discord.utils.utcnow() - audit_entry.created_at).total_seconds() < 5:
            moderator = audit_entry.user
            if moderator.id != message.author.id:
                embed = await logembeds.message_deleted_by_mod(message, moderator)
        
        if not embed:
            embed = await logembeds.message_deleted(message)
        
        if embed:
            await self.cog._send_log(message.guild, embed, "messages", "delete")

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        """Handler for bulk message deletions (purges)."""
        if not messages or not self.cog:
            return
            
        guild = messages[0].guild
        channel = messages[0].channel
        await asyncio.sleep(0.5)
        
        audit_entry = await guild.audit_logs(
            limit=1, action=discord.AuditLogAction.message_bulk_delete
        ).find(lambda e: e.target.id == channel.id)

        moderator = audit_entry.user if audit_entry else "Unknown Moderator"

        transcript = ""
        for msg in reversed(messages):
            transcript += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author} ({msg.author.id}):\n{msg.content}\n\n"
        
        file = discord.File(StringIO(transcript), filename=f"purge-{channel.name}-{discord.utils.utcnow().timestamp()}.txt")
        embed = await logembeds.messages_purged(len(messages), channel, moderator)
        
        await self.cog._send_log(guild, embed, "messages", "purge", file=file)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handler for the on_message_edit event."""
        if not before.guild or before.author.bot or before.content == after.content or not self.cog:
            return

        embed = await logembeds.message_edited(before, after)
        if embed:
            await self.cog._send_log(before.guild, embed, "messages", "edit")