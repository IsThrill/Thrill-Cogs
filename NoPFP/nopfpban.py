import discord
import logging

from redbot.core import commands, Config

log = logging.getLogger("red.aikaterna.nopfpban")


class NoPfpBan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2706371337)
        default_guild_settings = {"autoban_enabled": False, "autoban_reason": "Automated ban: No profile picture", "ban_mode": True}
        self.config.register_guild(**default_guild_settings)

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    @commands.Cog.listener()
    async def on_member_join(self, member):
        autoban_enabled = await self.config.guild(member.guild).autoban_enabled()
        autoban_reason = await self.config.guild(member.guild).autoban_reason()
        ban_mode = await self.config.guild(member.guild).ban_mode()
        
        if autoban_enabled and not member.avatar:
            try:
                if ban_mode:
                    await member.send(f"You have been automatically banned from {member.guild.name} due to not having a profile picture.\nReason: {autoban_reason}")
                    await member.ban(reason=autoban_reason)
                else:
                    await member.send(f"You have been automatically kicked from {member.guild.name} due to not having a profile picture.\nReason: {autoban_reason}")
                    await member.kick(reason=autoban_reason)
            except discord.Forbidden:
                log.info(f"NoPfpBan cog does not have permissions to {'ban' if ban_mode else 'kick'} in guild {member.guild.id}")
                fail_channel_id = await self.config.guild(member.guild).fail_channel()
                fail_channel = self.bot.get_channel(fail_channel_id)
                if fail_channel:
                    await fail_channel.send(f"Failed to DM and {'ban' if ban_mode else 'kick'} user {member.name} ({member.id}) due to missing permissions.")
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
        Set the automatic ban/kick reason, for this guild.
        It will show in the audit log as the reason for removing the user.
        """
        await self.config.guild(ctx.guild).autoban_reason.set(reason)
        await ctx.send(f"Autoban audit log reason set to: `{reason}`")

    @autoban.command()
    async def status(self, ctx):
        """Check the status of autoban."""
        autoban_enabled = await self.config.guild(ctx.guild).autoban_enabled()
        ban_mode = await self.config.guild(ctx.guild).ban_mode()
        await ctx.send(f"Autoban is {'enabled' if autoban_enabled else 'disabled'} in this guild. Current mode: {'Ban' if ban_mode else 'Kick'}")

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
    async def togglebanmode(self, ctx):
        """
        Toggle between banning and kicking users without profile pictures.
        """
        current_mode = await self.config.guild(ctx.guild).ban_mode()
        new_mode = not current_mode
        await self.config.guild(ctx.guild).ban_mode.set(new_mode)
        await ctx.send(f"Autoban mode toggled. Users will now {'be banned' if new_mode else 'be kicked'} if they don't have a profile picture.")
