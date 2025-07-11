import discord
from redbot.core.bot import Red

from .. import logembeds

class MemberListeners:
    """
    Contains all listeners related to member events.
    """

    def __init__(self, bot: Red, cog):
        self.bot = bot
        self.cog = cog

    async def on_member_join(self, member: discord.Member):
        if not member.guild:
            return

        embed = await logembeds.member_joined(member)
        # Use the main cog's helper to send the log
        await self.cog._send_log(member.guild, embed, "members")

    async def on_member_remove(self, member: discord.Member):
        if not member.guild:
            return

        embed = await logembeds.member_left(member)
        await self.cog._send_log(member.guild, embed, "members")

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot:
            return

        # Check for nickname change
        if before.nick != after.nick:
            pass

        # Check for role changes
        if before.roles != after.roles:
            pass

        # Check for avatar change
        if before.display_avatar != after.display_avatar:
            pass 