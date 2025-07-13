from .core import ThrillsRobustLogging

from .listeners.automod import AutoModListeners
from .listeners.channels import ChannelListeners
from .listeners.events import EventListeners
from .listeners.members import MemberListeners
from .listeners.messages import MessageListeners
from .listeners.moderation import ModerationListeners
from .listeners.roles import RoleListeners
from .listeners.server import ServerListeners
from .listeners.voice import VoiceListeners

async def setup(bot):
    main_cog = ThrillsRobustLogging(bot)
    await bot.add_cog(main_cog)

    listener_cogs = [
        AutoModListeners,
        ChannelListeners,
        EventListeners,
        MemberListeners,
        MessageListeners,
        ModerationListeners,
        RoleListeners,
        ServerListeners,
        VoiceListeners,
    ]

    for cog_class in listener_cogs:
        listener_cog = cog_class(bot)
        listener_cog.cog = main_cog
        await bot.add_cog(listener_cog)