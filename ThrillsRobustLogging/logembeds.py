import discord
from datetime import datetime, timezone

# --- Color Palette for Consistency ---
LOG_COLORS = {
    "red": 0xE74C3C,      # Deletions, Bans
    "orange": 0xE67E22,   # Moderation Actions
    "yellow": 0xFEE75C,   # Message Edits, Nickname Changes
    "green": 0x2ECC71,    # Joins, Creations
    "blue": 0x3498DB,     # Informational, Voice Updates
    "purple": 0x9B59B6    # Server & Role Updates
}

# --- Event-Specific Embeds ---

async def message_deleted(message: discord.Message):
    """Creates an embed for a deleted message."""
    if message.author.bot:  # Optional: Skips logging for bots
        return None

    embed = discord.Embed(
        description=f"**Message sent by {message.author.mention} deleted in {message.channel.mention}**",
        color=LOG_COLORS["red"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=f"{message.author.display_name}", icon_url=message.author.display_avatar.url)

    if message.content:
        embed.add_field(name="Content", value=f"```{message.content[:1021]}...```" if len(message.content) > 1024 else f"```{message.content}```", inline=False)

    if message.attachments:
        files = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
        embed.add_field(name="Attachments", value=files, inline=False)

    embed.set_footer(text=f"Author ID: {message.author.id} | Message ID: {message.id}")
    return embed

async def message_edited(before: discord.Message, after: discord.Message):
    """Creates an embed for an edited message."""
    if before.author.bot or before.content == after.content:
        return None

    embed = discord.Embed(
        description=f"**Message edited in {before.channel.mention}** [Jump to Message]({after.jump_url})",
        color=LOG_COLORS["yellow"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=f"{before.author.display_name}", icon_url=before.author.display_avatar.url)
    embed.add_field(name="Before", value=f"```{before.content[:1024]}```", inline=False)
    embed.add_field(name="After", value=f"```{after.content[:1024]}```", inline=False)
    embed.set_footer(text=f"Author ID: {before.author.id} | Message ID: {before.id}")
    return embed

async def member_joined(member: discord.Member):
    """Creates an embed for a new member."""
    embed = discord.Embed(
        description=f"**{member.mention} joined the server**",
        color=LOG_COLORS["green"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Total Members", value=f"{member.guild.member_count}", inline=True)
    embed.set_footer(text=f"User ID: {member.id}")
    return embed

async def member_left(member: discord.Member):
    """Creates an embed for a member who left."""
    embed = discord.Embed(
        description=f"**{member.mention} left the server**",
        color=LOG_COLORS["red"],
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if member.joined_at:
        embed.add_field(name="Had Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    if roles:
        embed.add_field(name="Roles", value=" ".join(roles)[:1024], inline=False)
    
    embed.set_footer(text=f"User ID: {member.id}")
    return embed