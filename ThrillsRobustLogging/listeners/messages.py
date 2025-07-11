import discord
from redbot.core.bot import Red
from redbot.core.cog_manager import CogManager

from .. import logembeds

class MessageListeners:
    """
    Contains all listeners related to message events.
    """

    def __init__(self, bot: Red, cog):
        self.bot = bot
        self.cog = cog
        self.config = cog.config

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed, category: str):
        """A helper function to check settings and send the log."""
        if not guild or not embed:
            return

        # Check if the specific log toggle is enabled
        if not await self.config.get_toggle(guild, category, embed.title.split()[1].lower()):
            return
        
        # Get the channel configuration for the guild
        log_channels = await self.config.get_log_channels(guild)
        
        # Find the correct channel to send the log to
        log_channel_id = log_channels.get(category) or log_channels.get("default")
        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel or not log_channel.permissions_for(guild.me).send_messages:
            return
            
        await log_channel.send(embed=embed)

    async def on_message_delete(self, message: discord.Message):
        """Handler for the on_message_delete event."""
        if not message.guild or message.author.bot:
            return

        embed = await logembeds.message_deleted(message)
        await self-._send_log(message.guild, embed, "messages")

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handler for the on_message_edit event."""
        if not before.guild or before.author.bot or before.content == after.content:
            return

        embed = await logembeds.message_edited(before, after)
        await self._send_log(before.guild, embed, "messages")