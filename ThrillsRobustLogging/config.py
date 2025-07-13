from redbot.core import Config

# This dictionary defines the default settings for a guild.
DEFAULT_GUILD_SETTINGS = {
    "log_channels": {
        "default": None,
        "messages": None,
        "members": None,
        "moderation": None,
        "server": None,
        "roles": None,
        "channels": None,
        "voice": None,
        "events": None,
        "automod": None,
        "raw_audit": None,
    },
    # A complete set of toggles for every type of event.
    "log_toggles": {
        "messages": {
            "delete": True,
            "edit": True,
            "purge": True,
        },
        "members": {
            "join": True,
            "leave": True,
            "nick_change": True,
            "role_change": True,
            "avatar_change": True,
        },
        "moderation": {
            "ban": True,
            "unban": True,
            "kick": True,
            "timeout_add": True,
            "timeout_remove": True,
        },
        "roles": {
            "create": True,
            "delete": True,
            "update": True,
        },
        "channels": {
            "create": True,
            "delete": True,
            "update": True,
            "thread_create": True,
            "thread_delete": True,
            "thread_update": True,
        },
        "voice": {
            "join": True,
            "leave": True,
            "move": True,
            "mute": True,
            "deafen": True,
        },
        "server": {
            "update": True,
            "webhook_create": True,
            "webhook_delete": True,
            "webhook_update": True,
            "emoji_create": True,
            "emoji_delete": True,
            "emoji_update": True,
            "sticker_create": True,
            "sticker_delete": True,
            "sticker_update": True,
            "invite_create": True,
            "invite_delete": True,
        },
        "events": {
            "scheduled_event_create": True,
            "scheduled_event_delete": True,
            "scheduled_event_update": True,
            "stage_start": True,
            "stage_end": True,
        },
        "automod": {
            "trigger": True,
        },
        "raw_audit": {
            "enable": False, 
        }
    }
}

class TRLConfig:
    def __init__(self):
        self.config = Config.get_conf(
            self,
            identifier=166046424262, 
            force_registration=True,
        )
        self.config.register_guild(**DEFAULT_GUILD_SETTINGS)

    # --- Channel Management ---
    async def get_log_channels(self, guild):
        return await self.config.guild(guild).log_channels()

    async def set_log_channel(self, guild, category, channel_id):
        async with self.config.guild(guild).log_channels() as channels:
            channels[category] = channel_id

    # --- Toggle Management ---
    async def get_all_toggles(self, guild):
        return await self.config.guild(guild).log_toggles()

    async def get_toggle(self, guild, category, setting):
        toggles = await self.get_all_toggles(guild)
        return toggles.get(category, {}).get(setting, False)

    async def set_toggle(self, guild, category, setting, value):
        async with self.config.guild(guild).log_toggles() as toggles:
            if category not in toggles:
                toggles[category] = {}
            toggles[category][setting] = value