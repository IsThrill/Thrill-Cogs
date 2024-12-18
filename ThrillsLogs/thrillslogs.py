import datetime
import discord
import pytz
from redbot.core import Config, commands, i18n

_ = i18n.Translator("ThrillsLogs", __file__)

class ThrillsLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789)
        self.config.register_guild(voice_logging_channel=None)
        self.bot.add_listener(self.on_voice_state_update, "on_voice_state_update")

    async def get_log_channel(self, guild):
        """Fetch the designated log channel."""
        log_channel_id = await self.config.guild(guild).voice_logging_channel()
        return guild.get_channel(log_channel_id) if log_channel_id else None

    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        log_channel = await self.get_log_channel(guild)

        if not log_channel or not log_channel.permissions_for(guild.me).send_messages:
            return  # No logging channel or bot lacks permissions

        # Get the current timestamp in EST timezone
        est = pytz.timezone('America/New_York')
        current_time = datetime.datetime.now(est)

        embed = discord.Embed(timestamp=current_time)

        avatar_url = member.display_avatar.url if member.display_avatar else None
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        change_type = None

        # User joins a voice channel
        if before.channel is None and after.channel:
            embed.title = "Member Joined Voice Channel"
            embed.color = discord.Color.green()
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="Channel", value=f"{after.channel.mention}", inline=False)

            # List members in the joined channel
            members_list = "\n".join([m.mention for m in after.channel.members]) or "None"
            embed.add_field(name="Members in Channel", value=members_list, inline=False)
            change_type = "join"

        # User leaves a voice channel
        elif after.channel is None and before.channel:
            embed.title = "Member Left Voice Channel"
            embed.color = discord.Color.red()
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="Channel", value=f"{before.channel.mention}", inline=False)

            # List remaining members in the left channel
            members_list = "\n".join([m.mention for m in before.channel.members]) or "None"
            embed.add_field(name="Members in Channel", value=members_list, inline=False)
            change_type = "leave"

        # User switches voice channels
        elif before.channel != after.channel:
            embed.title = "Member Switched Channels"
            embed.color = discord.Color.blue()
            embed.add_field(name="User", value=f"{member.mention}", inline=False)
            embed.add_field(name="From Channel", value=f"{before.channel.mention}", inline=True)
            embed.add_field(name="To Channel", value=f"{after.channel.mention}", inline=True)

            # List members in both channels
            before_members = "\n".join([m.mention for m in before.channel.members]) or "None"
            after_members = "\n".join([m.mention for m in after.channel.members]) or "None"
            embed.add_field(name="Members in Previous Channel", value=before_members, inline=False)
            embed.add_field(name="Members in New Channel", value=after_members, inline=False)
            change_type = "switch"

        # Send the log if there is a change
        if change_type:
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                print(f"[ERROR] Permission denied to send messages to {log_channel}")
            except discord.HTTPException as e:
                print(f"[ERROR] Failed to send embed: {e}")

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
