import discord
from datetime import datetime, timezone
from typing import List, Optional 

# --- Color Palette for Consistency ---
LOG_COLORS = {
    "red": 0xE74C3C,      # Deletions, Bans, Leaves
    "orange": 0xE67E22,   # Moderation Actions (Kicks, Mutes), AutoMod
    "yellow": 0xFEE75C,   # Message Edits, Nickname/Role/Sticker/Event Updates
    "green": 0x2ECC71,    # Joins, Creations, Unbans
    "blue": 0x3498DB,     # Informational, Voice Moves, Avatar Changes
    "purple": 0x9B59B6    # High-level Server & Role Updates
}

# --- Helper to safely get moderator mention ---
def _get_mod_mention(moderator):
    """Safely returns a moderator's mention or the raw string if it's not a user object."""
    return moderator.mention if isinstance(moderator, (discord.User, discord.Member)) else str(moderator)

# --- AutoMod & Raw Audit Listeners ---

async def automod_action_triggered(execution: "discord.AutoModAction"):
    """Creates an embed for a triggered AutoMod rule."""
    action_map = {
        "block_message": "Blocked Message", "send_alert_message": "Sent Alert", "timeout": "Timed Out User"
    }
    trigger_map = {
        "keyword": "Matched Keyword", "spam": "Detected Spam",
        "keyword_preset": "Matched Keyword Preset", "mention_spam": "Detected Mention Spam"
    }
    action_taken = action_map.get(execution.action.type.name, 'Unknown')
    if execution.action.type.name == 'timeout':
        action_taken = f"Timed Out User ({execution.action.duration.total_seconds() / 60:.0f}m)"

    embed = discord.Embed(
        title="AutoMod Rule Triggered",
        description=f"Action Taken: **{action_taken}**",
        color=LOG_COLORS["orange"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=execution.member.display_name, icon_url=execution.member.display_avatar.url)
    embed.add_field(name="Triggered By", value=execution.member.mention, inline=True)
    embed.add_field(name="In Channel", value=execution.channel.mention, inline=True)
    embed.add_field(name="Rule Name", value=f"`{execution.rule.name}`", inline=False)
    embed.add_field(name="Reason", value=f"`{trigger_map.get(execution.rule_trigger_type.name, 'Unknown')}`", inline=True)
    if execution.matched_keyword:
        embed.add_field(name="Matched Keyword", value=f"`{execution.matched_keyword}`", inline=True)
    if execution.content:
        embed.add_field(name="Original Message", value=f"```{discord.utils.escape_markdown(execution.content)}```"[:1024], inline=False)
    embed.set_footer(text=f"User ID: {execution.member.id}")
    return embed

async def raw_audit_log_entry(entry: discord.AuditLogEntry):
    """Creates an embed for any raw audit log entry."""
    action_str = str(entry.action).replace("AuditLogAction.", "").replace("_", " ").title()
    embed = discord.Embed(
        description=f"**Action:** `{action_str}`",
        color=LOG_COLORS["blue"],
        timestamp=entry.created_at
    )
    embed.set_author(name=f"User: {entry.user} ({entry.user.id})", icon_url=entry.user.display_avatar.url)
    if entry.target:
        embed.add_field(name="Target", value=f"`{entry.target}` (`{entry.target.id}`)", inline=False)
    if entry.reason:
        embed.add_field(name="Reason", value=f"```{entry.reason}```", inline=False)
    return embed

# --- Message Listeners ---

async def message_deleted(message: discord.Message):
    if message.author.bot: return None
    embed = discord.Embed(
        description=f"**Message sent by {message.author.mention} deleted in {message.channel.mention}**",
        color=LOG_COLORS["red"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=f"{message.author.display_name}", icon_url=message.author.display_avatar.url)
    if message.content:
        embed.add_field(name="Content", value=f"```{discord.utils.escape_markdown(message.content)}```"[:1024], inline=False)
    if message.attachments:
        files = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
        embed.add_field(name="Attachments", value=files, inline=False)
    embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
    return embed

async def message_deleted_by_mod(message: discord.Message, moderator: discord.User):
    embed = discord.Embed(
        description=f"**Message sent by {message.author.mention} deleted in {message.channel.mention}**",
        color=LOG_COLORS["orange"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=f"{message.author.display_name}", icon_url=message.author.display_avatar.url)
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=False)
    if message.content:
        embed.add_field(name="Content", value=f"```{discord.utils.escape_markdown(message.content)}```"[:1024], inline=False)
    if message.attachments:
        files = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
        embed.add_field(name="Attachments", value=files, inline=False)
    embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
    return embed

async def message_edited(before: discord.Message, after: discord.Message):
    if before.author.bot or before.content == after.content: return None
    embed = discord.Embed(
        description=f"**Message edited in {before.channel.mention}** [Jump to Message]({after.jump_url})",
        color=LOG_COLORS["yellow"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=f"{before.author.display_name}", icon_url=before.author.display_avatar.url)
    embed.add_field(name="Before", value=f"```{discord.utils.escape_markdown(before.content)}```"[:1024], inline=False)
    embed.add_field(name="After", value=f"```{discord.utils.escape_markdown(after.content)}```"[:1024], inline=False)
    embed.set_footer(text=f"Author ID: {before.author.id} | Message ID: {before.id}")
    return embed

async def messages_purged(count: int, channel: discord.TextChannel, moderator: discord.User):
    embed = discord.Embed(
        title="Messages Purged",
        description=f"**{count} messages were deleted in {channel.mention}**",
        color=LOG_COLORS["red"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Purged By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Channel ID: {channel.id}")
    return embed

# --- Member Listeners ---

async def member_joined(member: discord.Member, invite: discord.Invite, is_new: bool):
    """Creates an embed for a new member with invite tracking."""
    
    description = f"**{member.mention} ({discord.utils.escape_markdown(str(member))}) joined the server**"
    if is_new:
        description += " <:thrillswarning:1248039750012502157>"

    embed = discord.Embed(
        description=description,
        color=LOG_COLORS["green"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    # --- Member Details ---
    embed.add_field(name="Account Age", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Total Members", value=f"{member.guild.member_count}", inline=True)
    embed.add_field(name="User ID", value=f"`{member.id}`", inline=False)

    invite_info = "Could not determine invite."
    if invite:
        invite_link = f"https://discord.gg/{invite.code}"
        if invite.inviter: 
            invite_info = (f"**Invited by:** {invite.inviter.mention}\n"
                           f"**Invite:** {invite_link} (`{invite.uses}` uses)")
        else: 
            invite_info = f"Joined via the server's vanity URL:\n{invite_link}"

    embed.add_field(name="Invite Information", value=invite_info, inline=False)
        
    embed.set_footer(text="Member Joined")
    return embed

async def member_left(member: discord.Member, invite_code: Optional[str]):
    """Creates an embed for a member who left, including their join invite."""
    
    embed = discord.Embed(
        description=f"**{member.mention} ({discord.utils.escape_markdown(str(member))}) left the server**",
        color=LOG_COLORS["red"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    # --- Member Details ---
    if member.joined_at:
        embed.add_field(name="Member For", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Joined On", value=f"<t:{int(member.joined_at.timestamp())}:D>", inline=True)
    
    if invite_code:
        embed.add_field(name="Joined Via", value=f"https://discord.gg/{invite_code}", inline=True)
    else:
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
        
    embed.add_field(name="User ID", value=f"`{member.id}`", inline=False)

    # --- Roles ---
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    if roles:
        embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles)[:1024], inline=False)
        
    embed.set_footer(text="Member Left")
    return embed

async def member_nickname_changed(member: discord.Member, moderator: discord.User, before_nick: str, after_nick: str):
    before_nick = before_nick or member.name
    after_nick = after_nick or member.name
    embed = discord.Embed(title="Nickname Changed", color=LOG_COLORS["yellow"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=False)
    embed.add_field(name="Changed By", value=_get_mod_mention(moderator), inline=False)
    embed.add_field(name="Before", value=f"`{before_nick}`", inline=True)
    embed.add_field(name="After", value=f"`{after_nick}`", inline=True)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def member_roles_updated(member: discord.Member, moderator, added_roles: list, removed_roles: list):
    embed = discord.Embed(title="Member Roles Updated", color=LOG_COLORS["purple"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=True)
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator), inline=True)
    if added_roles:
        embed.add_field(name="Roles Added", value=" ".join([r.mention for r in added_roles]), inline=False)
    if removed_roles:
        embed.add_field(name="Roles Removed", value=" ".join([r.mention for r in removed_roles]), inline=False)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def member_avatar_changed(member: discord.Member):
    embed = discord.Embed(description=f"{member.mention} **updated their server profile avatar**", color=LOG_COLORS["blue"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

# --- Moderation Listeners ---

async def member_banned(user: discord.User, moderator, reason: str):
    embed = discord.Embed(title="Member Banned", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{user.display_name} ({user.id})", icon_url=user.display_avatar.url)
    embed.add_field(name="Member", value=user.mention, inline=True)
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator), inline=True)
    embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
    return embed

async def member_unbanned(user: discord.User, moderator, reason: str):
    embed = discord.Embed(title="Member Unbanned", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{user.display_name} ({user.id})", icon_url=user.display_avatar.url)
    embed.add_field(name="Member", value=user.mention, inline=True)
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator), inline=True)
    embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
    return embed

async def member_kicked(member: discord.Member, moderator, reason: str):
    embed = discord.Embed(title="Member Kicked", color=LOG_COLORS["orange"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=True)
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator), inline=True)
    embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
    return embed

async def member_timed_out(member: discord.Member, moderator, reason: str, until: datetime):
    embed = discord.Embed(title="Member Timed Out", color=LOG_COLORS["orange"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=True)
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator), inline=True)
    embed.add_field(name="Expires", value=f"<t:{int(until.timestamp())}:R>", inline=False)
    embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
    return embed

async def member_timeout_removed(member: discord.Member, moderator, reason: str):
    embed = discord.Embed(title="Member Timeout Removed", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url)
    embed.add_field(name="Member", value=member.mention, inline=True)
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator), inline=True)
    embed.add_field(name="Reason", value=f"```{reason}```", inline=False)
    return embed

# --- Role Listeners ---

async def role_created(role: discord.Role, moderator):
    embed = discord.Embed(description=f"**Role Created: {role.mention}**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Role Name", value=role.name, inline=True)
    embed.add_field(name="Created By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Role ID: {role.id}")
    return embed

async def role_deleted(role: discord.Role, moderator):
    embed = discord.Embed(description=f"**Role Deleted**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Role Name", value=f"`{role.name}`", inline=True)
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Role ID: {role.id}")
    return embed

async def role_updated(role: discord.Role, moderator, changes: list):
    embed = discord.Embed(title=f"Role Updated: {role.name}", description="\n".join(changes), color=LOG_COLORS["purple"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Role", value=role.mention, inline=True)
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Role ID: {role.id}")
    return embed

# --- Channel, Thread, and Category Listeners ---

async def channel_created(channel: discord.abc.GuildChannel, moderator: discord.User):
    channel_type = str(channel.type).replace('_', ' ').title()
    embed = discord.Embed(description=f"**{channel_type} Created: {channel.mention}**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Name", value=f"`{channel.name}`", inline=True)
    embed.add_field(name="Created By", value=_get_mod_mention(moderator), inline=True)
    if channel.category:
        embed.add_field(name="Category", value=channel.category.name, inline=True)
    embed.set_footer(text=f"Channel ID: {channel.id}")
    return embed

async def channel_deleted(channel: discord.abc.GuildChannel, moderator: discord.User):
    channel_type = str(channel.type).replace('_', ' ').title()
    embed = discord.Embed(description=f"**{channel_type} Deleted**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Name", value=f"`{channel.name}`", inline=True)
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=True)
    if channel.category:
        embed.add_field(name="Category", value=channel.category.name, inline=True)
    embed.set_footer(text=f"Channel ID: {channel.id}")
    return embed

async def channel_updated(channel: discord.abc.GuildChannel, moderator: discord.User, changes: list):
    embed = discord.Embed(title=f"Channel Updated: #{channel.name}", description="\n".join(changes), color=LOG_COLORS["purple"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Channel", value=channel.mention, inline=True)
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Channel ID: {channel.id}")
    return embed

async def thread_created(thread: discord.Thread):
    embed = discord.Embed(description=f"**Thread Created: {thread.mention}**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Parent Channel", value=thread.parent.mention, inline=True)
    if thread.owner:
        embed.add_field(name="Created By", value=thread.owner.mention, inline=True)
    embed.set_footer(text=f"Thread ID: {thread.id}")
    return embed

async def thread_deleted(thread: discord.Thread, moderator):
    embed = discord.Embed(title="Thread Deleted", description=f"Thread `{thread.name}` was deleted from {thread.parent.mention}", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Thread ID: {thread.id}")
    return embed

async def thread_updated(thread: discord.Thread, moderator, changes: list):
    embed = discord.Embed(title=f"Thread Updated: {thread.mention}", description="\n".join(changes), color=LOG_COLORS["yellow"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator))
    embed.set_footer(text=f"Thread ID: {thread.id}")
    return embed

# --- Voice Listeners ---

async def voice_joined(member: discord.Member, channel: discord.VoiceChannel):
    embed = discord.Embed(description=f"{member.mention} **joined voice channel** {channel.mention}", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def voice_left(member: discord.Member, channel: discord.VoiceChannel):
    embed = discord.Embed(description=f"{member.mention} **left voice channel** {channel.mention}", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def voice_moved(member: discord.Member, before: discord.VoiceChannel, after: discord.VoiceChannel):
    embed = discord.Embed(description=f"{member.mention} **moved voice channels**", color=LOG_COLORS["blue"], timestamp=datetime.now(timezone.utc))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.add_field(name="From", value=before.mention, inline=True)
    embed.add_field(name="To", value=after.mention, inline=True)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def voice_server_muted(member: discord.Member, channel: discord.VoiceChannel, moderator, muted: bool):
    action = "muted in" if muted else "unmuted in"
    color = LOG_COLORS["orange"] if muted else LOG_COLORS["green"]
    embed = discord.Embed(description=f"{member.mention} **was server {action}** {channel.mention}", color=color, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def voice_server_deafened(member: discord.Member, channel: discord.VoiceChannel, moderator, deafened: bool):
    action = "deafened in" if deafened else "undeafened in"
    color = LOG_COLORS["orange"] if deafened else LOG_COLORS["green"]
    embed = discord.Embed(description=f"{member.mention} **was server {action}** {channel.mention}", color=color, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Moderator", value=_get_mod_mention(moderator))
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

# --- Server, Invite, Emoji & Sticker Listeners ---

async def server_updated(guild: discord.Guild, moderator, changes: list):
    embed = discord.Embed(title="Server Settings Updated", description="\n".join(changes), color=LOG_COLORS["purple"], timestamp=datetime.now(timezone.utc))
    mod_name = moderator.display_name if isinstance(moderator, (discord.User, discord.Member)) else str(moderator)
    mod_avatar = moderator.display_avatar.url if isinstance(moderator, (discord.User, discord.Member)) else None
    embed.set_author(name=mod_name, icon_url=mod_avatar)
    embed.set_footer(text=f"Server ID: {guild.id}")
    return embed

async def webhook_created(webhook, moderator, channel: discord.TextChannel):
    embed = discord.Embed(description=f"**Webhook `{webhook.name}` created in {channel.mention}**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Created By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Webhook ID: {webhook.id}")
    return embed

async def webhook_deleted(webhook, moderator, channel: discord.TextChannel):
    embed = discord.Embed(description=f"**Webhook `{webhook.name}` deleted from {channel.mention}**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Webhook ID: {webhook.id}")
    return embed

async def webhook_updated(webhook, moderator, channel: discord.TextChannel, changes: list):
    embed = discord.Embed(title=f"Webhook Updated: {webhook.name}", description="\n".join(changes), color=LOG_COLORS["purple"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Webhook", value=f"`{webhook.name}` in {channel.mention}", inline=True)
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Webhook ID: {webhook.id}")
    return embed

async def invite_created(invite: discord.Invite):
    embed = discord.Embed(description=f"**Invite created for {invite.channel.mention}**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
    if invite.inviter:
        embed.add_field(name="Created By", value=invite.inviter.mention, inline=True)
    if invite.max_uses:
        embed.add_field(name="Max Uses", value=f"`{invite.max_uses}`", inline=True)
    embed.set_footer(text=f"Invite created")
    return embed

async def invite_deleted(invite: discord.Invite):
    embed = discord.Embed(description=f"**Invite deleted for {invite.channel.mention}**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Code", value=f"`{invite.code}`", inline=True)
    embed.set_footer(text=f"Invite deleted")
    return embed

async def emoji_created(emoji: discord.Emoji, moderator):
    embed = discord.Embed(description=f"**Emoji Created: {emoji}**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=emoji.url)
    embed.add_field(name="Name", value=f"`{emoji.name}`", inline=True)
    embed.add_field(name="Created By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Emoji ID: {emoji.id}")
    return embed

async def emoji_deleted(emoji: discord.Emoji, moderator):
    embed = discord.Embed(description=f"**Emoji Deleted**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=emoji.url)
    embed.add_field(name="Name", value=f"`{emoji.name}`", inline=True)
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=True)
    embed.set_footer(text=f"Emoji ID: {emoji.id}")
    return embed

async def emoji_renamed(before: discord.Emoji, after: discord.Emoji, moderator):
    embed = discord.Embed(description=f"**Emoji Renamed: {after}**", color=LOG_COLORS["yellow"], timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=after.url)
    embed.add_field(name="Before", value=f"`{before.name}`", inline=True)
    embed.add_field(name="After", value=f"`{after.name}`", inline=True)
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Emoji ID: {after.id}")
    return embed

async def sticker_created(sticker: discord.GuildSticker, moderator):
    embed = discord.Embed(description=f"**Sticker Created: `{sticker.name}`**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=sticker.url)
    embed.add_field(name="Created By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Sticker ID: {sticker.id}")
    return embed

async def sticker_deleted(sticker: discord.GuildSticker, moderator):
    embed = discord.Embed(description=f"**Sticker Deleted: `{sticker.name}`**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=sticker.url)
    embed.add_field(name="Deleted By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Sticker ID: {sticker.id}")
    return embed

async def sticker_updated(before: discord.GuildSticker, after: discord.GuildSticker, moderator):
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** `{before.name}` → `{after.name}`")
    if before.description != after.description:
        changes.append(f"**Description:** `{before.description}` → `{after.description}`")
    embed = discord.Embed(title="Sticker Updated", description="\n".join(changes), color=LOG_COLORS["yellow"], timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=after.url)
    embed.add_field(name="Updated By", value=_get_mod_mention(moderator), inline=False)
    embed.set_footer(text=f"Sticker ID: {after.id}")
    return embed

# --- Scheduled Event & Stage Listeners ---

async def scheduled_event_created(event: discord.ScheduledEvent):
    embed = discord.Embed(title="Scheduled Event Created", description=f"**[{event.name}]({event.url})**", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    if event.creator:
        embed.set_author(name=f"Created by {event.creator.display_name}", icon_url=event.creator.display_avatar.url)
    embed.add_field(name="Channel", value=event.channel.mention if event.channel else f"`{event.location}`", inline=True)
    embed.add_field(name="Starts At", value=f"<t:{int(event.start_time.timestamp())}:F>", inline=True)
    return embed

async def scheduled_event_deleted(event: discord.ScheduledEvent):
    embed = discord.Embed(title="Scheduled Event Deleted", description=f"**{event.name}**", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    if event.creator:
        embed.set_author(name=f"Originally created by {event.creator.display_name}", icon_url=event.creator.display_avatar.url)
    embed.add_field(name="Channel", value=f"`{event.channel.name if event.channel else event.location}`", inline=True)
    return embed

async def scheduled_event_updated(before: discord.ScheduledEvent, after: discord.ScheduledEvent):
    changes = []
    if before.name != after.name:
        changes.append(f"**Name:** `{before.name}` → `{after.name}`")
    if before.description != after.description:
        changes.append(f"**Description updated**")
    if before.start_time != after.start_time:
        changes.append(f"**Start Time:** <t:{int(before.start_time.timestamp())}:f> → <t:{int(after.start_time.timestamp())}:f>")
    if before.status != after.status:
        changes.append(f"**Status:** `{before.status}` → `{after.status}`")
    if not changes: return None
    embed = discord.Embed(
        title="Scheduled Event Updated",
        description=f"**[{after.name}]({after.url})**\n" + "\n".join(changes),
        color=LOG_COLORS["yellow"],
        timestamp=datetime.now(timezone.utc)
    )
    return embed

async def stage_started(stage: discord.StageInstance, moderator):
    embed = discord.Embed(title="Stage Started", description=f"**{stage.topic}** in {stage.channel.mention}", color=LOG_COLORS["green"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Started By", value=_get_mod_mention(moderator), inline=False)
    return embed

async def stage_ended(stage: discord.StageInstance, moderator):
    embed = discord.Embed(title="Stage Ended", description=f"**{stage.topic}** in {stage.channel.mention}", color=LOG_COLORS["red"], timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Ended By", value=_get_mod_mention(moderator), inline=False)
    return embed
