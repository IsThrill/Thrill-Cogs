import discord
from discord.ui import Button, View
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from datetime import datetime
import pytz

class SuspiciousUserView(View):
    def __init__(self, cog: commands.Cog, member: discord.Member, settings: dict):
        super().__init__(timeout=None) 
        self.cog = cog
        self.member = member
        self.settings = settings

    @discord.ui.button(label="Mark as Suspicious", style=discord.ButtonStyle.danger)
    async def mark_suspicious_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You don't have permission to do that.", ephemeral=True)
            return

        suspicious_role_id = self.settings.get("suspicious_role")
        if not suspicious_role_id:
            await interaction.response.send_message("The suspicious role is not configured. Use the `sus setrole` command.", ephemeral=True)
            return

        suspicious_role = interaction.guild.get_role(suspicious_role_id)
        if not suspicious_role:
            await interaction.response.send_message("The configured suspicious role could not be found.", ephemeral=True)
            return
            
        original_role_ids = [role.id for role in self.member.roles if role.id != interaction.guild.id]
        async with self.cog.config.guild(interaction.guild).quarantined_users() as quarantined:
            quarantined[str(self.member.id)] = original_role_ids

        try:
            await self.member.edit(roles=[suspicious_role], reason="Marked as suspicious by moderator.")
            await interaction.response.send_message(f"{self.member.mention}'s roles have been replaced with the suspicious role.", ephemeral=True)
            button.disabled = True
            for child in self.children:
                if child.label == "Verify Safe":
                    child.disabled = False
            await interaction.message.edit(view=self)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have the permissions to edit this user's roles.", ephemeral=True)

    @discord.ui.button(label="Verify Safe", style=discord.ButtonStyle.success)
    async def verify_safe_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You don't have permission to do that.", ephemeral=True)
            return

        original_role_ids = []
        async with self.cog.config.guild(interaction.guild).quarantined_users() as quarantined:
            if str(self.member.id) in quarantined:
                original_role_ids = quarantined.pop(str(self.member.id))
            else:
                await interaction.response.send_message("This user was not in quarantine or has already been verified.", ephemeral=True)
                return
        
        roles_to_restore = [role for r_id in original_role_ids if (role := interaction.guild.get_role(r_id))]

        try:
            await self.member.edit(roles=roles_to_restore, reason="Verified as safe by moderator.")
            await interaction.response.send_message(f"Restored original roles for {self.member.mention}.", ephemeral=True)
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have the permissions to restore this user's roles.", ephemeral=True)
            async with self.cog.config.guild(interaction.guild).quarantined_users() as quarantined:
                quarantined[str(self.member.id)] = original_role_ids


class SuspiciousUserMonitor(commands.Cog):
    """A cog to monitor new members for suspicious account ages."""
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "suspicious_role": None,
            "alert_channel": None,
            "mention_role": None,
            "min_account_age": 90,
            "quarantined_users": {},
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        guild = member.guild
        settings = await self.config.guild(guild).all()
        
        alert_channel_id = settings.get("alert_channel")
        if not alert_channel_id:
            return

        account_age = datetime.now(pytz.utc) - member.created_at
        
        if account_age.days < settings["min_account_age"]:
            alert_channel = guild.get_channel(alert_channel_id)
            if not alert_channel:
                return

            mention_role_id = settings.get("mention_role")
            content = f"<@&{mention_role_id}>" if mention_role_id else ""
            content += f" (User: {member.mention})"

            est_tz = pytz.timezone("US/Eastern")
            account_creation_est = member.created_at.astimezone(est_tz)

            embed = discord.Embed(
                title="Suspicious Account Alert",
                description=f"A user has joined whose account is younger than the configured minimum of **{settings['min_account_age']}** days.",
                color=discord.Color.red(),
                timestamp=datetime.now(pytz.utc)
            )
            embed.add_field(name="User", value=f"{member.mention} ({member.name})", inline=False)
            embed.add_field(name="User ID", value=box(str(member.id)), inline=True)
            embed.add_field(name="Account Age", value=f"{account_age.days} days", inline=True)
            embed.add_field(name="Account Creation Date (EST)", value=account_creation_est.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=False)
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            
            view = SuspiciousUserView(cog=self, member=member, settings=settings)
            
            try:
                await alert_channel.send(
                    content=content,
                    embed=embed,
                    view=view,
                    allowed_mentions=discord.AllowedMentions(roles=True, users=True)
                )
            except discord.Forbidden:
                print(f"Missing permissions to send alert in {alert_channel.name} on guild {guild.name}")
            except Exception as e:
                print(f"Failed to send suspicious user alert: {e}")

    @commands.group(name="sus", invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def suspiciousmonitor(self, ctx: commands.Context):
        """Manage the Suspicious User Monitor settings."""
        await ctx.send_help()

    @suspiciousmonitor.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def setrole(self, ctx: commands.Context, role: discord.Role):
        """Set the role to be assigned to suspicious users."""
        await self.config.guild(ctx.guild).suspicious_role.set(role.id)
        await ctx.send(f"Suspicious role set to {role.mention}.")

    @suspiciousmonitor.command(name="setchannel")
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel where alerts will be sent."""
        await self.config.guild(ctx.guild).alert_channel.set(channel.id)
        await ctx.send(f"Alert channel set to {channel.mention}.")

    @suspiciousmonitor.command(name="setage")
    @commands.has_permissions(administrator=True)
    async def setage(self, ctx: commands.Context, days: int):
        """Set the minimum account age (in days) before a user is flagged."""
        if days < 0:
            return await ctx.send("Please provide a non-negative number of days.")
        await self.config.guild(ctx.guild).min_account_age.set(days)
        await ctx.send(f"Minimum account age set to {days} days.")

    @suspiciousmonitor.command(name="setmention")
    @commands.has_permissions(administrator=True)
    async def setmention(self, ctx: commands.Context, role: discord.Role):
        """Set the role to be mentioned in the alert."""
        await self.config.guild(ctx.guild).mention_role.set(role.id)
        await ctx.send(f"Mention role set to {role.mention}.")
        
    @suspiciousmonitor.command(name="settings")
    @commands.has_permissions(administrator=True)
    async def show_settings(self, ctx: commands.Context):
        """Display the current settings for the Suspicious User Monitor."""
        settings = await self.config.guild(ctx.guild).all()
        
        suspicious_role_id = settings.get("suspicious_role")
        alert_channel_id = settings.get("alert_channel")
        mention_role_id = settings.get("mention_role")
        min_account_age = settings.get("min_account_age")

        suspicious_role = ctx.guild.get_role(suspicious_role_id) if suspicious_role_id else None
        alert_channel = ctx.guild.get_channel(alert_channel_id) if alert_channel_id else None
        mention_role = ctx.guild.get_role(mention_role_id) if mention_role_id else None

        embed = discord.Embed(
            title="Suspicious User Monitor Settings",
            color=await ctx.embed_color()
        )
        embed.add_field(
            name="Suspicious Role", 
            value=suspicious_role.mention if suspicious_role else "Not set",
            inline=False
        )
        embed.add_field(
            name="Alert Channel", 
            value=alert_channel.mention if alert_channel else "Not set",
            inline=False
        )
        embed.add_field(
            name="Mention Role", 
            value=mention_role.mention if mention_role else "Not set",
            inline=False
        )
        embed.add_field(
            name="Minimum Account Age", 
            value=f"{min_account_age} days",
            inline=False
        )
        
        await ctx.send(embed=embed)
