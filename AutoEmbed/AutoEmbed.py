from redbot.core import commands, Config
import discord

log = logging.getLogger("red.isthrill.AutoEmbeder")

class AutoEmbeder(commands.Cog):
    """Embeds A Message Based On Reactions In A Specified Channel."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2706371337)
        default_guild_settings = {
            "embed_enabled": True,
            "embed_title": None,
            "embed_thumbnail": None,
            "embed_color": discord.Color.blue(),
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

        if reaction.message.author.bot:
            if reaction.message.channel.id == await self.config.guild(reaction.message.guild).auto_react_channel():
                if reaction.emoji == "✅":  # Checkmark emoji
                    await self.create_embed(reaction.message)
                    await reaction.message.delete()
                elif reaction.emoji == "❌":  # X emoji
                    await reaction.message.clear_reactions()

    async def create_embed(self, message):
        """Function to create embed from message."""
        embed_enabled = await self.config.guild(message.guild).embed_enabled()
        if embed_enabled:
            embed_title = await self.config.guild(message.guild).embed_title()
            embed_thumbnail = await self.config.guild(message.guild).embed_thumbnail()
            embed_color = await self.config.guild(message.guild).embed_color()

            embed = discord.Embed(
                title=embed_title if embed_title else "Message Embed",
                description=message.content,
                color=embed_color
            )
            embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
            await message.channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_embed_options(self, ctx, title=None, thumbnail=None, color=None):
        """Set the embed options."""
        if color:
            try:
                color = discord.Color(int(color, 16))  # Convert hex color to discord.Color object
            except ValueError:
                await ctx.send("Invalid color format. Please provide a hexadecimal color code.")
                return

        await self.config.guild(ctx.guild).embed_title.set(title)
        await self.config.guild(ctx.guild).embed_thumbnail.set(thumbnail)
        await self.config.guild(ctx.guild).embed_color.set(color)
        await ctx.send("Embed options set successfully.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def toggle_embed(self, ctx):
        """Toggle embedding messages."""
        current_status = await self.config.guild(ctx.guild).embed_enabled()
        new_status = not current_status
        await self.config.guild(ctx.guild).embed_enabled.set(new_status)
        await ctx.send(f"Embedding messages is now {'enabled' if new_status else 'disabled'}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_auto_react_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where the bot will auto react to messages."""
        await self.config.guild(ctx.guild).auto_react_channel.set(channel.id)
        await ctx.send(f"Auto react channel set to {channel.mention}.")

    async def cog_command_error(self, ctx, error):
        """Error handler for the cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You are not allowed to use this command.")
