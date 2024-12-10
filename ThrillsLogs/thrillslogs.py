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
            timestamp=time,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # When a user joins a voice channel
        if before.channel is None and after.channel:
            embed.title = "Member Joined Channel"
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="Channel Joined", value=f"{after.channel.mention}", inline=False)

            members_list = sorted(after.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)
            member_mentions = [m.mention for m in members_list]

            if member_mentions:
                embed.add_field(name="Members In Channel", value="\n".join(member_mentions), inline=False)

        # When a user leaves a voice channel
        elif after.channel is None and before.channel:
            embed.title = "Member Left Channel"
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="Channel Left", value=f"{before.channel.mention}", inline=False)

            members_list = sorted(before.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)
            member_mentions = [m.mention for m in members_list]

            if member_mentions:
                embed.add_field(name="Members In Channel", value="\n".join(member_mentions), inline=False)

        # When a user switches channels
        elif before.channel != after.channel:
            embed.title = "Member Switched Channels"
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="From Channel", value=f"{before.channel.mention}", inline=True)
            embed.add_field(name="To Channel", value=f"{after.channel.mention}", inline=True)

            members_list_before = sorted(before.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)
            members_list_after = sorted(after.channel.members, key=lambda m: m.joined_at or datetime.datetime.min)

            members_in_from_channel = "\n".join([m.mention for m in members_list_before]) if members_list_before else "None"
            members_in_to_channel = "\n".join([m.mention for m in members_list_after]) if members_list_after else "None"

            embed.add_field(name="Members In From Channel", value=members_in_from_channel, inline=False)
            embed.add_field(name="Members In To Channel", value=members_in_to_channel, inline=False)

        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=1):
                    if entry.action == discord.AuditLogAction.member_update and entry.target.id == member.id:
                        embed.add_field(name="Updated By", value=entry.user.mention, inline=True)
                        if entry.reason:
                            embed.add_field(name="Reason", value=entry.reason, inline=False)

        except discord.Forbidden:
            print(f"Permission denied to view audit logs in {guild.name}")

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Permission denied to send messages to {log_channel}")

    async def cog_load(self):
        self.bot.add_listener(self.on_voice_state_update, "on_voice_state_update")

    @commands.group(name="thrillslogs", aliases=["ThrillsLogs"], invoke_without_command=True)
    async def thrillslogs(self, ctx):
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
        await self.config.guild(ctx.guild).voice_logging_channel.clear()
        await ctx.send("✅ Voice logging channel has been reset.")
