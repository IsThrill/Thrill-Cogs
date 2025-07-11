import discord
from redbot.core.bot import Red

from .. import logembeds

class RoleListeners:
    """
    Contains all listeners related to role events.
    """
    def __init__(self, bot: Red, cog):
        self.bot = bot
        self.cog = cog

    async def on_guild_role_create(self, role: discord.Role):
        pass

    async def on_guild_role_delete(self, role: discord.Role):
        pass

    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        pass