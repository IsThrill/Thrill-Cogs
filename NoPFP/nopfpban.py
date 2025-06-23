import discord
import logging
import asyncio

from redbot.core import commands, Config
from redbot.core.bot import Red

log = logging.getLogger("red.isthrill.nopfpban")


class NoPfpBan(commands.Cog):
    """
    Automatically bans or kicks users who join without a profile picture.
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2706371337)
        default_guild_settings = {
            "enabled": False,
            "reason": "Automated action: No profile picture",
            "action": "ban",
            "log_channel": None
        }
        self.config.register_guild(**default_guild_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        settings = await self.config.guild(member.guild).all()
        if not settings["enabled"] or member.avatar:
            return
        
        action_past_tense = "banned" if settings['action'] == "ban" else "kicked"
        
        try:
            dm_message = (
                f"You have been automatically {action_past_tense} from {member.guild.name} "
                f"for the following reason: {settings['reason']}"
            )
            await member.send(dm_message)
            await asyncio.sleep(2)
        except discord.Forbidden:
            log.info(f"Could not DM {member} ({member.id}), proceeding with action.")

        action_func = member.ban if settings["action"] == "ban" else member.kick

        try:
            await action_func(reason=settings["reason"])
            log.info(f"Successfully {action_past_tense} {member} from {member.guild.name}.")
            await self._log_action(
                member,
                f"User {action_past_tense.capitalize()}",
                f"**{member.display_name}** (`{member.id}`) was automatically {action_past_tense}.",
                discord.Color.green() if settings['action'] == 'kick' else discord.Color.orange()
            )
        except discord.Forbidden:
            log.error(f"Failed to {settings['action']} {member}. Bot may lack permissions.")
            await self._log_action(
                member,
                "Action Failed",
                f"Failed to {settings['action']} **{member.display_name}** (`{member.id}`).\n"
                "Please ensure the bot has `Ban Members` or `Kick Members` permissions and that its role is higher than the member's.",
                discord.Color.red()
            )

    async def _log_action(self, member: discord.Member, title: str, description: str, color: discord.Color):
        log_channel_id = await self.config.guild(member.guild).log_channel()
        if not log_channel_id:
            return
        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            log.warning(f"Log channel {log_channel_id} not found in guild {member.guild.id}")
            return
        embed = discord.Embed(
            title=f"No PFP > {title}",
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"User Join")
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            log.warning(f"Failed to send log message to channel {log_channel.name} in guild {member.guild.name}.")

    @commands.group(name="nopfpban", aliases=["nopfp"], invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def nopfpban(self, ctx: commands.Context):
        """
        Manage settings for banning users with no profile picture.
        """
            await ctx.send_help()

    @nopfpban.command(name="toggle")
    async def nopfpban_toggle(self, ctx: commands.Context, true_or_false: bool):
        """Enable or disable the NoPfpBan feature."""
        await self.config.guild(ctx.guild).enabled.set(true_or_false)
        status = "enabled" if true_or_false else "disabled"
        await ctx.send(f"NoPfpBan has been {status} in this guild.")

    @nopfpban.command(name="reason")
    async def nopfpban_reason(self, ctx: commands.Context, *, reason: str):
        """Set the reason for the automatic action."""
        await self.config.guild(ctx.guild).reason.set(reason)
        await ctx.send(f"Autoban reason set to: `{reason}`")

    @nopfpban.command(name="action")
    async def nopfpban_action(self, ctx: commands.Context, action: str):
        """
        Set the action to either `ban` or `kick`.
        """
        action = action.lower()
        if action not in ["ban", "kick"]:
            return await ctx.send("Action must be either `ban` or `kick`.")
        await self.config.guild(ctx.guild).action.set(action)
        await ctx.send(f"Autoban action set to `{action}`.")

    @nopfpban.command(name="logchannel")
    async def nopfpban_logchannel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """
        Set the channel for logging actions.
        
        Omit the channel to disable logging.
        """
        channel_id = channel.id if channel else None
        await self.config.guild(ctx.guild).log_channel.set(channel_id)
        if channel:
            await ctx.send(f"Log channel set to {channel.mention}.")
        else:
            await ctx.send("Log channel has been disabled.")

    @nopfpban.command(name="settings", aliases=["status"])
    async def nopfpban_settings(self, ctx: commands.Context):
        """Check the current settings for NoPfpBan."""
        settings = await self.config.guild(ctx.guild).all()
        status = "Enabled" if settings["enabled"] else "Disabled"
        log_channel = self.bot.get_channel(settings["log_channel"])
        log_status = log_channel.mention if log_channel else "Not Set"

        embed = discord.Embed(
            title=f"NoPfpBan Settings for {ctx.guild.name}",
            color=await ctx.embed_color()
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Action", value=settings["action"].capitalize(), inline=True)
        embed.add_field(name="Log Channel", value=log_status, inline=True)
        embed.add_field(name="Reason", value=f"```{settings['reason']}```", inline=False)
        await ctx.send(embed=embed)
