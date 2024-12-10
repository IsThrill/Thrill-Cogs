import datetime
import discord
from redbot.core import Config, commands, i18n, modlog

_ = i18n.Translator("ThrillsLogs", __file__)

class ThrillsLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def modlogChannel(self, guild):
        """Fetch the designated modlog channel."""
        if guild.id in self.bot.settings and "voice_logging_channel" in self.bot.settings[guild.id]:
            log_channel_id = self.bot.settings[guild.id]["voice_logging_channel"]
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                return log_channel
        return None

    async def onVoiceStateUpdate(self, member, before, after):
        guild = member.guild
        time = datetime.datetime.utcnow()

        log_channel = await self.modlogChannel(guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="Voice State Update",
            timestamp=time,
            color=discord.Color.blue()
        )

        embed.set_author(name=str(member), icon_url=member.display_avatar.url)

        description = ""

        if before.channel is None and after.channel:
            description = f"✅ **{member.mention} joined** {after.channel.mention}"
            embed.add_field(name="Channel Joined", value=after.channel.name, inline=True)
            embed.add_field(name="Max Members", value=after.channel.user_limit or "Unlimited", inline=True)

        elif after.channel is None and before.channel:
            description = f"🔴 **{member.mention} left** {before.channel.mention}"
            embed.add_field(name="Channel Left", value=before.channel.name, inline=True)
            embed.add_field(name="Max Members", value=before.channel.user_limit or "Unlimited", inline=True)

        elif before.channel != after.channel:
            description = (
                f"🔄 **{member.mention} switched channels**\n"
                f"From **{before.channel.mention}** to **{after.channel.mention}**"
            )
            embed.add_field(name="From Channel", value=before.channel.name, inline=True)
            embed.add_field(name="Max Members (From)", value=before.channel.user_limit or "Unlimited", inline=True)
            embed.add_field(name="To Channel", value=after.channel.name, inline=True)
            embed.add_field(name="Max Members (To)", value=after.channel.user_limit or "Unlimited", inline=True)

        if not description:
            return

        embed.description = description

        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=1):
                    if entry.action == discord.AuditLogAction.member_update and entry.target.id == member.id:
                        embed.add_field(name="Updated By", value=entry.user.mention, inline=True)
                        if entry.reason:
                            embed.add_field(name="Reason", value=entry.reason, inline=False)
        except discord.Forbidden:
            pass

        await log_channel.send(embed=embed)

    # Main command group for ThrillsLogs
    async def ThrillsLogs(self, ctx):
        pass

    @commands.group(name="ThrillsLogs", invoke_without_command=True)
    async def thrillsLogs(self, ctx):
        """Main command group for ThrillsLogs."""
        await ctx.send("Use subcommands under `ThrillsLogs` to configure voice logging.")

    @thrillsLogs.command(name="set")
    async def setVoiceChannel(self, ctx, channel: discord.TextChannel):
        """Set the channel where voice activity will be logged."""
        guild_id = ctx.guild.id
        if guild_id not in self.bot.settings:
            self.bot.settings[guild_id] = {}

        self.bot.settings[guild_id]["voice_logging_channel"] = channel.id
        await ctx.send(f"✅ Voice logging channel has been set to {channel.mention}")

    @thrillsLogs.command(name="check")
    async def checkVoiceChannel(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.bot.settings and "voice_logging_channel" in self.bot.settings[guild_id]:
            log_channel_id = self.bot.settings[guild_id]["voice_logging_channel"]
            log_channel = ctx.guild.get_channel(log_channel_id)
            if log_channel:
                await ctx.send(f"✅ The voice logging channel is {log_channel.mention}")
                return

        await ctx.send("❌ No voice logging channel has been set.")

    @thrillsLogs.command(name="clear")
    async def clearVoiceChannel(self, ctx):
        guild_id = ctx.guild.id
        if guild_id in self.bot.settings and "voice_logging_channel" in self.bot.settings[guild_id]:
            del self.bot.settings[guild_id]["voice_logging_channel"]
            await ctx.send("✅ Voice logging channel has been reset.")
        else:
            await ctx.send("❌ No voice logging channel has been configured.")
