import discord
import logging

from redbot.core import commands, Config

log = logging.getLogger("red.isthrill.nopfpban")


class NoPfpBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2706371337)
        default_guild_settings = {"autoban_enabled": False, "autoban_reason": "Automated ban: No profile picture"}
        self.config.register_guild(**default_guild_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.Cog.listener()
    async def on_member_join(self, member):
        autoban_enabled = await self.config.guild(member.guild).autoban_enabled()
        autoban_reason = await self.config.guild(member.guild).autoban_reason()
        if autoban_enabled and not member.avatar:
            try:
                await member.send(f"You have been automatically banned from {member.guild.name} due to not having a profile picture.\nReason: {autoban_reason}")
                await member.ban(reason=autoban_reason)
            except discord.Forbidden:
                log.info(f"NoPfpBan cog does not have permissions to ban in guild {member.guild.id}")
                await self.kick_user(member, autoban_reason)

    async def kick_user(self, member, reason):
        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            log.info(f"NoPfpBan cog does not have permissions to kick in guild {member.guild.id}")
            fail_channel_id = await self.config.guild(member.guild).fail_channel()
            fail_channel = self.bot.get_channel(fail_channel_id)
            if fail_channel:
                await fail_channel.send(f"Failed to kick user {member.name} ({member.id}) due to missing permissions.")
            else:
                log.warning(f"Fail channel not configured for guild {member.guild.id}")
            return

        # Logging the failure to kick
        fail_channel_id = await self.config.guild(member.guild).fail_channel()
        fail_channel = self.bot.get_channel(fail_channel_id)
        if fail_channel:
            await fail_channel.send(f"Failed to DM the user {member.name} ({member.id}) due to there privacy settings.")
        else:
            log.warning(f"Fail channel not configured for guild {member.guild.id}")

    @commands.group()
    async def autoban(self, ctx):
        """Manage autoban settings."""
        pass

    @autoban.command()
    async def enable(self, ctx):
        """Enable autoban in this guild for users with no profile picture."""
        await self.config.guild(ctx.guild).autoban_enabled.set(True)
        await ctx.send("Autoban enabled in this guild.")

    @autoban.command()
    async def disable(self, ctx):
        """Disable autoban in this guild for users with no profile picture."""
        await self.config.guild(ctx.guild).autoban_enabled.set(False)
        await ctx.send("Autoban disabled in this guild.")

    @autoban.command()
    async def reason(self, ctx, *, reason: str):
        """
        Set the automatic ban reason, for this guild.
        It will show in the audit log as the reason for removing the user.
        """
        await self.config.guild(ctx.guild).autoban_reason.set(reason)
        await ctx.send(f"Autoban audit log reason set to: `{reason}`")

    @autoban.command()
    async def status(self, ctx):
        """Check the status of autoban."""
        autoban_enabled = await self.config.guild(ctx.guild).autoban_enabled()
        await ctx.send(f"Autoban is {'enabled' if autoban_enabled else 'disabled'} in this guild.")

    @autoban.command()
    @commands.has_permissions(administrator=True)
    async def setfailchannel(self, ctx, channel: discord.TextChannel):
        """
        Set the channel to log failed DMs for autoban.
        Example: [p]autoban setfailchannel #logs
        """
        await self.config.guild(ctx.guild).fail_channel.set(channel.id)
        await ctx.send(f"Fail channel set to: {channel.mention}")

    @autoban.command()
    @commands.has_permissions(administrator=True)
    async def toggleaction(self, ctx):
        """
        Toggle between kicking and banning users.
        """
        current_action = await self.config.guild(ctx.guild).autoban_action()
        new_action = "ban" if current_action == "kick" else "kick"
        await self.config.guild(ctx.guild).autoban_action.set(new_action)
        await ctx.send(f"Autoban action set to: {new_action}")


