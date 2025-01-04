import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.menus import MenuPages
from redbot.core.utils.chat_formatting import box
from datetime import datetime, timezone

class SuspiciousUserMonitor(commands.Cog):
    """Monitor and manage new users with accounts younger than 3 months."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "suspicious_role": None,
            "staff_role": None,
            "questionnaire_channel": None,
            "suspicious_users": {},
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await self.config.guild(guild).all()

        if not (settings["suspicious_role"] and settings["staff_role"] and settings["questionnaire_channel"]):
            return

        account_age = datetime.now(timezone.utc) - member.created_at
        if account_age.days < 90:  # Check if the account is younger than 3 months
            staff_role = guild.get_role(settings["staff_role"])
            suspicious_role = guild.get_role(settings["suspicious_role"])
            if not (staff_role and suspicious_role):
                return

            previous_roles = [role.id for role in member.roles if role != guild.default_role]

            embed = discord.Embed(
                title="Suspicious Account Alert",
                description=f"<@{member.id}> joined the server. Their account is {account_age.days} days old.",
                color=discord.Color.red()
            )
            embed.add_field(name="User ID", value=f"`{member.id}`", inline=True)
            embed.add_field(name="Account Creation Date", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)

            view = discord.ui.View()

            @discord.ui.button(label="Mark as Suspicious", style=discord.ButtonStyle.danger)
            async def mark_suspicious(interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.guild_permissions.manage_roles:
                    await member.add_roles(suspicious_role, reason="Marked as suspicious")
                    await member.remove_roles(*[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)], reason="Marked as suspicious")

                    # Save previous roles
                    async with self.config.guild(guild).suspicious_users() as suspicious_users:
                        suspicious_users[str(member.id)] = previous_roles

                    # DM the questionnaire
                    try:
                        await member.send(
                            "Hey there, you've been automatically assigned and put into a suspicious category before we can continue your entry into the discord, please answer the questionnaire I've provided.\n\n"
                            "```
- How did you find A New Beginning?
- IF by a friend/source (What source did you use?)
- IF by a friend, what was their name? (Discord, VRC, Etc)
- IF you've had a previous Discord account what was your Previous Discord Account?
```
If you do not respond to these within the 10-minute deadline, you will be automatically removed from Discord.\n\nHope to hear back from you soon!"
                        )
                    except discord.Forbidden:
                        pass

                    await interaction.response.send_message("User marked as suspicious and notified.", ephemeral=True)

            @discord.ui.button(label="Verify as Safe", style=discord.ButtonStyle.success)
            async def verify_safe(interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.guild_permissions.manage_roles:
                    async with self.config.guild(guild).suspicious_users() as suspicious_users:
                        previous_roles = suspicious_users.pop(str(member.id), [])

                    await member.remove_roles(suspicious_role, reason="Verified as safe")
                    await member.add_roles(*[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)], reason="Verified as safe")

                    await interaction.response.send_message("User verified as safe and roles restored.", ephemeral=True)

            view.add_item(mark_suspicious)
            view.add_item(verify_safe)

            alert_channel = guild.get_channel(settings["questionnaire_channel"])
            if alert_channel:
                await alert_channel.send(content=f"<@&{staff_role.id}>", embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel) or message.author.bot:
            return

        guild = self.bot.get_guild(988099809124708383)  # Replace with your guild ID
        settings = await self.config.guild(guild).all()
        alert_channel = guild.get_channel(settings["questionnaire_channel"])

        if str(message.author.id) in settings["suspicious_users"]:
            await message.author.send("Your response has been submitted.")
            if alert_channel:
                embed = discord.Embed(
                    title="Suspicious User Response",
                    description=message.content,
                    color=discord.Color.blue()
                )
                embed.set_author(name=str(message.author), icon_url=message.author.avatar.url)
                embed.add_field(name="User ID", value=f"`{message.author.id}`", inline=False)
                await alert_channel.send(embed=embed)

    @commands.guild_only()
    @commands.admin()
    @commands.group()
    async def suspiciousmonitor(self, ctx):
        """Configure the suspicious user monitor."""
        pass

    @suspiciousmonitor.command()
    async def setrole(self, ctx, role: discord.Role):
        """Set the suspicious role."""
        await self.config.guild(ctx.guild).suspicious_role.set(role.id)
        await ctx.send(f"Suspicious role set to {role.mention}.")

    @suspiciousmonitor.command()
    async def setstaff(self, ctx, role: discord.Role):
        """Set the staff role to ping."""
        await self.config.guild(ctx.guild).staff_role.set(role.id)
        await ctx.send(f"Staff role set to {role.mention}.")

    @suspiciousmonitor.command()
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the questionnaire channel."""
        await self.config.guild(ctx.guild).questionnaire_channel.set(channel.id)
        await ctx.send(f"Questionnaire channel set to {channel.mention}.")