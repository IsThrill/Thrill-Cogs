from redbot.core import Config

# This dictionary defines the default settings for a guild.
DEFAULT_GUILD_SETTINGS = {
    "log_channels": {
        "default": None,
        "messages": None,
        "members": None,
        "server": None,
        "voice": None,
        "moderation": None
    },
    # A complete set of toggles for every type of event.
    "log_toggles": {
        "messages": {
            "delete": False,         # Log deleted messages
            "edit": False,           # Log edited messages
            "purge": False,          # Log bulk message deletions (purges)
        },
        "members": {
            "join": False,           # Log when a member joins
            "leave": False,          # Log when a member leaves or is kicked
            "nickname": False,       # Log nickname changes
            "roles": False,          # Log when a member's roles are updated
            "avatar": False,         # Log when a member changes their avatar
        },
        "roles": {
            "create": False,         # Log role creation
            "delete": False,         # Log role deletion
            "update": False,         # Log role permission/name/color changes
        },
        "channels": {
            "create": False,         # Log channel/thread/category creation
            "delete": False,         # Log channel/thread/category deletion
            "update": False,         # Log channel/thread/category updates (name, topic, etc.)
        },
        "voice": {
            "join": False,           # Log when a member joins a voice channel
            "leave": False,          # Log when a member leaves a voice channel
            "move": False,           # Log when a member moves between voice channels
        },
        "server": {
            "update": False,         # Log server-wide changes (name, icon, boost level)
            "emojis": False,         # Log emoji/sticker creation and deletion
            "integrations": False,   # Log when webhooks or bots are added/removed
        },
        "moderation": {
            "ban": False,            # Log when a member is banned
            "unban": False,          # Log when a member is unbanned
            "automod": False,        # Log when Discord's AutoMod takes an action
        },
        "events": {
            "create": False,         # Log creation of a Scheduled Event
            "delete": False,         # Log deletion of a Scheduled Event
            "update": False,         # Log updates to a Scheduled Event
            "user_add": False,       # Log when a user subscribes to a Scheduled Event
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
        """Returns the entire dictionary of log channels for a guild."""
        return await self.config.guild(guild).log_channels()

    async def set_log_channel(self, guild, category, channel_id):
        """Sets a specific category's log channel."""
        async with self.config.guild(guild).log_channels() as channels:
            channels[category] = channel_id

    # --- Toggle Management ---
    async def get_all_toggles(self, guild):
        """Returns the entire dictionary of log toggles."""
        return await self.config.guild(guild).log_toggles()

    async def get_toggle(self, guild, category, setting):
        """Checks if a specific event is enabled for logging."""
        toggles = await self.get_all_toggles(guild)
        return toggles.get(category, {}).get(setting, False)

    async def set_toggle(self, guild, category, setting, value):
        """Enables or disables a specific log event."""
        async with self.config.guild(guild).log_toggles() as toggles:
            if category not in toggles:
                toggles[category] = {}
            toggles[category][setting] = value