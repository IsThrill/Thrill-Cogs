import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from datetime import datetime, timedelta
import pytz  # Import pytz for timezone conversion

class BanReasonModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title="Ban Reason")
        self.member = member

        # Text input for ban reason
        self.reason = discord.ui.TextInput(
            label="Ban Reason", placeholder="Enter the reason for banning the user...", style=discord.TextStyle.long
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value
        try:
            # Ban the member with the reason provided
            await self.member.ban(reason=reason)
            await interaction.response.send_message(f"User {self.member} has been banned for: {reason}", ephemeral=True)
            
            # Send DM with the reason
            try:
                await self.member.send(f"You've been banned from A New Beginning. Reason: {reason}")
            except discord.Forbidden:
                pass

        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to ban this user.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to ban the user.", ephemeral=True)

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
            "test_mode": False,
            "user_responses": {},  # To track user responses
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        settings = await self.config.guild(guild).all()

        if not (settings["suspicious_role"] and settings["staff_role"] and settings["questionnaire_channel"]):
            return

        # If test mode is enabled, treat all users as suspicious
        if settings["test_mode"]:
            account_age = timedelta(days=0)  # Fake account age to bypass the 3-month check
        else:
            account_age = datetime.now(pytz.utc) - member.created_at  # Get UTC time and calculate age

        # Convert account creation date to EST
        est_tz = pytz.timezone("US/Eastern")
        account_creation_est = member.created_at.astimezone(est_tz)

        if account_age.days < 90 or settings["test_mode"]:  # If account is younger than 3 months or in test mode
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
            embed.add_field(name="User ID", value=f"<@{member.id}>", inline=True)  # Clickable User ID
            embed.add_field(name="Account Creation Date (EST)", value=account_creation_est.strftime("%Y-%m-%d %H:%M:%S %Z"), inline=True)  # Formatted in EST

            view = discord.ui.View()

            # Create button instances
            mark_suspicious_button = discord.ui.Button(label="Mark as Suspicious", style=discord.ButtonStyle.danger)
            async def mark_suspicious(interaction: discord.Interaction):
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
                            "``\n"
                            "- How did you find A New Beginning?\n"
                            "- IF by a friend/source (What source did you use?)\n"
                            "- IF by a friend, what was their name? (Discord, VRC, Etc)\n"
                            "- IF you've had a previous Discord account what was your Previous Discord Account?\n"
                            "``\n"
                            "If you do not respond to these within the 10-minute deadline, you will be automatically removed from Discord.\n\n"
                            "Hope to hear back from you soon!"
                        )
                    except discord.Forbidden:
                        pass

                    await interaction.response.send_message("User marked as suspicious and notified.", ephemeral=True)

            mark_suspicious_button.callback = mark_suspicious

            verify_safe_button = discord.ui.Button(label="Verify as Safe", style=discord.ButtonStyle.success)
            async def verify_safe(interaction: discord.Interaction):
                if interaction.user.guild_permissions.manage_roles:
                    # Verify and reinstate roles
                    async with self.config.guild(guild).suspicious_users() as suspicious_users:
                        previous_roles = suspicious_users.pop(str(member.id), [])

                    await member.remove_roles(suspicious_role, reason="Verified as safe")
                    await member.add_roles(*[guild.get_role(rid) for rid in previous_roles if guild.get_role(rid)], reason="Verified as safe")

                    # Send DM to the user confirming their safe status
                    try:
                        await member.send(
                            "**Approved**\n"
                            "Thank you for your confirmation, we've gone ahead and re-instated your roles, and given your access back into the discord server."
                        )
                    except discord.Forbidden:
                        pass

                    await interaction.response.send_message("User verified as safe and roles restored.", ephemeral=True)

            verify_safe_button.callback = verify_safe

            # Add buttons to the view
            view.add_item(mark_suspicious_button)
            view.add_item(verify_safe_button)

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

        # Prevent multiple responses from the same user after being marked suspicious
        if str(message.author.id) in settings["suspicious_users"]:
            # If the user already responded, ignore further messages
            if message.author.id in settings["user_responses"]:
                await message.author.send("You have already submitted your response. You cannot send further messages.")
                return  # Ignore further messages from this user

            # Save the user's response
            async with self.config.guild(guild).user_responses() as user_responses:
                user_responses[str(message.author.id)] = message.content

            # Send the response to the alert channel
            if alert_channel:
                embed = discord.Embed(
                    title="Suspicious User Response",
                    description=message.content,
                    color=discord.Color.blue()
                )
                embed.set_author(name=str(message.author), icon_url=message.author.avatar.url)
                embed.add_field(name="User ID", value=f"<@{message.author.id}> (`{message.author.id}`)", inline=False)  # Clickable User ID

                # Add a Ban button to the embed
                ban_button = discord.ui.Button(label="Ban User", style=discord.ButtonStyle.danger)

                async def ban_user(interaction: discord.Interaction):
                    if interaction.user.guild_permissions.ban_members:
                        # Ensure the user is a member in the guild (check interaction.guild)
                        member = interaction.guild.get_member(message.author.id)  # Use interaction.guild instead of message.guild
                        if member:
                            # Prompt for ban reason
                            await interaction.response.send_modal(BanReasonModal(member))
                        else:
                            await interaction.response.send_message("User is no longer a member of the server.", ephemeral=True)

                ban_button.callback = ban_user

                view = discord.ui.View()
                view.add_item(ban_button)

                await alert_channel.send(embed=embed, view=view)

            await message.author.send("Your response has been submitted.")

    @commands.group(name="sus", aliases=["Sus"], invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def suspiciousmonitor(self, ctx):
        """Manage suspicious user monitoring."""
        commands_list = {
            "sus setrole": "Set the suspicious role for marking suspicious users.",
            "sus setstaff": "Set the staff role to be pinged in alerts.",
            "sus setchannel": "Set the channel for posting suspicious user alerts.",
            "sus test": "Enable/Disable test mode where all new users are treated as suspicious.",
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
        """Set the suspicious role."""
        await self.config.guild(ctx.guild).suspicious_role.set(role.id)
        await ctx.send(f"Suspicious role set to {role.mention}.")

    @suspiciousmonitor.command(name="setstaff")
    @commands.has_permissions(administrator=True)
    async def setstaff(self, ctx, role: discord.Role):
        """Set the staff role to ping."""
        await self.config.guild(ctx.guild).staff_role.set(role.id)
        await ctx.send(f"Staff role set to {role.mention}.")

    @suspiciousmonitor.command(name="setchannel")
    @commands.has_permissions(administrator=True)
    async def setchannel(self, ctx, channel: discord.TextChannel):
        """Set the questionnaire channel."""
        await self.config.guild(ctx.guild).questionnaire_channel.set(channel.id)
        await ctx.send(f"Questionnaire channel set to {channel.mention}.")

    @suspiciousmonitor.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test(self, ctx):
        """Toggle the test mode."""
        settings = await self.config.guild(ctx.guild).all()
        test_mode = not settings["test_mode"]
        await self.config.guild(ctx.guild).test_mode.set(test_mode)
        status = "enabled" if test_mode else "disabled"
        await ctx.send(f"Test mode has been {status}. All new members will now be treated as suspicious." if test_mode else "Test mode has been disabled.")
