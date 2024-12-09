import discord
import logging
from redbot.core import commands, Config

log = logging.getLogger("red.isthrill.imagelogs")

class ImageLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild_settings = {
            "log_channel": None
        }
        self.config.register_guild(**default_guild_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Logs when a message is deleted, regardless of content."""
        
        # Fetch the log channel
        log_channel_id = await self.config.guild(message.guild).log_channel()
        log.info(f"Log channel ID fetched: {log_channel_id}")  # Debug log
        
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)

            if log_channel:
                # Send "Yippee" message to the log channel when any message is deleted
                await log_channel.send("Yippee")
                log.info("Yippee message sent successfully.")  # Debug log
            else:
                await message.channel.send("Log channel not found.")
                log.error("Log channel not found. Check the channel ID.")
        else:
            await message.channel.send("Log channel is not set.")
            log.warning("No log channel set.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """
        Set the channel to log deleted message events.
        Example: [p]setlogchannel #image-logs
        """
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"Log channel set to: {channel.mention}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def checklogchannel(self, ctx):
        """Check the current log channel."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel()
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            await ctx.send(f"The current log channel is: {log_channel.mention}")
        else:
            await ctx.send("No log channel has been set.")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removelogchannel(self, ctx):
        """
        Remove the current log channel.
        Example: [p]removelogchannel
        """
        await self.config.guild(ctx.guild).log_channel.set(None)
        await ctx.send("The log channel has been reset. No further deletions will be logged until a new channel is set.")
