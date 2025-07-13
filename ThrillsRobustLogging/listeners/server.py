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

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Logs changes to core server settings."""
        if not self.cog: return
        changes: List[str] = []

        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.icon and after.icon and before.icon.key != after.icon.key:
            changes.append(f"**Icon:** [Before]({before.icon.url}) → [After]({after.icon.url})")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification Level:** `{before.verification_level}` → `{after.verification_level}`")
        if before.description != after.description:
            changes.append(f"**Description:** Changed from `{before.description}` to `{after.description}`")

        if changes:
            moderator = "Unknown"
            try:
                async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
                    if entry.target == after:
                        moderator = entry.user
                        break
            except discord.Forbidden:
                pass

            embed = await logembeds.server_updated(after, moderator, changes)
            await self.cog._send_log(after, embed, "server", "update")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.TextChannel | discord.VoiceChannel):
        """Logs creation, deletion, or updates of webhooks."""
        if not self.cog: return
        guild = channel.guild
        await asyncio.sleep(1.0) 

        try:
            audit_entry = None
            webhook_actions = (
                discord.AuditLogAction.webhook_create,
                discord.AuditLogAction.webhook_delete,
                discord.AuditLogAction.webhook_update,
            )
            
            async for entry in guild.audit_logs(limit=5):
                if entry.action not in webhook_actions:
                    continue

                if hasattr(entry.target, "channel_id") and entry.target.channel_id == channel.id:
                    audit_entry = entry
                    break
                elif hasattr(entry.before, "channel_id") and entry.before.channel_id == channel.id:
                    audit_entry = entry
                    break

            if not audit_entry:
                return

            moderator = audit_entry.user
            
            if audit_entry.action == discord.AuditLogAction.webhook_create:
                embed = await logembeds.webhook_created(audit_entry.target, moderator, channel)
                await self.cog._send_log(guild, embed, "server", "webhook_create")
            elif audit_entry.action == discord.AuditLogAction.webhook_delete:
                embed = await logembeds.webhook_deleted(audit_entry.before, moderator, channel)
                await self.cog._send_log(guild, embed, "server", "webhook_delete")
            elif audit_entry.action == discord.AuditLogAction.webhook_update:
                changes = [f"`{k}` changed" for k in audit_entry.changes.before]
                embed = await logembeds.webhook_updated(audit_entry.target, moderator, channel, changes)
                await self.cog._send_log(guild, embed, "server", "webhook_update")

        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Logs when an invite is created."""
        if not self.cog or not invite.guild: return
        embed = await logembeds.invite_created(invite)
        await self.cog._send_log(invite.guild, embed, "server", "invite_create")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Logs when an invite is deleted."""
        if not self.cog or not invite.guild: return
        embed = await logembeds.invite_deleted(invite)
        await self.cog._send_log(invite.guild, embed, "server", "invite_delete")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: List[discord.Emoji], after: List[discord.Emoji]):
        """Logs the creation, deletion, or renaming of emojis."""
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
        """Logs the creation, deletion, or updating of guild stickers."""
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
