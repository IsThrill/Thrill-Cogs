import discord
import logging
import asyncio
import datetime

from redbot.core import commands, Config

log = logging.getLogger("red.isthrill.imagedeletelogger")


class ImageDeleteLogger(commands.Cog):
    """Logs deleted image messages to a specified channel."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2706371338)
        default_guild_settings = {
            "log_channel": None  # Channel where the deleted images will be logged
        }
        self.config.register_guild(**default_guild_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Triggered when a message is deleted."""
        if message.attachments:
            for attachment in message.attachments:
                if attachment.url.endswith(('jpg', 'jpeg', 'png', 'gif', 'webp')):
                    await self.log_deleted_image(message, attachment)
        elif message.embeds:
            for embed in message.embeds:
                if embed.url.endswith(('jpg', 'jpeg', 'png', 'gif', 'webp')):
                    await self.log_deleted_image(message, embed)

    async def log_deleted_image(self, message, attachment_or_embed):
        """Logs the deleted image in an embed format to the log channel."""
        log_channel_id = await self.config.guild(message.guild).log_channel()
        log_channel = self.bot.get_channel(log_channel_id)

        if log_channel:
            embed = discord.Embed(
                title="Image Deleted",
                description=f"An image posted by {message.author.mention} in {message.channel.mention} was deleted.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )

            embed.set_image(url=attachment_or_embed.url)
            embed.set_footer(text=f"Message ID: {message.id} | Author: {message.author.name}")

            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                log.warning(f"Failed to send message to the log channel due to missing permissions.")
        else:
            log.warning(f"Log channel not configured for guild {message.guild.id}.")

    @commands.group()
    @commands.has_permissions(administrator=True)
    async def imagelog(self, ctx):
        """Manage image deletion logging settings."""
        pass

    @imagelog.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """
        Set the channel where deleted image messages will be logged.
        Example: [p]imagelog setlogchannel #logs
        """
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"Log channel set to: {channel.mention}")

    @imagelog.command()
    @commands.has_permissions(administrator=True)
    async def checklogchannel(self, ctx):
        """Check the current log channel for deleted images."""
        log_channel_id = await self.config.guild(ctx.guild).log_channel()
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            await ctx.send(f"The current log channel is: {log_channel.mention}")
        else:
            await ctx.send("No log channel has been set yet.")

    @imagelog.command()
    @commands.has_permissions(administrator=True)
    async def disablelogging(self, ctx):
        """Disable image deletion logging."""
        await self.config.guild(ctx.guild).log_channel.set(None)
        await ctx.send("Image deletion logging has been disabled in this guild.")
