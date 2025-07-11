import discord
from redbot.core.bot import Red

from .. import logembeds

class ChannelListeners:
    """
    Contains all listeners related to channel, category, and thread events.
    """
    def __init__(self, bot: Red, cog):
        self.bot = bot
        self.cog = cog

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        pass

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        pass

    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        pass

    async def on_thread_create(self, thread: discord.Thread):
        pass