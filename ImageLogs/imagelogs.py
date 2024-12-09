import discord
import logging
import asyncio

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
        """Logs the deletion of images from messages."""
        if message.attachments:
            # Filter out non-image attachments
            image_attachments = [
                attachment for attachment in message.attachments if attachment.url.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'))
            ]
            
            if image_attachments:
                log_channel_id = await self.config.guild(message.guild).log_channel()
                
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    
                    if log_channel:
                        # Debug: Check if the log channel is correctly retrieved
                        log.debug(f"Log channel retrieved: {log_channel.name} ({log_channel.id})")
                        
                        for attachment in image_attachments:
                            embed = discord.Embed(
                                title="Image Deleted",
                                description=f"An image was deleted from a message by **{message.author}**",
                                color=discord.Color.red()
                            )
                            embed.add_field(name="Message Content", value=message.content or "No content")
                            embed.add_field(name="Image URL", value=attachment.url)
                            embed.add_field(name="Message Author", value=str(message.author))
                            embed.set_footer(text=f"Message deleted at {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            try:
                                await log_channel.send(embed=embed)
                            except discord.Forbidden:
                                log.warning(f"Failed to send message to {log_channel} due to insufficient permissions.")
                            except discord.HTTPException as e:
                                log.error(f"Error sending to log channel: {e}")
                    else:
                        log.warning(f"Invalid log channel ID: {log_channel_id}")
                else:
                    log.warning(f"No log channel set for guild {message.guild.id}")
            else:
                # Debug: No valid image attachments found
                log.debug("No valid image attachments found in the deleted message.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx, channel: discord.TextChannel):
        """
        Set the channel to log deleted image events.
        Example: [p]imagedelogger setlogchannel #image-logs
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
        Example: [p]imagedelogger removelogchannel
        """
        await self.config.guild(ctx.guild).log_channel.set(None)
        await ctx.send("The log channel has been reset. No further image deletions will be logged until a new channel is set.")
