import datetime
import discord
import logging
from redbot.core import Config, commands, i18n

_ = i18n.Translator("ThrillsLogs", __file__)

# Set up logging
logging.basicConfig(level=logging.INFO)

class ThrillsLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)

        # Register default configuration
        self.config.register_guild(
            voiceLoggingChannel=None
        )

    async def getLogChannel(self, guild):
        """Fetch the designated log channel."""
        log_channel_id = await self.config.guild(guild).voiceLoggingChannel()
        if log_channel_id:
            return guild.get_channel(log_channel_id)
        return None

    def createEmbedLogActivity(self, title, member, channel=None):
        """Helper method to create embed logs."""
        embed = discord.Embed(
            title=title,
            timestamp=datetime.datetime.utcnow(),
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if channel:
            embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)
        return embed

    async def getAuditLogEntry(self, guild, member):
        """Fetch audit log information about member updates."""
        async for entry in guild.audit_logs(limit=10):
            if entry.action == discord.AuditLogAction.member_update and entry.target.id == member.id:
                return entry.user.mention, entry.reason
        return "Unknown", None

    async def onVoiceStateUpdate(self, member, before, after):
        guild = member.guild
        log_channel = await self.getLogChannel(guild)

        if not log_channel:
            return  # No logging channel configured

        embed = None

        # When a user joins a voice channel
        if before.channel is None and after.channel:
            embed = self.createEmbedLogActivity("User Joined Channel", member, after.channel)

            members_list = sorted(after.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)
            member_mentions = [m.mention for m in members_list]

            if member_mentions:
                embed.add_field(name="Members In Channel", value="\n".join(member_mentions), inline=False)

        # When a user leaves a voice channel
        elif after.channel is None and before.channel:
            embed = self.createEmbedLogActivity("User Left Channel", member, before.channel)

            members_list = sorted(before.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)
            member_mentions = [m.mention for m in members_list]

            if member_mentions:
                embed.add_field(name="Members In Channel", value="\n".join(member_mentions), inline=False)

        # When a user switches channels
        elif before.channel != after.channel:
            embed = self.createEmbedLogActivity("User Switched Channels", member, after.channel)
            embed.add_field(name="From Channel", value=f"{before.channel.mention}", inline=True)
            embed.add_field(name="To Channel", value=f"{after.channel.mention}", inline=True)

            members_list_before = sorted(before.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)
            members_list_after = sorted(after.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)

            embed.add_field(name="Members In From Channel", value="\n".join([m.mention for m in members_list_before]), inline=False)
            embed.add_field(name="Members In To Channel", value="\n".join([m.mention for m in members_list_after]), inline=False)

        try:
            if guild.me.guild_permissions.view_audit_log:
                audit_user, reason = await self.getAuditLogEntry(guild, member)
                embed.add_field(name="Updated By", value=audit_user, inline=True)
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)

        except discord.Forbidden:
            logging.error(f"Permission denied to view audit logs in {guild.name}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            logging.error(f"Permission denied to send messages to {log_channel}")

    async def cogLoad(self):
        self.bot.add_listener(self.onVoiceStateUpdate, "on_voice_state_update")

    @commands.group(name="thrillslogs", aliases=["ThrillsLogs"], invoke_without_command=True)
    async def thrillsLogs(self, ctx):
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

    @thrillsLogs.command(name="set")
    async def setVoiceChannel(self, ctx, channel: discord.TextChannel):
        await self.config.guild(ctx.guild).voiceLoggingChannel.set(channel.id)
        await ctx.send(f"✅ Voice logging channel has been set to {channel.mention}")

    @thrillsLogs.command(name="check")
    async def checkVoiceChannel(self, ctx):
        log_channel_id = await self.config.guild(ctx.guild).voiceLoggingChannel()

        if log_channel_id:
            log_channel = ctx.guild.get_channel(log_channel_id)
            if log_channel:
                await ctx.send(f"✅ The voice logging channel is {log_channel.mention}")
                return

        await ctx.send("❌ No voice logging channel has been set.")

    @thrillsLogs.command(name="clear")
    async def clearVoiceChannel(self, ctx):
        await self.config.guild(ctx.guild).voiceLoggingChannel.clear()
        await ctx.send("✅ Voice logging channel has been reset.")
