import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from datetime import datetime, timedelta
import pytz

class BanReasonModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title="Ban Reason")
        self.member = member

        self.reason = discord.ui.TextInput(
            label="Ban Reason",
            placeholder="Enter the reason for banning the user...",
            style=discord.TextStyle.long,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        try:
            # First, try to DM the user with the ban reason
            try:
                await self.member.send(f"You've been banned from the server. Reason: {reason}")
            except discord.Forbidden:
                # If DM fails, report to the staff channel and proceed with banning
                guild = interaction.guild
                staff_channel_id = await Config.get_conf(None, identifier=1234567890).guild(guild).questionnaire_channel()
                staff_channel = guild.get_channel(staff_channel_id)
                if staff_channel:
                    await staff_channel.send(f"Failed to DM <@{self.member.id}> the ban reason. Proceeding with the ban.")

            # Perform the ban after handling the DM
            await self.member.ban(reason=reason)
            await interaction.response.send_message(f"User {self.member} has been banned for: {reason}", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to ban this user.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to ban the user.", ephemeral=True)

class VerificationModal(discord.ui.Modal):
    def __init__(self, member: discord.Member, bot: Red):
        super().__init__(title="Verification Questions")
        self.member = member
        self.bot = bot

        # Adding the questions as TextInput fields
        self.question_1 = discord.ui.TextInput(label="How did you find A New Beginning?", style=discord.TextStyle.long)
        self.question_2 = discord.ui.TextInput(label="If by a friend/source, what source?", style=discord.TextStyle.long)
        self.question_3 = discord.ui.TextInput(label="If by a friend, what was their name?", style=discord.TextStyle.long)
        self.question_4 = discord.ui.TextInput(label="If you've had a previous Discord account, what was your previous account?", style=discord.TextStyle.long)
        
        self.add_item(self.question_1)
        self.add_item(self.question_2)
        self.add_item(self.question_3)
        self.add_item(self.question_4)

    async def on_submit(self, interaction: discord.Interaction):
        # Collect responses
        responses = {
            "How did you find A New Beginning?": self.question_1.value,
            "If by a friend/source, what source?": self.question_2.value,
            "If by a friend, what was their name?": self.question_3.value,
            "If you've had a previous Discord account, what was your previous account?": self.question_4.value,
        }
        
        # Send the responses to the staff channel
        guild = interaction.guild
        settings = await self.bot.get_cog('SuspiciousUserMonitor').config.guild(guild).all()
        alert_channel = guild.get_channel(settings["questionnaire_channel"])

        embed = discord.Embed(
            title=f"Suspicious User Response from {self.member}",
            color=discord.Color.blue(),
        )
        for question, response in responses.items():
            embed.add_field(name=question, value=response, inline=False)
        
        if alert_channel:
            await alert_channel.send(embed=embed)

        # Acknowledge the user
        await interaction.response.send_message("Thank you for your response. Your information has been sent to the staff.", ephemeral=True)

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
                color=discord.Color.red(),
            )
            embed.add_field(name="User ID", value=box(str(member.id)), inline=True)
            embed.add_field(name="Account Creation Date (EST)", value=account_creation_est.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=True)
            embed.set_thumbnail(url=member.avatar.url)

            view = discord.ui.View(timeout=600)

            mark_suspicious_button = discord.ui.Button(label="Mark as Suspicious", style=discord.ButtonStyle.danger)

            async def mark_suspicious(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    await member.add_roles(suspicious_role, reason="Marked as suspicious")
                    await member.remove_roles(
                        *[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)],
                        reason="Marked as suspicious",
                    )
                    async with self.config.guild(guild).suspicious_users() as suspicious_users:
                        suspicious_users[str(member.id)] = previous_roles

                    try:
                        # Send interactive message to the user
                        verification_button = discord.ui.Button(label="Verification", style=discord.ButtonStyle.success)

                        async def verify_user(interaction: discord.Interaction):
                            # Send the modal for verification questions
                            await interaction.response.send_modal(VerificationModal(member, self.bot))

                        verification_button.callback = verify_user

                        dm_message = await member.send(
                            "Hey there, you've been automatically assigned and put into a suspicious category before we can continue your entry into the Discord. Please click the button below."
                        )
                        view.add_item(verification_button)
                        await dm_message.edit(content="Hey there, you've been automatically assigned and put into a suspicious category. Please click below to verify.", view=view)
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
                    await member.add_roles(
                        *[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)],
                        reason="Verified as safe",
                    )

                    try:
                        await member.send("**Approved**\nThank you for your confirmation. Your roles have been restored.")
                    except discord.Forbidden:
                        pass

                    await interaction.response.send_message("User verified as safe and roles restored.", ephemeral=True)

            verify_safe_button.callback = verify_safe

            view.add_item(mark_suspicious_button)
            view.add_item(verify_safe_button)

            alert_channel = guild.get_channel(settings["questionnaire_channel"])
            if alert_channel:
                staff_ping = f"<@&{staff_role.id}>" if not settings["test_mode"] else ""
                await alert_channel.send(content=staff_ping, embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel) or message.author.bot:
            return

        guild = self.bot.get_guild(988099809124708383)
        settings = await self.config.guild(guild).all()
        alert_channel = guild.get_channel(settings["questionnaire_channel"])

        if str(message.author.id) in settings["suspicious_users"]:
            # Check if the user has already submitted their response.
            async with self.config.guild(guild).user_responses() as user_responses:
                if str(message.author.id) in user_responses:
                    await message.author.send("You have already submitted your response.")
                    return  # Prevent further submission.

                # Store the first response.
                user_responses[str(message.author.id)] = message.content

                if alert_channel:
                    embed = discord.Embed(
                        title="Suspicious User Response",
                        description=message.content,
                        color=discord.Color.blue(),
                    )
                    embed.set_author(name=str(message.author), icon_url=message.author.avatar.url)
                    embed.add_field(name="User ID", value=box(str(message.author.id)), inline=False)

                    ban_button = discord.ui.Button(label="Ban User", style=discord.ButtonStyle.danger)

                    async def ban_user(interaction: discord.Interaction):
                        if interaction.user.guild_permissions.ban_members:
                            member = interaction.guild.get_member(message.author.id)
                            if member:
                                await interaction.response.send_modal(BanReasonModal(member))
                            else:
                                await interaction.response.send_message("User is no longer a member of the server.", ephemeral=True)

                    ban_button.callback = ban_user

                    view = discord.ui.View()
                    view.add_item(ban_button)

                    staff_ping = f"<@&{settings['staff_role']}>" if not settings["test_mode"] else ""
                    await alert_channel.send(content=staff_ping, embed=embed, view=view)

                await message.author.send("Your response has been submitted.")

    @commands.group(name="sus", invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def suspiciousmonitor(self, ctx):
        commands_list = {
            "sus setrole": "Set the suspicious role.",
            "sus setstaff": "Set the staff role to ping.",
            "sus setchannel": "Set the alert channel.",
            "sus test": "Toggle test mode.",
            "sus clearresponse": "Clear a user's response so they can resubmit.",
        }
        description = "\n".join([f"`{cmd}`: {desc}" for cmd, desc in commands_list.items()])
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

    @suspiciousmonitor.command(name="clearresponse")
    @commands.has_permissions(administrator=True)
    async def clearresponse(self, ctx, user: discord.User):
        """
        Clear a specific user's response so they can resubmit.
        """
        async with self.config.guild(ctx.guild).user_responses() as user_responses:
            if str(user.id) in user_responses:
                del user_responses[str(user.id)]
                await ctx.send(f"Response for {user} has been cleared. They can now resubmit.")
            else:
                await ctx.send(f"No response found for {user}.")
