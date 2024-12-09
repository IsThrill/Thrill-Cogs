import discord
from discord.ext import commands
from redbot.core import Config

import logging

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
        """Logs images when a message is deleted."""
        if not message.guild:
            return  # Ignore DMs

        # Fetch the log channel
        log_channel_id = await self.config.guild(message.guild).log_channel()
        if not log_channel_id:
            return  # No log channel configured

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            log.warning(f"Log channel with ID {log_channel_id} not found in guild {message.guild.name}.")
            return

        # Extract image attachments
        images = [
            attachment for attachment in message.attachments 
            if attachment.content_type and attachment.content_type.startswith("image")
        ]
        
        if not images:
            return  # No images to log

        embeds = []
        for index, image in enumerate(images):
            embed = discord.Embed(
                title=f"Deleted Image {index + 1} of {len(images)}",
                description=f"Message deleted in {message.channel.mention}",
                color=discord.Color.red(),
                timestamp=message.created_at
            )
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            embed.set_footer(text=f"Message ID: {message.id}")
            embed.set_image(url=image.url)
            embeds.append(embed)

        # Send embeds in batches of 10
        for i in range(0, len(embeds), 10):
            await log_channel.send(embeds=embeds[i:i + 10])

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
