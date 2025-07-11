import discord
from redbot.core.bot import Red

from .. import logembeds

class ModerationListeners:
    """
    Contains all listeners related to core moderation events.
    """
    def __init__(self, bot: Red, cog):
        self.bot = bot
        self.cog = cog

    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        # Handles member bans.
        pass

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        # Handles member unbans.
        pass