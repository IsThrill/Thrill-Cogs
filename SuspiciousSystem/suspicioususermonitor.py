import discord
from discord.ui import Button, View
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from datetime import datetime, timedelta
import pytz

class SuspiciousUserMonitor(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "suspicious_role": None,
            "alert_channel": None,
            "mention_role": None,
            "min_account_age": 90,
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return 
        
        guild = member.guild
        settings = await self.config.guild(guild).all()
        
        if not settings["alert_channel"]:
            return

        account_age = datetime.now(pytz.utc) - member.created_at
        est_tz = pytz.timezone("US/Eastern")
        account_creation_est = member.created_at.astimezone(est_tz)

        if account_age.days < settings["min_account_age"]:
            alert_channel = guild.get_channel(settings["questionnaire_channel"])
            mention_role = f'<@&{settings["mention_role"]}>' if settings["mention_role"] else "@everyone"
            
            embed = discord.Embed(
                title="Suspicious Account Alert",
                description=f"{mention_role}, <@{member.id}> joined the server. Their account is {account_age.days} days old.",
                color=discord.Color.red(),
            )
            embed.add_field(name="User ID", value=box(str(member.id)), inline=True)
            embed.add_field(name="Account Creation Date (EST)", value=account_creation_est.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=True)
            embed.set_thumbnail(url=member.avatar.url)

            view = View()
            mark_suspicious_button = Button(label="Mark as Suspicious", style=discord.ButtonStyle.danger)
            verify_safe_button = Button(label="Verify Safe", style=discord.ButtonStyle.success)

            async def mark_suspicious(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    suspicious_role = guild.get_role(1283455822281838693)
                    if suspicious_role:
                        await member.edit(roles=[suspicious_role])
                        await interaction.response.send_message("User marked as suspicious.", ephemeral=True)

            async def verify_safe(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    await member.remove_roles(guild.get_role(1283455822281838693), reason="Verified as safe")
                    await interaction.response.send_message("User verified as safe and roles restored.", ephemeral=True)

            mark_suspicious_button.callback = mark_suspicious
            verify_safe_button.callback = verify_safe

            view.add_item(mark_suspicious_button)
            view.add_item(verify_safe_button)

            if alert_channel:
                await alert_channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))

    @commands.group(name="sus", invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def suspiciousmonitor(self, ctx):
        commands_list = {
            "sus setrole": "Set the suspicious role.",
            "sus setchannel": "Set the alert channel.",
            "sus setage": "Set the minimum account age for alerting staff.",
            "sus setmention": "Sets the mention role or specify everyone",
        }
        description = "\n".join([f"{cmd}: {desc}" for cmd, desc in commands_list.items()])
        embed = discord.Embed(
            title="Suspicious Monitor Commands",
            description=description,
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

    @suspiciousmonitor.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def setrole(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).suspicious_role.set(role.id)
        await ctx.send(f"Suspicious role set to {role.mention}.")

    @suspiciousmonitor.command(name="setchannel")
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        await self.config.guild(ctx.guild).alert_channel.set(channel.id)
        await ctx.send(f"Alert channel set to {channel.mention}.")

    @suspiciousmonitor.command(name="setage")
    @commands.has_permissions(administrator=True)
    async def setage(self, ctx, days: int):
        await self.config.guild(ctx.guild).min_account_age.set(days)
        await ctx.send(f"Minimum account age set to {days} days.")

    @suspiciousmonitor.command(name="setmention")
    @commands.has_permissions(administrator=True)
    async def setmention(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).mention_role.set(role.id)
        await ctx.send(f"Mention role set to {role.mention}.")
