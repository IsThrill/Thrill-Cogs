import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, List, Optional
import asyncio
from .. import logembeds

if TYPE_CHECKING:
    from ..core import ThrillsRobustLogging

class ServerListeners(commands.Cog):
    """
    Handles listeners for server-wide updates (settings, webhooks, emojis, etc.).
    """
    def __init__(self, bot: Red):
        self.bot = bot
        self.cog: "ThrillsRobustLogging" = None
        self.webhook_cache = {}

    # --- Webhook Cache Management ---
    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(10)
        for guild in self.bot.guilds:
            await self._cache_webhooks(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self._cache_webhooks(guild)

    async def _cache_webhooks(self, guild: discord.Guild):
        try:
            self.webhook_cache[guild.id] = await guild.webhooks()
        except (discord.Forbidden, discord.HTTPException):
            self.webhook_cache[guild.id] = []

    # --- Main Listeners ---

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel | discord.VoiceChannel):
        """Logs creation, deletion, or updates of webhooks using state caching."""
        if not self.cog: return
        guild = channel.guild
        await asyncio.sleep(1.2) 

        before_hooks = self.webhook_cache.get(guild.id, [])
        after_hooks = await guild.webhooks()

        before_map = {wh.id: wh for wh in before_hooks}
        after_map = {wh.id: wh for wh in after_hooks}

        # --- Deletion Check ---
        deleted_ids = before_map.keys() - after_map.keys()
        for webhook_id in deleted_ids:
            deleted_webhook_data = before_map[webhook_id]
            moderator = "Unknown"
            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.webhook_delete):
                    if hasattr(entry.before, "id") and entry.before.id == webhook_id:
                        moderator = entry.user
                        break
            except (discord.Forbidden, AttributeError): pass
            embed = await logembeds.webhook_deleted(deleted_webhook_data, moderator, channel)
            await self.cog._send_log(guild, embed, "server", "webhook_delete")

        # --- Creation Check ---
        created_ids = after_map.keys() - before_map.keys()
        for webhook_id in created_ids:
            created_webhook = after_map[webhook_id]
            entry = await self.cog._get_audit_log_entry(guild, created_webhook, discord.AuditLogAction.webhook_create)
            moderator = entry.user if entry else "Unknown"
            embed = await logembeds.webhook_created(created_webhook, moderator, channel)
            await self.cog._send_log(guild, embed, "server", "webhook_create")
            
        # --- Update Check ---
        for webhook_id in before_map.keys() & after_map.keys():
            before_hook = before_map[webhook_id]
            after_hook = after_map[webhook_id]
            if before_hook.name != after_hook.name or before_hook.channel_id != after_hook.channel_id:
                changes = []
                if before_hook.name != after_hook.name:
                    changes.append(f"**Name:** `{before_hook.name}` → `{after_hook.name}`")
                if before_hook.channel_id != after_hook.channel_id:
                    changes.append(f"**Channel:** {before_hook.channel.mention} → {after_hook.channel.mention}")
                
                entry = await self.cog._get_audit_log_entry(guild, after_hook, discord.AuditLogAction.webhook_update)
                moderator = entry.user if entry else "Unknown"
                embed = await logembeds.webhook_updated(after_hook, moderator, channel, changes)
                await self.cog._send_log(guild, embed, "server", "webhook_update")

        # Finally, update the cache
        self.webhook_cache[guild.id] = after_hooks


    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if not self.cog: return
        changes: List[str] = []
        if before.name != after.name: changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.icon and after.icon and before.icon.key != after.icon.key: changes.append(f"**Icon:** [Before]({before.icon.url}) → [After]({after.icon.url})")
        if before.verification_level != after.verification_level: changes.append(f"**Verification Level:** `{before.verification_level}` → `{after.verification_level}`")
        if before.description != after.description: changes.append(f"**Description:** Changed from `{before.description}` to `{after.description}`")
        if changes:
            moderator = "Unknown"
            try:
                async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
                    if entry.target == after: moderator = entry.user; break
            except discord.Forbidden: pass
            embed = await logembeds.server_updated(after, moderator, changes)
            await self.cog._send_log(after, embed, "server", "update")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if not self.cog or not invite.guild: return
        embed = await logembeds.invite_created(invite)
        await self.cog._send_log(invite.guild, embed, "server", "invite_create")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if not self.cog or not invite.guild: return
        embed = await logembeds.invite_deleted(invite)
        await self.cog._send_log(invite.guild, embed, "server", "invite_delete")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: List[discord.Emoji], after: List[discord.Emoji]):
        if not self.cog: return
        before_map = {e.id: e for e in before}
        after_map = {e.id: e for e in after}
        for emoji_id in after_map.keys() - before_map.keys():
            emoji = after_map[emoji_id]
            entry = await self.cog._get_audit_log_entry(guild, emoji, discord.AuditLogAction.emoji_create)
            moderator = entry.user if entry else "Unknown Moderator"
            embed = await logembeds.emoji_created(emoji, moderator)
            await self.cog._send_log(guild, embed, "server", "emoji_create")
        for emoji_id in before_map.keys() - after_map.keys():
            emoji = before_map[emoji_id]
            entry = await self.cog._get_audit_log_entry(guild, emoji, discord.AuditLogAction.emoji_delete)
            moderator = entry.user if entry else "Unknown Moderator"
            embed = await logembeds.emoji_deleted(emoji, moderator)
            await self.cog._send_log(guild, embed, "server", "emoji_delete")
        for emoji_id in before_map.keys() & after_map.keys():
            if before_map[emoji_id].name != after_map[emoji_id].name:
                before_emoji = before_map[emoji_id]
                after_emoji = after_map[emoji_id]
                entry = await self.cog._get_audit_log_entry(guild, after_emoji, discord.AuditLogAction.emoji_update)
                moderator = entry.user if entry else "Unknown Moderator"
                embed = await logembeds.emoji_renamed(before_emoji, after_emoji, moderator)
                await self.cog._send_log(guild, embed, "server", "emoji_update")

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild: discord.Guild, before: List[discord.GuildSticker], after: List[discord.GuildSticker]):
        if not self.cog: return
        before_map = {s.id: s for s in before}
        after_map = {s.id: s for s in after}
        for sticker_id in after_map.keys() - before_map.keys():
            sticker = after_map[sticker_id]
            entry = await self.cog._get_audit_log_entry(guild, sticker, discord.AuditLogAction.sticker_create)
            moderator = entry.user if entry else "Unknown Moderator"
            embed = await logembeds.sticker_created(sticker, moderator)
            await self.cog._send_log(guild, embed, "server", "sticker_create")
        for sticker_id in before_map.keys() - after_map.keys():
            sticker = before_map[sticker_id]
            entry = await self.cog._get_audit_log_entry(guild, sticker, discord.AuditLogAction.sticker_delete)
            moderator = entry.user if entry else "Unknown Moderator"
            embed = await logembeds.sticker_deleted(sticker, moderator)
            await self.cog._send_log(guild, embed, "server", "sticker_delete")
        for sticker_id in before_map.keys() & after_map.keys():
            if before_map[sticker_id].name != after_map[sticker_id].name or before_map[sticker_id].description != after_map[sticker_id].description:
                before_sticker = before_map[sticker_id]
                after_sticker = after_map[sticker_id]
                entry = await self.cog._get_audit_log_entry(guild, after_sticker, discord.AuditLogAction.sticker_update)
                moderator = entry.user if entry else "Unknown Moderator"
                embed = await logembeds.sticker_updated(before_sticker, after_sticker, moderator)
                await self.cog._send_log(guild, embed, "server", "sticker_update")
