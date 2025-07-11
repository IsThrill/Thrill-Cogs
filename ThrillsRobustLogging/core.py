import discord
from discord import app_commands
from redbot.core import commands, Config

# Import components
from .config import TRLConfig, DEFAULT_GUILD_SETTINGS
from . import logembeds

class ThrillsRobustLogging(commands.GroupCog, group_name="logset"):
    """
    A powerful and robust logging cog
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = TRLConfig()
        super().__init__()

    # --- Improved Helper ---
    async def _send_log(self, guild: discord.Guild, embed: discord.Embed, category: str, setting_name: str):
        if not guild or not embed:
            return

        # Checks the specific toggle directly, which is more accurate.
        if not await self.config.get_toggle(guild, category, setting_name):
            return
        
        log_channels = await self.config.get_log_channels(guild)
        log_channel_id = log_channels.get(category) or log_channels.get("default")
        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel or not log_channel.permissions_for(guild.me).send_messages:
            return
            
        await log_channel.send(embed=embed)

    # --- Slash Commands ---
    @app_commands.command(name="channel", description="Set a log channel for a specific category.")
    @app_commands.describe(
        category="The category of logs to set the channel for.",
        channel="The text channel to send logs to. Leave blank to reset."
    )
    @app_commands.choices(category=[
        app_commands.Choice(name=cat, value=cat) for cat in DEFAULT_GUILD_SETTINGS["log_channels"].keys()
    ])
    @app_commands.checks.admin_or_permissions(manage_guild=True)
    async def logset_channel(self, interaction: discord.Interaction, category: str, channel: discord.TextChannel = None):
        """Sets a log channel for a specific category."""
        await self.config.set_log_channel(interaction.guild, category, channel.id if channel else None)
        if channel:
            await interaction.response.send_message(f"Logs for the `{category}` category will now be sent to {channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Reset the log channel for the `{category}` category.", ephemeral=True)

    @app_commands.command(name="toggle", description="Toggle a specific logging event on or off.")
    @app_commands.describe(
        category="The category of the event.",
        setting="The specific event to toggle."
    )
    @app_commands.checks.admin_or_permissions(manage_guild=True)
    async def logset_toggle(self, interaction: discord.Interaction, category: str, setting: str):
        """Toggles a specific logging event on or off."""
        all_toggles = await self.config.get_all_toggles(interaction.guild)
        if category not in all_toggles or setting not in all_toggles[category]:
            await interaction.response.send_message("Invalid category or setting name.", ephemeral=True)
            return

        current_value = all_toggles[category][setting]
        new_value = not current_value
        await self.config.set_toggle(interaction.guild, category, setting, new_value)
        status = "enabled" if new_value else "disabled"
        await interaction.response.send_message(f"Logging for `{setting}` in `{category}` has been **{status}**.", ephemeral=True)

    # --- Event Listeners (Consolidated) ---
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot: return
        embed = await logembeds.message_deleted(message)
        await self._send_log(message.guild, embed, "messages", "delete")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content: return
        embed = await logembeds.message_edited(before, after)
        await self._send_log(before.guild, embed, "messages", "edit")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = await logembeds.member_joined(member)
        await self._send_log(member.guild, embed, "members", "join")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = await logembeds.member_left(member)
        await self._send_log(member.guild, embed, "members", "leave")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        # embed = await logembeds.member_banned(guild, user) # Placeholder
        # await self._send_log(guild, embed, "moderation", "ban")
        pass