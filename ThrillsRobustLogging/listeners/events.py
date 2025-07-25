import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING
import asyncio
from .. import logembeds

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

class EventListeners(commands.Cog):
    """
    Handles listeners for event-based features like Scheduled Events and Stages.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        """Logs when a scheduled event is created."""
        if not self.cog: return
        embed = await logembeds.scheduled_event_created(event)
        await self.cog._send_log(event.guild, embed, "events", "scheduled_event_create")

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        """Logs when a scheduled event is deleted."""
        if not self.cog: return
        embed = await logembeds.scheduled_event_deleted(event)
        await self.cog._send_log(event.guild, embed, "events", "scheduled_event_delete")

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        """Logs when a scheduled event is updated."""
        if not self.cog: return
        embed = await logembeds.scheduled_event_updated(before, after)
        if embed: 
            await self.cog._send_log(after.guild, embed, "events", "scheduled_event_update")

    @commands.Cog.listener()
    async def on_stage_instance_create(self, stage_instance: discord.StageInstance):
        """Logs when a stage goes live."""
        if not self.cog: return
        
        entry = await self.cog._get_audit_log_entry(stage_instance.guild, stage_instance, discord.AuditLogAction.stage_instance_create)
        moderator = entry.user if entry else "Unknown"

        embed = await logembeds.stage_started(stage_instance, moderator)
        await self.cog._send_log(stage_instance.guild, embed, "events", "stage_start")

    @commands.Cog.listener()
    async def on_stage_instance_delete(self, stage_instance: discord.StageInstance):
        """Logs when a stage ends."""
        if not self.cog: return

        entry = await self.cog._get_audit_log_entry(stage_instance.guild, stage_instance, discord.AuditLogAction.stage_instance_delete)
        moderator = entry.user if entry else "Unknown"
        
        embed = await logembeds.stage_ended(stage_instance, moderator)
        await self.cog._send_log(stage_instance.guild, embed, "events", "stage_end")
