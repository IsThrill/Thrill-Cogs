import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from datetime import datetime, timedelta
import pytz  

class BanReasonModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title="Ban Reason")
        self.member = member

        self.reason = discord.ui.TextInput(
            label="Ban Reason", placeholder="Enter the reason for banning the user...", style=discord.TextStyle.long
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        try:
            await self.member.ban(reason=reason)
            await interaction.response.send_message(f"User {self.member} has been banned for: {reason}", ephemeral=True)

            try:
                await self.member.send(f"You've been banned from the server. Reason: {reason}")
            except discord.Forbidden:
                guild = interaction.guild
                staff_channel = guild.get_channel(await Config.get_conf(None, identifier=1234567890).guild(guild).questionnaire_channel())
                if staff_channel:
                    await staff_channel.send(f"Failed to reach <@{self.member.id}>'s DMs before banning.")

        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to ban this user.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to ban the user.", ephemeral=True)

class SuspiciousUserMonitor(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "suspicious_role": None,
            "staff_role": None,
            "questionnaire_channel": None,
            "suspicious_users": {},
            "test_mode": False,
            "user_responses": {},
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await self.config.guild(guild).all()

        if not (settings["suspicious_role"] and settings["staff_role"] and settings["questionnaire_channel"]):
            return

        account_age = datetime.now(pytz.utc) - member.created_at if not settings["test_mode"] else timedelta(days=0)
        est_tz = pytz.timezone("US/Eastern")
        account_creation_est = member.created_at.astimezone(est_tz)

        if account_age.days < 90 or settings["test_mode"]:
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
            embed.add_field(name="User ID", value=f"<@{member.id}>", inline=True)
            embed.add_field(name="Account Creation Date (EST)", value=account_creation_est.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=True)
            embed.set_thumbnail(url=member.avatar.url)

            view = discord.ui.View(timeout=600)

            mark_suspicious_button = discord.ui.Button(label="Mark as Suspicious", style=discord.ButtonStyle.danger)
            async def mark_suspicious(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    await member.add_roles(suspicious_role, reason="Marked as suspicious")
                    await member.remove_roles(*[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)], reason="Marked as suspicious")

                    async with self.config.guild(guild).suspicious_users() as suspicious_users:
                        suspicious_users[str(member.id)] = previous_roles

                    try:
                        await member.send(
                            "You have been marked as suspicious. Please respond to the questionnaire sent to you."
                        )
                    except discord.Forbidden:
                        staff_channel = guild.get_channel(settings["questionnaire_channel"])
                        if staff_channel:
                            await staff_channel.send(f"Failed to send a DM to <@{member.id}>.")

                    await interaction.response.send_message("User marked as suspicious and notified.", ephemeral=True)

            mark_suspicious_button.callback = mark_suspicious

            verify_safe_button = discord.ui.Button(label="Verify as Safe", style=discord.ButtonStyle.success)
            async def verify_safe(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    async with self.config.guild(guild).suspicious_users() as suspicious_users:
                        previous_roles = suspicious_users.pop(str(member.id), [])

                    await member.remove_roles(suspicious_role, reason="Verified as safe")
                    await member.add_roles(*[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)], reason="Verified as safe")

                    try:
                        await member.send(
                            "**Approved**\nThank you for your confirmation. Your roles have been restored."
                        )
                    except discord.Forbidden:
                        pass

                    await interaction.response.send_message("User verified as safe and roles restored.", ephemeral=True)

            verify_safe_button.callback = verify_safe

            view.add_item(mark_suspicious_button)
            view.add_item(verify_safe_button)

            alert_channel = guild.get_channel(settings["questionnaire_channel"])
            if alert_channel:
                await alert_channel.send(content=f"<@&{staff_role.id}>", embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel) or message.author.bot:
            return

        guild = self.bot.get_guild(988099809124708383)  
        settings = await self.config.guild(guild).all()
        alert_channel = guild.get_channel(settings["questionnaire_channel"])

        if str(message.author.id) in settings["suspicious_users"]:
            if message.author.id in settings["user_responses"]:
                await message.author.send("You have already submitted your response.")
                return

            async with self.config.guild(guild).user_responses() as user_responses:
                user_responses[str(message.author.id)] = message.content

            if alert_channel:
                embed = discord.Embed(
                    title="Suspicious User Response",
                    description=message.content,
                    color=discord.Color.blue()
                )
                embed.set_author(name=str(message.author), icon_url=message.author.avatar.url)
                embed.add_field(name="User ID", value=f"<@{message.author.id}> ({message.author.id})", inline=False)

                ban_button = discord.ui.Button(label="Ban User", style=discord.ButtonStyle.danger)

                async def ban_user(interaction: discord.Interaction):
                    if interaction.user.guild_permissions.ban_members:
                        member = interaction.guild.get_member(message.author.id)
                        if member:
                            try:
                                await member.send(f"You are being banned for the following reason: {message.content}")
                            except discord.Forbidden:
                                if alert_channel:
                                    await alert_channel.send(f"Failed to DM <@{message.author.id}> before banning.")

                            await interaction.response.send_modal(BanReasonModal(member))
                        else:
                            await interaction.response.send_message("User is no longer a member of the server.", ephemeral=True)

                ban_button.callback = ban_user

                view = discord.ui.View()
                view.add_item(ban_button)

                await alert_channel.send(embed=embed, view=view)

            await message.author.send("Your response has been submitted.")

    @commands.group(name="sus", invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def suspiciousmonitor(self, ctx):
        commands_list = {
            "sus setrole": "Set the suspicious role.",
            "sus setstaff": "Set the staff role to ping.",
            "sus setchannel": "Set the alert channel.",
            "sus test": "Toggle test mode.",
        }
        description = "\n".join([f"`{cmd}`: {desc}" for cmd, desc in commands_list.items()])
        embed = discord.Embed(
            title="Suspicious Monitor Commands",
            description=description,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @suspiciousmonitor.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def setrole(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).suspicious_role.set(role.id)
        await ctx.send(f"Suspicious role set to {role.mention}.")

    @suspiciousmonitor.command(name="setstaff")
    @commands.has_permissions(administrator=True)
    async def setstaff(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).staff_role.set(role.id)
        await ctx.send(f"Staff role set to {role.mention}.")

    @suspiciousmonitor.command(name="setchannel")
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        await self.config.guild(ctx.guild).questionnaire_channel.set(channel.id)
        await ctx.send(f"Questionnaire channel set to {channel.mention}.")

    @suspiciousmonitor.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx):
        settings = await self.config.guild(ctx.guild).all()
        test_mode = not settings["test_mode"]
        await self.config.guild(ctx.guild).test_mode.set(test_mode)
        status = "enabled" if test_mode else "disabled"
        await ctx.send(f"Test mode {status}.")
