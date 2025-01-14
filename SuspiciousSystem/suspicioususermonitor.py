import discord
from discord.ui import Modal, TextInput, Button, View
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
            try:
                await self.member.send(f"You've been banned from the server. Reason: {reason}")
            except discord.Forbidden:
                guild = interaction.guild
                staff_channel_id = await Config.get_conf(None, identifier=1234567890).guild(guild).questionnaire_channel()
                staff_channel = guild.get_channel(staff_channel_id)
                if staff_channel:
                    await staff_channel.send(f"Failed to DM <@{self.member.id}> the ban reason. Proceeding with the ban.")
            
            await self.member.ban(reason=reason)
            await interaction.response.send_message(f"User {self.member} has been banned for: {reason}", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to ban this user.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to ban the user.", ephemeral=True)

class StaffReplyModal(Modal):
    def __init__(self, member: discord.Member, config: Config):
        super().__init__(title="Staff Reply")
        self.member = member
        self.config = config  
        self.reply = TextInput(
            label="Your Reply",
            placeholder="Enter your reply to the user...",
            style=discord.TextStyle.long,
        )
        self.add_item(self.reply)

    async def on_submit(self, interaction: discord.Interaction):
        reply_content = self.reply.value
        try:
            # Send the reply to the user as an embedded message
            embed = discord.Embed(
                title="**Staff Reply**",
                description=reply_content,
                color=discord.Color.green(),
            )
            embed.set_author(name=str(interaction.user), icon_url=interaction.user.avatar.url)
            await self.member.send(embed=embed)
            await interaction.response.send_message(f"Staff reply sent to {self.member}.", ephemeral=True)
            
            # Clear previous response so the user can not resubmit
            guild = interaction.guild
            settings = await self.config.guild(guild).all()
            async with self.config.guild(guild).user_responses() as user_responses:
                if str(self.member.id) in user_responses:
                    del user_responses[str(self.member.id)]
                    
        except discord.Forbidden:
            await interaction.response.send_message("Unable to send a reply. The user has DMs disabled.", ephemeral=True)

class SuspiciousUserMonitor(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        default_guild = {
            "suspicious_role": None,
            "questionnaire_channel": None,
            "suspicious_users": {},
            "test_mode": False,
            "user_responses": {},
            "min_account_age": 90,
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await self.config.guild(guild).all()

        if not (settings["suspicious_role"] and settings["questionnaire_channel"]):
            return

        account_age = datetime.now(pytz.utc) - member.created_at if not settings["test_mode"] else timedelta(days=0)
        est_tz = pytz.timezone("US/Eastern")
        account_creation_est = member.created_at.astimezone(est_tz)

        if account_age.days < settings["min_account_age"] or settings["test_mode"]:
            suspicious_role = guild.get_role(settings["suspicious_role"])
            if not (suspicious_role):
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
                    # Ensure the suspicious role exists
                    suspicious_role = interaction.guild.get_role(settings["suspicious_role"])
                    if not suspicious_role:
                        await interaction.response.send_message("Suspicious role is not set.", ephemeral=True)
                        return
            
                    # Remove all roles except the default and suspicious role
                    roles_to_remove = [role for role in member.roles if role != interaction.guild.default_role and role != suspicious_role]
                    await member.remove_roles(*roles_to_remove, reason="Marked as suspicious")
            
                    # Store the previous roles in the config (optional, for later restoration)
                    previous_roles = [role.id for role in roles_to_remove]
                    async with self.config.guild(interaction.guild).suspicious_users() as suspicious_users:
                        suspicious_users[str(member.id)] = previous_roles
                    
                    # Add the suspicious role
                    await member.add_roles(suspicious_role, reason="Marked as suspicious")
            
                    # Send the message and notify the user
                    try:
                        await member.send("Hey there, you've been automatically assigned and put into a suspicious category before we can continue your entry into the Discord. Please answer the questionnaire I've provided.\n\n"
                                          "1. How did you find A New Beginning?\n"
                                          "2. If by a friend/source (What source did you use?)\n"
                                          "3. If by a friend, what was their name? (Discord, VRC, Etc.)\n"
                                          "4. If you've had a previous Discord account, what was your Previous Discord Account?\n\n"
                                          "If you do not respond to these within the 10-minute deadline, you will be automatically removed from Discord.")
                    except discord.Forbidden:
                        staff_channel = guild.get_channel(settings["questionnaire_channel"])
                        if staff_channel:
                            await staff_channel.send(f"Failed to send a DM to <@{member.id}>.")
            
                    await interaction.response.send_message("User marked as suspicious and notified.", ephemeral=True)


            mark_suspicious_button.callback = mark_suspicious

            verify_safe_button = discord.ui.Button(label="Verify as Safe", style=discord.ButtonStyle.success)
            
            async def verify_safe(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    # Retrieve the target member from the interaction context (the suspicious member)
                    embed = interaction.message.embeds[0]
                    member_id = int(embed.description.split(" ")[0][2:-1])  # Extract target member from embed
                    target_member = interaction.guild.get_member(member_id)
            
                    if not target_member:
                        await interaction.response.send_message("Unable to find the member in the guild. They may have left.", ephemeral=True)
                        return
            
                    # Get the suspicious role from the settings
                    settings = await self.config.guild(interaction.guild).all()
                    suspicious_role = interaction.guild.get_role(settings["suspicious_role"])
            
                    if not suspicious_role:
                        await interaction.response.send_message("Suspicious role is not set in the server.", ephemeral=True)
                        return
            
                    # Check if the target member has the suspicious role
                    if suspicious_role not in target_member.roles:
                        await interaction.response.send_message("The user has not been marked as suspicious.", ephemeral=True)
                        return
            
                    # Proceed with verifying the user as safe and removing the suspicious role
                    async with self.config.guild(interaction.guild).suspicious_users() as suspicious_users:
                        previous_roles = suspicious_users.pop(str(target_member.id), [])
            
                    # Remove suspicious role and restore previous roles
                    await target_member.remove_roles(suspicious_role, reason="Verified as safe")
                    await target_member.add_roles(
                        *[interaction.guild.get_role(rid) for rid in previous_roles if interaction.guild.get_role(rid)],
                        reason="Verified as safe",
                    )
            
                    # Try sending a DM to the user about the verification
                    try:
                        await target_member.send("**Approved**\nThank you for your confirmation. Your roles have been restored.")
                    except discord.Forbidden:
                        pass
            
                    await interaction.response.send_message("User verified as safe and roles restored.", ephemeral=True)

            verify_safe_button.callback = verify_safe

            view.add_item(mark_suspicious_button)
            view.add_item(verify_safe_button)

            alert_channel = guild.get_channel(settings["questionnaire_channel"])
            if alert_channel:
                staff_ping = "@everyone" if not settings["test_mode"] else ""
                await alert_channel.send(content=staff_ping, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(everyone=True))


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
                    return  

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

                    ban_button = Button(label="Ban User", style=discord.ButtonStyle.danger)
                    staff_reply_button = Button(label="Staff Reply", style=discord.ButtonStyle.primary)

                    # Ban user callback
                    async def ban_user(interaction: discord.Interaction):
                        if interaction.user.guild_permissions.ban_members:
                            member = interaction.guild.get_member(message.author.id)
                            if member:
                                await interaction.response.send_modal(BanReasonModal(member))
                            else:
                                await interaction.response.send_message("User is no longer a member of the server or hasn't finished onboarding.", ephemeral=True)

                    ban_button.callback = ban_user

                    # Staff reply callback
                    async def staff_reply(interaction: discord.Interaction):
                        if interaction.user.guild_permissions.manage_roles:
                            member = interaction.guild.get_member(message.author.id)
                            if member:
                                await interaction.response.send_modal(StaffReplyModal(member, self.config))  # Pass config here
                            else:
                                await interaction.response.send_message("User is no longer a member of the server or hasn't finished onboarding.", ephemeral=True)

                    staff_reply_button.callback = staff_reply

                    view = View()
                    view.add_item(ban_button)
                    view.add_item(staff_reply_button)

                    staff_ping = "<@everyone>" if not settings["test_mode"] else ""
                    await alert_channel.send(content=staff_ping, embed=embed, view=view)

                await message.author.send("Your response has been submitted.")

    @commands.group(name="sus", invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def suspiciousmonitor(self, ctx):
        commands_list = {
            "sus setrole": "Set the suspicious role.",
            "sus config": "Shows the servers current configuration",
            "sus setchannel": "Set the alert channel.",
            "sus test": "Toggle test mode.",
            "sus clearresponse": "Clear a user's response so they can resubmit.",
            "sus setage": "Set the minimum account age for alerting staff.",
        }
        description = "\n".join([f"{cmd}: {desc}" for cmd, desc in commands_list.items()])
        embed = discord.Embed(
            title="Suspicious Monitor Commands",
            description=description,
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

    @suspiciousmonitor.command(name="config")
    @commands.has_permissions(administrator=True)
    async def config(self, ctx):
        """
        Show the current server's configuration.
        """
        settings = await self.config.guild(ctx.guild).all()

        suspicious_role = ctx.guild.get_role(settings["suspicious_role"]) if settings["suspicious_role"] else "None"
        questionnaire_channel = ctx.guild.get_channel(settings["questionnaire_channel"]) if settings["questionnaire_channel"] else "None"
        min_account_age = settings["min_account_age"]
        test_mode = "Enabled" if settings["test_mode"] else "Disabled"

        embed = discord.Embed(
            title="Current Server Configuration",
            color=discord.Color.green(),
        )
        embed.add_field(name="Suspicious Role", value=suspicious_role, inline=False)
        embed.add_field(name="Questionnaire Channel", value=questionnaire_channel, inline=False)
        embed.add_field(name="Minimum Account Age", value=f"{min_account_age} days", inline=False)
        embed.add_field(name="Test Mode", value=test_mode, inline=False)

        await ctx.send(embed=embed)

    @suspiciousmonitor.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def setrole(self, ctx, role: discord.Role):
        """
        Sets the suspicious role.
        """
        await self.config.guild(ctx.guild).suspicious_role.set(role.id)
        await ctx.send(f"Suspicious role set to {role.mention}.")


    @suspiciousmonitor.command(name="setchannel")
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """
        Sets the alert channel for staff to view. 
        """
        await self.config.guild(ctx.guild).questionnaire_channel.set(channel.id)
        await ctx.send(f"Questionnaire channel set to {channel.mention}.")

    @suspiciousmonitor.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx):
        """
        Enable testing mode. 
        """
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

    @suspiciousmonitor.command(name="setage")
    @commands.has_permissions(administrator=True)
    async def setage(self, ctx, days: int):
        """
        Set the minimum account age (in days) required before users are flagged as suspicious.
        """
        await self.config.guild(ctx.guild).min_account_age.set(days)
        await ctx.send(f"Minimum account age set to {days} days.")
