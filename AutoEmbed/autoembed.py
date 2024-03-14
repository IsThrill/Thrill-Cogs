from redbot.core import commands, Config
import discord
import logging

log = logging.getLogger("red.isthrill.autoembed")

class AutoEmbed(commands.Cog):
    """Embeds a message based on reactions in a specified channel."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2706371337)
        default_guild_settings = {
            "embed_enabled": True,
            "embed_title": None,
            "embed_thumbnail": None,
            "embed_color": discord.Color.blue().value,
            "auto_react_channel": None
        }
        self.config.register_guild(**default_guild_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Event listener for reaction adding."""
        if user.bot:
            return

        auto_react_channel_id = await self.config.guild(reaction.message.guild).auto_react_channel()
        if reaction.message.channel.id != auto_react_channel_id:
            return

        if reaction.emoji == "✅":  # Checkmark emoji
            await self.create_embed(reaction.message)
            await reaction.message.delete()
        elif reaction.emoji == "❌":  # X emoji
            await reaction.message.clear_reactions()

    async def create_embed(self, message):
        """Function to create embed from message."""
        embed_enabled = await self.config.guild(message.guild).embed_enabled()
        if not embed_enabled:
            return

        embed_title = await self.config.guild(message.guild).embed_title()
        embed_thumbnail = await self.config.guild(message.guild).embed_thumbnail()
        embed_color = discord.Color(await self.config.guild(message.guild).embed_color())

        embed = discord.Embed(
            title=embed_title or "Message Embed",
            description=message.content,
            color=embed_color
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
        await message.channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setembedoptions(self, ctx, title=None, thumbnail=None, color=None):
        """Set the embed options."""
        try:
            if color:
                color = discord.Color(int(color, 16))
        except ValueError:
            await ctx.send("Invalid color format. Please provide a hexadecimal color code.")
            return

        await self.config.guild(ctx.guild).embed_title.set(title)
        await self.config.guild(ctx.guild).embed_thumbnail.set(thumbnail)
        await self.config.guild(ctx.guild).embed_color.set(color.value if color else None)

        await ctx.send("Embed options set successfully.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setautoreactchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel where the bot will auto react to messages."""
        await self.config.guild(ctx.guild).auto_react_channel.set(channel.id)
        await ctx.send(f"Auto react channel set to {channel.mention}.")
