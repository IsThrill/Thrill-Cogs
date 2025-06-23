import discord
from redbot.core import commands, Config
import logging
import aiohttp
import io

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
    if not message.guild or not message.attachments:
        return

    log_channel_id = await self.config.guild(message.guild).log_channel()
    if not log_channel_id:
        return

    log_channel = self.bot.get_channel(log_channel_id)
    if not log_channel:
        log.warning(f"Log channel with ID {log_channel_id} not found in guild {message.guild.name}.")
        return

    image_attachments = [
        att for att in message.attachments if att.content_type and att.content_type.startswith("image")
    ]
    if not image_attachments:
        return

    files_to_upload = []
    async with aiohttp.ClientSession() as session:
        for attachment in image_attachments:
            try:
                async with session.get(attachment.url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        files_to_upload.append(discord.File(io.BytesIO(image_data), filename=attachment.filename))
                    else:
                        log.warning(f"Failed to download image {attachment.url} with status {response.status}")
            except Exception as e:
                log.error(f"Error downloading image {attachment.url}: {e}")

    if not files_to_upload:
        log.info(f"Could not download any of the {len(image_attachments)} images from deleted message {message.id}.")
        return

    description = f"Message with **{len(files_to_upload)}** image(s) deleted in {message.channel.mention}"
    if message.content:
        description += f"\n\n**Content:**\n>>> {message.content}"

    embed = discord.Embed(
        title="Deleted Image(s)",
        description=description,
        color=discord.Color.red(),
        timestamp=message.created_at
    )
    embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
    embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
    
    
    embed.set_image(url=f"attachment://{files_to_upload[0].filename}")

    try:
        await log_channel.send(embed=embed, files=files_to_upload)
    except discord.HTTPException as e:
        log.error(f"Failed to upload {len(files_to_upload)} images to log channel. Error: {e}")

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
