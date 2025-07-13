import discord
from redbot.core import commands
from redbot.core.bot import Red
from typing import TYPE_CHECKING, List, Optional
import asyncio
from collections import deque, defaultdict
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
        self.processed_log_ids = deque(maxlen=50)
        self.webhook_cache = defaultdict(dict)

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(10)
        for guild in self.bot.guilds:
            await self._update_webhook_cache(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self._update_webhook_cache(guild)

    async def _update_webhook_cache(self, guild: discord.Guild):
        try:
            webhooks = await guild.webhooks()
            self.webhook_cache[guild.id] = {
                wh.id: {
                    "name": wh.name,
                    "channel_id": wh.channel_id,
                    "type": wh.type.name.upper()
                }
                for wh in webhooks
            }
        except (discord.Forbidden, discord.HTTPException):
            self.webhook_cache[guild.id] = {}

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        if not self.cog:
            return
        await asyncio.sleep(1.5)
        guild = channel.guild

        try:
            async for entry in guild.audit_logs(limit=5):
                if entry.id in self.processed_log_ids:
                    continue

                if entry.action in (
                    discord.AuditLogAction.webhook_create,
                    discord.AuditLogAction.webhook_update
                ):
                    webhook = entry.target
                    if not hasattr(webhook, "channel_id") or webhook.channel_id != channel.id:
                        continue

                    self.processed_log_ids.append(entry.id)
                    moderator = entry.user

                    if entry.action == discord.AuditLogAction.webhook_create:
                        wh_type = getattr(webhook.type, "name", "UNKNOWN").upper()
                        embed = await logembeds.webhook_created(webhook, moderator, webhook.channel, wh_type)
                        await self.cog._send_log(guild, embed, "server", "webhook_create")
                    else:
                        changes = [
                            f"**{change[0].replace('_', ' ').title()}** updated."
                            for change in entry.changes.after
                        ]
                        embed = await logembeds.webhook_updated(webhook, moderator, changes)
                        await self.cog._send_log(guild, embed, "server", "webhook_update")
                    break
        except Exception:
            pass

        await self._update_webhook_cache(guild)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        if (
            entry.action != discord.AuditLogAction.webhook_delete
            or not self.cog
            or entry.id in self.processed_log_ids
        ):
            return

        self.processed_log_ids.append(entry.id)
        guild = entry.guild
        moderator = entry.user
        webhook_id = getattr(entry.target, 'id', None)

        cached = self.webhook_cache.get(guild.id, {}).pop(webhook_id, None)
        name = getattr(entry.target, "name", None) or (cached.get("name") if cached else "Unknown Webhook")

        channel = getattr(entry.extra, "channel", None)
        if not channel and cached:
            channel_id = cached.get("channel_id")
            channel = guild.get_channel(channel_id) if channel_id else None

        if channel:
            embed = await logembeds.webhook_deleted(None, moderator, channel, name=name)
            await self.cog._send_log(guild, embed, "server", "webhook_delete")

        await self._update_webhook_cache(guild)

    # --- Other Server Event Listeners ---
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
