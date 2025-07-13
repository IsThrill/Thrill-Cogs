import discord
import asyncio 
from discord import app_commands
from redbot.core import commands, Config
from typing import List, Optional

from .config import TRLConfig, DEFAULT_GUILD_SETTINGS

class ThrillsRobustLogging(commands.GroupCog, group_name="logset"):
    """A powerful and robust logging cog."""

    def __init__(self, bot):
        self.bot = bot
        self.config = TRLConfig()
        self.toggles_map = DEFAULT_GUILD_SETTINGS["log_toggles"]
        super().__init__()

    # --- Centralized Helpers ---
    async def _send_log(self, guild: discord.Guild, embed: discord.Embed, category: str, setting_name: str, file: discord.File = None):
        """The central function for sending all log messages."""
        if not guild or not embed:
            return

        if not await self.config.get_toggle(guild, category, setting_name):
            return
        
        log_channels = await self.config.get_log_channels(guild)
        log_channel_id = log_channels.get(category) or log_channels.get("default")
        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel or not log_channel.permissions_for(guild.me).send_messages:
            return
            
        await log_channel.send(embed=embed, file=file)

    async def _get_audit_log_entry(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction) -> Optional[discord.AuditLogEntry]:
        """A centralized helper to fetch the latest audit log entry."""
        await asyncio.sleep(0.5)
        try:
            entry = await guild.audit_logs(limit=5, action=action).find(lambda e: e.target.id == target_id)
            return entry
        except discord.Forbidden:
            return None

    # --- Autocomplete Functions for Commands ---
    async def category_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocompletes the category parameter."""
        categories = list(self.toggles_map.keys())
        return [
            app_commands.Choice(name=cat.replace("_", " ").title(), value=cat)
            for cat in categories if current.lower() in cat.lower()
        ]

    async def setting_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocompletes the setting based on the selected category."""
        category = interaction.namespace.category
        if not category or category not in self.toggles_map:
            return []
        
        settings = list(self.toggles_map[category].keys())
        return [
            app_commands.Choice(name=setting.replace("_", " ").title(), value=setting)
            for setting in settings if current.lower() in setting.lower()
        ]

    # --- Slash Commands ---
    @app_commands.command(name="channel", description="Set a log channel for a specific category.")
    @app_commands.describe(
        category="The category of logs to set the channel for.",
        channel="The text channel to send logs to. Leave blank to reset."
    )
    @app_commands.choices(category=[
        app_commands.Choice(name=cat.replace("_", " ").title(), value=cat) 
        for cat in DEFAULT_GUILD_SETTINGS["log_channels"].keys()
    ])
    @commands.admin_or_can_manage_channel()
    async def logset_channel(self, interaction: discord.Interaction, category: str, channel: discord.TextChannel = None):
        """Sets a log channel for a specific category."""
        await self.config.set_log_channel(interaction.guild, category, channel.id if channel else None)
        if channel:
            await interaction.response.send_message(f"Logs for the `{category}` category will now be sent to {channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Reset the log channel for the `{category}` category.", ephemeral=True)

    @app_commands.command(name="toggle", description="Toggle a specific logging event on or off.")
    @app_commands.autocomplete(category=category_autocomplete, setting=setting_autocomplete)
    @app_commands.describe(category="The category of the event.", setting="The specific event to toggle.")
    @commands.admin_or_can_manage_channel()
    async def logset_toggle(self, interaction: discord.Interaction, category: str, setting: str):
        """Toggles a specific logging event on or off."""
        if category not in self.toggles_map or setting not in self.toggles_map[category]:
            await interaction.response.send_message("Invalid category or setting name. Please use the autocomplete options.", ephemeral=True)
            return

        current_value = await self.config.get_toggle(interaction.guild, category, setting)
        new_value = not current_value
        await self.config.set_toggle(interaction.guild, category, setting, new_value)
        status = "enabled" if new_value else "disabled"
        await interaction.response.send_message(f"Logging for `{setting}` in `{category}` has been **{status}**.", ephemeral=True)
        
    @app_commands.command(name="status", description="View the current logging configuration.")
    @commands.admin_or_can_manage_channel()
    async def logset_status(self, interaction: discord.Interaction):
        """Displays the current logging settings for the server."""
        await interaction.response.defer(ephemeral=True)
        
        all_channels = await self.config.get_log_channels(interaction.guild)
        all_toggles = await self.config.get_all_toggles(interaction.guild)
        
        embed = discord.Embed(title="Logging Status", color=await self.bot.get_embed_color(interaction.guild))
        
        channel_desc = []
        for cat, cid in all_channels.items():
            ch = interaction.guild.get_channel(cid) if cid else None
            channel_desc.append(f"**{cat.title()}**: {ch.mention if ch else 'Not Set'}")
        embed.add_field(name="Log Channels", value="\n".join(channel_desc), inline=False)
        
        for category, settings in all_toggles.items():
            toggle_desc = []
            for setting, enabled in settings.items():
                emoji = "✅" if enabled else "❌"
                toggle_desc.append(f"{emoji} {setting.replace('_', ' ').title()}")
            embed.add_field(name=f"{category.title()} Toggles", value="\n".join(toggle_desc), inline=True)
            
        await interaction.followup.send(embed=embed)