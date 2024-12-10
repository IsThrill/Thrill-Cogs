import datetime
import discord
from redbot.core import Config, commands, i18n

_ = i18n.Translator("ThrillsLogs", __file__)

class ThrillsLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)

        # Register default configuration
        self.config.register_guild(
            voice_logging_channel=None
        )

    async def get_log_channel(self, guild):
        """Fetch the designated log channel."""
        log_channel_id = await self.config.guild(guild).voice_logging_channel()
        if log_channel_id:
            return guild.get_channel(log_channel_id)
        return None

    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        log_channel = await self.get_log_channel(guild)

        if not log_channel:
            return  # No logging channel configured

        time = datetime.datetime.utcnow()

        embed = discord.Embed(
            title="Joined/Left/Switched Channel",
            timestamp=time,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)  # Set user's avatar as thumbnail

        description = ""

        # When a user joins a voice channel
        if before.channel is None and after.channel:
            description = f"**{member.mention} joined** {after.channel.mention}"
            embed.add_field(name="Channel Joined", value=after.channel.name, inline=True)

            # List members currently present in the channel
            members_list = [m.mention for m in after.channel.members]
            if members_list:
                embed.add_field(name="Current Members", value=", ".join(members_list), inline=False)

        # When a user leaves a voice channel
        elif after.channel is None and before.channel:
            description = f"**{member.mention} left** {before.channel.mention}"
            embed.add_field(name="Channel Left", value=before.channel.name, inline=True)

            members_list = [m.mention for m in before.channel.members]
            if members_list:
                embed.add_field(name="Current Members", value=", ".join(members_list), inline=False)

        # When a user switches channels
        elif before.channel != after.channel:
            description = f"🔄 **{member.mention} switched channels**\nFrom **{before.channel.mention}** to **{after.channel.mention}**"
            embed.add_field(name="From Channel", value=before.channel.name, inline=True)

            members_list_before = [m.mention for m in before.channel.members]
            if members_list_before:
                embed.add_field(name="Members in From Channel", value=", ".join(members_list_before), inline=False)

            members_list_after = [m.mention for m in after.channel.members]
            if members_list_after:
                embed.add_field(name="Members in To Channel", value=", ".join(members_list_after), inline=False)

        if not description:
            return

        embed.description = description

        try:
            # Fetch the most recent audit log entry to verify the action
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=1):
                    if entry.action == discord.AuditLogAction.member_update and entry.target.id == member.id:
                        embed.add_field(name="Updated By", value=entry.user.mention, inline=True)
                        if entry.reason:
                            embed.add_field(name="Reason", value=entry.reason, inline=False)

        except discord.Forbidden:
            print(f"Permission denied to view audit logs in {guild.name}")

        try:
            # Send the embed message to the designated log channel
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Permission denied to send messages to {log_channel}")

    # Main command group for ThrillsLogs
    @commands.group(name="thrillslogs", aliases=["ThrillsLogs"], invoke_without_command=True)
    async def thrillslogs(self, ctx):
        """List available subcommands for ThrillsLogs."""
        commands_list = {
            "thrillslogs set": "Set the channel where voice logging will be enabled.",
            "thrillslogs check": "Check the currently configured voice logging channel.",
            "thrillslogs clear": "Reset the voice logging channel configuration."
        }

        embed = discord.Embed(
            title="ThrillsLogs Subcommands",
            description="Here are the available subcommands:",
            color=discord.Color.green()
        )

        for command, description in commands_list.items():
            embed.add_field(name=f"`{command}`", value=description, inline=False)

        await ctx.send(embed=embed)

    @thrillslogs.command(name="set")
    async def set_voice_channel(self, ctx, channel: discord.TextChannel):
        """Configure the channel where voice activity will be logged."""
        await self.config.guild(ctx.guild).voice_logging_channel.set(channel.id)
        await ctx.send(f"✅ Voice logging channel has been set to {channel.mention}")

    @thrillslogs.command(name="check")
    async def check_voice_channel(self, ctx):
        log_channel_id = await self.config.guild(ctx.guild).voice_logging_channel()

        if log_channel_id:
            log_channel = ctx.guild.get_channel(log_channel_id)
            if log_channel:
                await ctx.send(f"✅ The voice logging channel is {log_channel.mention}")
                return

        await ctx.send("❌ No voice logging channel has been set.")

    @thrillslogs.command(name="clear")
    async def clear_voice_channel(self, ctx):
        """Remove the voice logging channel configuration."""
        await self.config.guild(ctx.guild).voice_logging_channel.clear()
        await ctx.send("✅ Voice logging channel has been reset.")

    async def cog_load(self):
        self.bot.add_listener(self.on_voice_state_update, "on_voice_state_update")
