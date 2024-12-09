import discord
from discord.ext import commands
import datetime

class ImageDeleteLogger(commands.Cog):
    """Logs deleted image messages in a specified channel"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Triggered when a message is deleted"""
        # Check if the deleted message contained an image attachment
        if message.attachments:
            for attachment in message.attachments:
                if attachment.url.endswith(('jpg', 'jpeg', 'png', 'gif', 'webp')):
                    await self.log_deleted_image(message, attachment)

        # Check if the deleted message contained an embed with an image
        elif message.embeds:
            for embed in message.embeds:
                if embed.url.endswith(('jpg', 'jpeg', 'png', 'gif', 'webp')):
                    await self.log_deleted_image(message, embed)

    async def log_deleted_image(self, message, attachment_or_embed):
        """Logs the deleted image in an embed format to the log channel"""
        log_channel_id = 123456789012345678  # Replace this with your actual log channel ID
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

            # Send the embed to the log channel
            await log_channel.send(embed=embed)

    @commands.command()
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """Command to set the log channel."""
        # Save the log channel in a persistent storage, like a config file or database
        # For simplicity, we're setting it in memory for this example.
        self.log_channel = channel.id
        await ctx.send(f"Log channel set to {channel.mention}")