import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from datetime import datetime, timedelta
import pytz
import asyncio
import re
import string


class QuestionnaireModal(Modal):
    """Modal for collecting user responses to questionnaire."""
    def __init__(self, cog, guild_id: int, user_id: int, questions: list):
        super().__init__(title="Security Questionnaire", timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.questions = questions
        self.text_inputs = []
        
        # Add up to 5 questions (Discord modal limit)
        for i, question in enumerate(questions[:5]):
            text_input = TextInput(
                label=question[:45],  # Discord label character limit
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=500,
                placeholder=question if len(question) > 45 else None
            )
            self.text_inputs.append(text_input)
            self.add_item(text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Cancel the timeout task and remove from pending - consistent approach
        task_id = f"{self.guild_id}_{self.user_id}"
        ticket_channel_id = None
        
        async with self.cog.config.guild_from_id(self.guild_id).pending_questionnaires() as pending:
            if str(self.user_id) in pending:
                ticket_channel_id = pending[str(self.user_id)].get("ticket_channel_id")
                del pending[str(self.user_id)]
        
        # Cancel timeout task using consistent task_id format
        if task_id in self.cog.timeout_tasks:
            self.cog.timeout_tasks[task_id].cancel()
            del self.cog.timeout_tasks[task_id]
        
        # Send responses to review channel
        guild = self.cog.bot.get_guild(self.guild_id)
        if not guild:
            return
        
        settings = await self.cog.config.guild(guild).all()
        alert_channel_id = settings.get("alert_channel")
        
        if not alert_channel_id:
            await interaction.followup.send("Error: Alert/Review channel not configured.", ephemeral=True)
            return
        
        review_channel = guild.get_channel(alert_channel_id)
        if not review_channel:
            await interaction.followup.send("Error: Review channel not found.", ephemeral=True)
            return
        
        member = guild.get_member(self.user_id)
        if not member:
            await interaction.followup.send("Error: Member not found in guild.", ephemeral=True)
            return
        
        # Create embed with responses
        embed = discord.Embed(
            title="Questionnaire Responses",
            description=f"User: {member.mention} ({member.name})",
            color=discord.Color.blue(),
            timestamp=datetime.now(pytz.utc)
        )
        embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
        
        # Add each question and answer
        for i, (question, text_input) in enumerate(zip(self.questions, self.text_inputs), 1):
            # Sanitize user input to prevent any weird behavior
            answer = text_input.value[:1000]  # Cap length
            embed.add_field(name=f"{i}. {question}", value=answer, inline=False)
        
        # Always set thumbnail (display_avatar is always present)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Create view with proper member_id encoded in custom_id
        view = QuestionnaireReviewView(self.cog)
        
        try:
            # Send with no allowed mentions to prevent any edge case pings
            await review_channel.send(
                embed=embed, 
                view=view,
                allowed_mentions=discord.AllowedMentions.none()
            )
            await interaction.followup.send(
                "✅ Thank you for completing the questionnaire! Staff will review your responses shortly.",
                ephemeral=True
            )
            
            # Delete ticket channel if it exists
            if ticket_channel_id:
                ticket_channel = guild.get_channel(ticket_channel_id)
                if ticket_channel:
                    try:
                        await ticket_channel.delete(reason="Questionnaire completed")
                    except discord.Forbidden:
                        pass
                    except Exception:
                        pass
                    
        except Exception as e:
            print(f"Error sending questionnaire review: {e}")
            await interaction.followup.send("An error occurred. Please contact staff.", ephemeral=True)


class QuestionnaireButton(View):
    """Button view for starting the questionnaire - with proper persistence and DM support."""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(
        label="Start Questionnaire",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="questionnaire_start_persistent"
    )
    async def start_questionnaire_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Handle DM context - parse guild_id from embed footer
        guild = interaction.guild
        guild_id = None
        user_id = interaction.user.id
        
        if guild is None:  # We're in DM
            # Parse guild_id from the embed footer
            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text:
                    # Footer format: "Guild ID: 123456789"
                    match = re.search(r'Guild ID: (\d+)', embed.footer.text)
                    if match:
                        guild_id = int(match.group(1))
                        guild = self.cog.bot.get_guild(guild_id)
            
            if not guild:
                await interaction.response.send_message(
                    "Error: Could not determine which server this questionnaire is for.", 
                    ephemeral=True
                )
                return
        else:
            # We're in a guild channel (ticket)
            guild_id = guild.id
            # Find the member this ticket is for by checking overwrites
            target_member = None
            channel = interaction.channel
            
            if hasattr(channel, 'overwrites'):
                for target, overwrite in channel.overwrites.items():
                    if isinstance(target, discord.Member) and target != guild.me:
                        if overwrite.read_messages and overwrite.send_messages:
                            target_member = target
                            break
            
            if not target_member:
                # Fallback: check if the interaction user has a pending questionnaire
                async with self.cog.config.guild(guild).pending_questionnaires() as pending:
                    if str(interaction.user.id) in pending:
                        target_member = interaction.user
            
            if target_member and interaction.user.id != target_member.id:
                await interaction.response.send_message(
                    "This questionnaire is not for you.", 
                    ephemeral=True
                )
                return
            
            if target_member:
                user_id = target_member.id
        
        # Get questions from config
        questions = await self.cog.config.guild(guild).questionnaire_questions()
        
        if not questions:
            await interaction.response.send_message(
                "No questionnaire questions configured. Please contact staff.",
                ephemeral=True
            )
            return
        
        # Show the modal
        modal = QuestionnaireModal(self.cog, guild_id, user_id, questions)
        await interaction.response.send_modal(modal)


class QuestionnaireReviewView(View):
    """Stateless view for staff to review questionnaire responses."""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(
        label="Verify Safe",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="questionnaire_verify_persistent"
    )
    async def verify_safe(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract member_id from the embed
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if not embed:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        # Parse User ID from the embed field - improved regex parsing
        member_id = None
        for field in embed.fields:
            if field.name == "User ID":
                # Extract ID using regex to be more robust
                match = re.search(r'\d{15,20}', field.value)
                if match:
                    member_id = int(match.group())
                    break
        
        if not member_id:
            return await interaction.response.send_message("Error: Could not determine user ID.", ephemeral=True)
        
        # Check permissions
        if not await self._check_staff_permission(interaction, "manage_roles"):
            return await interaction.response.send_message(
                "You don't have permission to verify users.",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        member = interaction.guild.get_member(member_id)
        if not member:
            return await interaction.followup.send("Member not found in the guild.", ephemeral=True)
        
        # Cancel any pending timeout tasks - use consistent task_id format
        task_id = f"{interaction.guild.id}_{member_id}"
        if task_id in self.cog.timeout_tasks:
            self.cog.timeout_tasks[task_id].cancel()
            del self.cog.timeout_tasks[task_id]
        
        # Remove from pending questionnaires and get ticket channel ID
        ticket_channel_id = None
        async with self.cog.config.guild(interaction.guild).pending_questionnaires() as pending:
            if str(member_id) in pending:
                ticket_channel_id = pending[str(member_id)].get("ticket_channel_id")
                del pending[str(member_id)]
        
        # Delete ticket channel if it exists
        if ticket_channel_id:
            ticket_channel = interaction.guild.get_channel(ticket_channel_id)
            if ticket_channel:
                try:
                    await ticket_channel.delete(reason="User verified safe by staff")
                except Exception:
                    pass
        
        # Check bot permissions before attempting role changes
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.followup.send("I don't have permission to manage roles.", ephemeral=True)
        
        # Restore saved roles
        saved_role_ids = await self.cog.config.member(member).saved_roles()
        if saved_role_ids:
            roles_to_add = []
            for rid in saved_role_ids:
                role = interaction.guild.get_role(rid)
                if role and role < interaction.guild.me.top_role and not role.managed:
                    roles_to_add.append(role)
            
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add, reason="Verified safe by staff")
                except discord.Forbidden:
                    pass
                except Exception:
                    pass
        
        # Remove suspicious role
        suspicious_role_id = await self.cog.config.guild(interaction.guild).suspicious_role()
        if suspicious_role_id:
            suspicious_role = interaction.guild.get_role(suspicious_role_id)
            if suspicious_role and suspicious_role in member.roles:
                if suspicious_role < interaction.guild.me.top_role:
                    try:
                        await member.remove_roles(suspicious_role, reason="Verified safe by staff")
                    except discord.Forbidden:
                        pass
                    except Exception:
                        pass
        
        # Clear saved roles
        await self.cog.config.member(member).saved_roles.set([])
        
        # Update the embed
        embed.color = discord.Color.green()
        embed.add_field(name="✅ Status", value=f"Verified safe by {interaction.user.mention}", inline=False)
        
        # Disable all buttons - fixed: use self.children not self.view.children
        for item in self.children:
            item.disabled = True
        
        await interaction.followup.send(f"✅ {member.mention} has been verified as safe.", ephemeral=True)
        await interaction.message.edit(embed=embed, view=self)
    
    @discord.ui.button(
        label="Ban",
        style=discord.ButtonStyle.danger,
        emoji="🔨",
        custom_id="questionnaire_ban_persistent"
    )
    async def questionnaire_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract member_id from the embed
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if not embed:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        # Parse User ID from the embed field - improved regex parsing
        member_id = None
        for field in embed.fields:
            if field.name == "User ID":
                match = re.search(r'\d{15,20}', field.value)
                if match:
                    member_id = int(match.group())
                    break
        
        if not member_id:
            return await interaction.response.send_message("Error: Could not determine user ID.", ephemeral=True)
        
        # Check permissions - must have ban_members or staff role
        if not await self._check_staff_permission(interaction, "ban_members"):
            return await interaction.response.send_message(
                "You don't have permission to ban users.",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        member = interaction.guild.get_member(member_id)
        if not member:
            return await interaction.followup.send("Member not found in the guild.", ephemeral=True)
        
        # Pre-check bot permissions and hierarchy
        if not interaction.guild.me.guild_permissions.ban_members:
            return await interaction.followup.send("I don't have permission to ban members.", ephemeral=True)
        
        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.followup.send("I cannot ban this user due to role hierarchy.", ephemeral=True)
        
        if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("You cannot ban this user due to role hierarchy.", ephemeral=True)
        
        # Cancel any pending timeout tasks
        task_id = f"{interaction.guild.id}_{member_id}"
        if task_id in self.cog.timeout_tasks:
            self.cog.timeout_tasks[task_id].cancel()
            del self.cog.timeout_tasks[task_id]
        
        # Remove from pending questionnaires and get ticket channel
        ticket_channel_id = None
        async with self.cog.config.guild(interaction.guild).pending_questionnaires() as pending:
            if str(member_id) in pending:
                ticket_channel_id = pending[str(member_id)].get("ticket_channel_id")
                del pending[str(member_id)]
        
        # Clear saved roles before ban
        await self.cog.config.member(member).saved_roles.set([])
        
        try:
            await member.ban(reason=f"Failed questionnaire - Banned by {interaction.user}")
            
            # Delete ticket channel if it exists
            if ticket_channel_id:
                ticket_channel = interaction.guild.get_channel(ticket_channel_id)
                if ticket_channel:
                    try:
                        await ticket_channel.delete(reason="User banned")
                    except Exception:
                        pass
            
            # Update embed
            embed.color = discord.Color.red()
            embed.add_field(name="🔨 Status", value=f"Banned by {interaction.user.mention}", inline=False)
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.followup.send(f"🔨 {member.mention} has been banned.", ephemeral=True)
            await interaction.message.edit(embed=embed, view=self)
            
        except discord.Forbidden:
            await interaction.followup.send("Failed to ban user - insufficient permissions.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
    
    async def _check_staff_permission(self, interaction: discord.Interaction, fallback_perm: str) -> bool:
        """Check if user has staff role or fallback permission."""
        # Check guild permission first
        if getattr(interaction.user.guild_permissions, fallback_perm):
            return True
        
        # Check staff role
        settings = await self.cog.config.guild(interaction.guild).all()
        staff_role_id = settings.get("staff_role")
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role and staff_role in interaction.user.roles:
                return True
        
        return False


class SuspiciousUserView(View):
    """Stateless view for handling suspicious user alerts."""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(
        label="Verify Safe",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="suspicious_verify_persistent"
    )
    async def verify_safe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract member_id from the embed
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if not embed:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        # Parse User ID from the embed field - improved regex parsing
        member_id = None
        for field in embed.fields:
            if field.name == "User ID":
                match = re.search(r'\d{15,20}', field.value)
                if match:
                    member_id = int(match.group())
                    break
        
        if not member_id:
            return await interaction.response.send_message("Error: Could not determine user ID.", ephemeral=True)
        
        # Check permissions
        if not await self._check_staff_permission(interaction, "manage_roles"):
            return await interaction.response.send_message(
                "You don't have permission to verify users.",
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        member = interaction.guild.get_member(member_id)
        if not member:
            return await interaction.followup.send("Member not found in the guild.", ephemeral=True)
        
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.followup.send("I don't have permission to manage roles.", ephemeral=True)
        
        # Cancel any pending timeout tasks
        task_id = f"{interaction.guild.id}_{member_id}"
        if task_id in self.cog.timeout_tasks:
            self.cog.timeout_tasks[task_id].cancel()
            del self.cog.timeout_tasks[task_id]
        
        # Remove from pending questionnaires and get ticket channel
        ticket_channel_id = None
        async with self.cog.config.guild(interaction.guild).pending_questionnaires() as pending:
            if str(member_id) in pending:
                ticket_channel_id = pending[str(member_id)].get("ticket_channel_id")
                del pending[str(member_id)]
        
        # Delete ticket channel if it exists
        if ticket_channel_id:
            ticket_channel = interaction.guild.get_channel(ticket_channel_id)
            if ticket_channel:
                try:
                    await ticket_channel.delete(reason="User verified safe by staff")
                except Exception:
                    pass
        
        # Restore saved roles
        saved_role_ids = await self.cog.config.member(member).saved_roles()
        if saved_role_ids:
            roles_to_add = []
            for rid in saved_role_ids:
                role = interaction.guild.get_role(rid)
                if role and role < interaction.guild.me.top_role and not role.managed:
                    roles_to_add.append(role)
            
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add, reason="Verified safe by staff")
                except discord.Forbidden:
                    pass
                except Exception:
                    pass
        
        # Remove suspicious role
        suspicious_role_id = await self.cog.config.guild(interaction.guild).suspicious_role()
        if suspicious_role_id:
            suspicious_role = interaction.guild.get_role(suspicious_role_id)
            if suspicious_role and suspicious_role in member.roles:
                if suspicious_role < interaction.guild.me.top_role:
                    try:
                        await member.remove_roles(suspicious_role, reason="Verified safe by staff")
                    except discord.Forbidden:
                        pass
                    except Exception:
                        pass
        
        # Clear saved roles
        await self.cog.config.member(member).saved_roles.set([])
        
        # Update the embed
        embed.color = discord.Color.green()
        embed.add_field(name="✅ Status", value=f"Verified safe by {interaction.user.mention}", inline=False)
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.followup.send(f"✅ {member.mention} has been verified as safe.", ephemeral=True)
        await interaction.message.edit(embed=embed, view=self)
        
    @discord.ui.button(
        label="Send Questionnaire",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="suspicious_questionnaire_persistent"
    )
    async def send_questionnaire_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Extract member_id from the embed
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if not embed:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        # Parse User ID from the embed field - improved regex parsing
        member_id = None
        for field in embed.fields:
            if field.name == "User ID":
                match = re.search(r'\d{15,20}', field.value)
                if match:
                    member_id = int(match.group())
                    break
        
        if not member_id:
            return await interaction.response.send_message("Error: Could not determine user ID.", ephemeral=True)
        
        # Check permissions
        if not await self._check_staff_permission(interaction, "manage_roles"):
            return await interaction.response.send_message(
                "You don't have permission to send questionnaires.",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        member = interaction.guild.get_member(member_id)
        if not member:
            return await interaction.followup.send("Member not found in the guild.", ephemeral=True)
        
        result = await self.cog.send_questionnaire(interaction.guild, member)
        await interaction.followup.send(result["message"], ephemeral=True)
        
        if result["success"]:
            # Update the embed
            embed.add_field(name="📝 Questionnaire", value=f"Sent by {interaction.user.mention}", inline=False)
            
            # Disable the questionnaire button
            for item in self.children:
                if hasattr(item, 'label') and item.label == "Send Questionnaire":
                    item.disabled = True
            
            await interaction.message.edit(embed=embed, view=self)
    
    async def _check_staff_permission(self, interaction: discord.Interaction, fallback_perm: str) -> bool:
        """Check if user has staff role or fallback permission."""
        # Check guild permission first
        if getattr(interaction.user.guild_permissions, fallback_perm):
            return True
        
        # Check staff role
        settings = await self.cog.config.guild(interaction.guild).all()
        staff_role_id = settings.get("staff_role")
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role and staff_role in interaction.user.roles:
                return True
        
        return False


class SuspiciousUserMonitor(commands.Cog):
    """Monitor and handle suspicious users with questionnaires."""
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.config.register_guild(
            suspicious_role=None,
            alert_channel=None,
            ticket_category=None,
            mention_role=None,
            staff_role=None,
            min_account_age=7,
            questionnaire_questions=[],
            pending_questionnaires={}
        )
        self.config.register_member(
            saved_roles=[]
        )
        self.timeout_tasks = {}
        self.sus_group = None
    
    async def cog_load(self):
        """Called when the cog is loaded."""
        # Register persistent views (stateless)
        self.bot.add_view(QuestionnaireReviewView(self))
        self.bot.add_view(SuspiciousUserView(self))
        self.bot.add_view(QuestionnaireButton(self))
        
        # Add slash commands to the tree
        if not self.sus_group:
            self.sus_group = self._create_sus_group()
        self.bot.tree.add_command(self.sus_group)
        
        # Rehydrate timeout tasks
        await self.rehydrate_timeout_tasks()
    
    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        # Cancel all timeout tasks
        for task in self.timeout_tasks.values():
            task.cancel()
        self.timeout_tasks.clear()
        
        # Remove slash commands from tree
        if self.sus_group:
            self.bot.tree.remove_command("sus")
    
    async def rehydrate_timeout_tasks(self):
        """Restore timeout tasks for pending questionnaires after bot restart."""
        all_guilds = await self.config.all_guilds()
        
        for guild_id_raw, guild_data in all_guilds.items():
            # Ensure guild_id is an integer
            guild_id = int(guild_id_raw) if isinstance(guild_id_raw, str) else guild_id_raw
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
                
            pending = guild_data.get("pending_questionnaires", {})
            
            for user_id_str, questionnaire_data in pending.items():
                try:
                    user_id = int(user_id_str)
                    member = guild.get_member(user_id)
                    if not member:
                        # Clean up orphaned entry
                        async with self.config.guild(guild).pending_questionnaires() as p:
                            if user_id_str in p:
                                del p[user_id_str]
                        continue
                    
                    sent_at = questionnaire_data.get("sent_at")
                    if not sent_at:
                        continue
                    
                    # Calculate remaining time (24 hours from sent_at)
                    sent_time = datetime.fromisoformat(sent_at)
                    elapsed = datetime.now(pytz.utc) - sent_time
                    remaining = timedelta(hours=24) - elapsed
                    
                    if remaining.total_seconds() > 0:
                        # Recreate the timeout task with consistent task_id
                        task_id = f"{guild_id}_{user_id}"
                        self.timeout_tasks[task_id] = asyncio.create_task(
                            self.timeout_questionnaire(guild, member, remaining.total_seconds())
                        )
                    else:
                        # Timeout has already passed, kick the user
                        await self.handle_timeout_kick(guild, member)
                        
                except (ValueError, KeyError, TypeError) as e:
                    print(f"Error rehydrating task for {user_id_str}: {e}")
                    continue
    
    def slugify_channel_name(self, name: str) -> str:
        """Convert a name to a valid Discord channel name (a-z, 0-9, hyphens only)."""
        # Remove all non-alphanumeric characters except spaces and hyphens
        name = re.sub(r'[^\w\s-]', '', name.lower())
        # Replace spaces with hyphens
        name = re.sub(r'[\s]+', '-', name)
        # Remove consecutive hyphens
        name = re.sub(r'-+', '-', name)
        # Remove leading/trailing hyphens
        name = name.strip('-')
        # Ensure it only contains allowed characters
        allowed = set(string.ascii_lowercase + string.digits + '-')
        name = ''.join(c for c in name if c in allowed)
        # Cap at 100 characters (Discord limit)
        if len(name) > 100:
            name = name[:100]
        # Ensure we have a valid name
        return name if name else 'suspicious-user'
    
    async def has_staff_role(self, interaction: discord.Interaction) -> bool:
        """Check if a user has the staff role or manage_roles permission."""
        if interaction.user.guild_permissions.manage_roles:
            return True
        
        staff_role_id = await self.config.guild(interaction.guild).staff_role()
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role and staff_role in interaction.user.roles:
                return True
        
        return False
    
    async def send_questionnaire_dm(self, member: discord.Member, guild: discord.Guild) -> bool:
        """Try to send questionnaire via DM. Returns True if successful, False otherwise."""
        try:
            questions = await self.config.guild(guild).questionnaire_questions()
            if not questions:
                return False
            
            embed = discord.Embed(
                title="Security Questionnaire Required",
                description=(
                    f"Hello! You've been flagged for additional security verification in **{guild.name}**.\n\n"
                    "Please complete this questionnaire within **24 hours** or you will be removed from the server.\n\n"
                    "Click the button below to start."
                ),
                color=discord.Color.orange()
            )
            # Add guild ID to footer for DM context
            embed.set_footer(text=f"Guild ID: {guild.id}")
            
            view = QuestionnaireButton(self)
            await member.send(embed=embed, view=view)
            return True
            
        except discord.Forbidden:
            return False
        except discord.HTTPException:
            return False
        except Exception:
            # Catch all other exceptions to ensure fallback to ticket
            return False
    
    async def create_ticket_channel(self, guild: discord.Guild, member: discord.Member):
        """Create a ticket channel for the questionnaire."""
        settings = await self.config.guild(guild).all()
        category_id = settings.get("ticket_category")
        
        if not category_id:
            return None
        
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return None
        
        # Create a valid channel name using the slugify method
        channel_name = self.slugify_channel_name(f"suspicious-{member.name}")
        
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            
            # Add staff role to overwrites if configured
            staff_role_id = settings.get("staff_role")
            if staff_role_id:
                staff_role = guild.get_role(staff_role_id)
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True,
                        manage_messages=True
                    )
            
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Questionnaire ticket for {member}"
            )
            
            embed = discord.Embed(
                title="Security Questionnaire Required",
                description=(
                    f"Hello {member.mention}! You've been flagged for additional security verification.\n\n"
                    "Please complete this questionnaire within **24 hours** or you will be removed from the server.\n\n"
                    "Click the button below to start."
                ),
                color=discord.Color.orange()
            )
            
            questions = await self.config.guild(guild).questionnaire_questions()
            embed.add_field(name="Number of Questions", value=str(len(questions)), inline=True)
            embed.add_field(name="Time Limit", value="24 hours", inline=True)
            
            view = QuestionnaireButton(self)
            await channel.send(member.mention, embed=embed, view=view)
            
            return channel
            
        except discord.Forbidden:
            return None
        except Exception as e:
            print(f"Error creating ticket channel: {e}")
            return None
    
    async def timeout_questionnaire(self, guild: discord.Guild, member: discord.Member, delay: float):
        """Timeout task for kicking users who don't complete the questionnaire."""
        await asyncio.sleep(delay)
        await self.handle_timeout_kick(guild, member)
    
    async def handle_timeout_kick(self, guild: discord.Guild, member: discord.Member):
        """Handle kicking a user after questionnaire timeout."""
        # Use consistent task_id format
        task_id = f"{guild.id}_{member.id}"
        
        # Remove from pending and get ticket channel
        ticket_channel_id = None
        async with self.config.guild(guild).pending_questionnaires() as pending:
            if str(member.id) in pending:
                ticket_channel_id = pending[str(member.id)].get("ticket_channel_id")
                del pending[str(member.id)]
        
        # Remove task from dict
        if task_id in self.timeout_tasks:
            del self.timeout_tasks[task_id]
        
        # Clear saved roles before kick
        await self.config.member(member).saved_roles.set([])
        
        # Delete ticket channel if it exists
        if ticket_channel_id:
            ticket_channel = guild.get_channel(ticket_channel_id)
            if ticket_channel:
                try:
                    await ticket_channel.delete(reason="Questionnaire timeout")
                except Exception:
                    pass
        
        # Check if we can kick the member
        if not guild.me.guild_permissions.kick_members:
            return
        
        if member.top_role >= guild.me.top_role:
            return
        
        # Try to kick the member
        try:
            await member.kick(reason="Failed to complete security questionnaire within 24 hours")
            
            # Notify in alert channel
            alert_channel_id = await self.config.guild(guild).alert_channel()
            if alert_channel_id:
                alert_channel = guild.get_channel(alert_channel_id)
                if alert_channel:
                    embed = discord.Embed(
                        title="User Auto-Kicked",
                        description=f"{member.mention} ({member.name}) was kicked for not completing the questionnaire.",
                        color=discord.Color.red(),
                        timestamp=datetime.now(pytz.utc)
                    )
                    embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
                    await alert_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                    
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"Error kicking member {member.id}: {e}")
    
    async def send_questionnaire(self, guild: discord.Guild, member: discord.Member) -> dict:
        """Send questionnaire to a user via DM or ticket."""
        questions = await self.config.guild(guild).questionnaire_questions()
        
        if not questions:
            return {"success": False, "message": "No questionnaire questions configured. Use `/sus addquestion` first."}
        
        # Check if questionnaire already sent
        async with self.config.guild(guild).pending_questionnaires() as pending:
            if str(member.id) in pending:
                return {"success": False, "message": "Questionnaire already sent to this user."}
        
        # Try DM first
        dm_sent = await self.send_questionnaire_dm(member, guild)
        
        ticket_channel = None
        if not dm_sent:
            # Create ticket channel as fallback
            ticket_channel = await self.create_ticket_channel(guild, member)
            if not ticket_channel:
                return {"success": False, "message": "Failed to send questionnaire (DMs disabled and ticket creation failed)."}
        
        # Add to pending questionnaires with consistent task_id
        task_id = f"{guild.id}_{member.id}"
        async with self.config.guild(guild).pending_questionnaires() as pending:
            pending[str(member.id)] = {
                "sent_at": datetime.now(pytz.utc).isoformat(),
                "ticket_channel_id": ticket_channel.id if ticket_channel else None
            }
        
        # Start timeout task (24 hours)
        self.timeout_tasks[task_id] = asyncio.create_task(
            self.timeout_questionnaire(guild, member, 86400)  # 24 hours in seconds
        )
        
        if dm_sent:
            return {"success": True, "message": f"✅ Questionnaire sent to {member.mention} via DM. They have 24 hours to complete it."}
        else:
            return {"success": True, "message": f"✅ Questionnaire ticket created for {member.mention} in {ticket_channel.mention}. They have 24 hours to complete it."}
    
    async def mark_user_suspicious(self, guild: discord.Guild, member: discord.Member, marked_by: discord.Member = None) -> dict:
        """Mark a user as suspicious and send questionnaire."""
        settings = await self.config.guild(guild).all()
        
        suspicious_role_id = settings.get("suspicious_role")
        if not suspicious_role_id:
            return {"success": False, "message": "Suspicious role not configured. Use `/sus setrole` first."}
        
        suspicious_role = guild.get_role(suspicious_role_id)
        if not suspicious_role:
            return {"success": False, "message": "Suspicious role not found."}
        
        # Check bot permissions
        if not guild.me.guild_permissions.manage_roles:
            return {"success": False, "message": "I don't have permission to manage roles."}
        
        if suspicious_role >= guild.me.top_role:
            return {"success": False, "message": "The suspicious role is higher than my highest role."}
        
        # Save current roles (excluding @everyone and managed roles)
        current_roles = [r.id for r in member.roles if r != guild.default_role and not r.managed and r < guild.me.top_role]
        await self.config.member(member).saved_roles.set(current_roles)
        
        # Remove all roles and add suspicious role
        try:
            roles_to_remove = [r for r in member.roles if r != guild.default_role and not r.managed and r < guild.me.top_role]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Marked as suspicious")
            await member.add_roles(suspicious_role, reason="Marked as suspicious")
        except discord.Forbidden:
            return {"success": False, "message": "I don't have permission to manage roles for this user."}
        except Exception as e:
            return {"success": False, "message": f"Error managing roles: {e}"}
        
        # Send alert to alert channel
        alert_channel_id = settings.get("alert_channel")
        if alert_channel_id:
            alert_channel = guild.get_channel(alert_channel_id)
            if alert_channel:
                embed = discord.Embed(
                    title="⚠️ User Marked as Suspicious",
                    description=f"User: {member.mention} ({member.name})",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(pytz.utc)
                )
                embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
                if marked_by:
                    embed.add_field(name="Marked by", value=marked_by.mention, inline=False)
                embed.add_field(name="Account Age", value=f"{(datetime.now(pytz.utc) - member.created_at.replace(tzinfo=pytz.utc)).days} days", inline=False)
                
                # Always set thumbnail
                embed.set_thumbnail(url=member.display_avatar.url)
                
                mention_role_id = settings.get("mention_role")
                mention_text = ""
                if mention_role_id:
                    mention_role = guild.get_role(mention_role_id)
                    if mention_role:
                        mention_text = mention_role.mention
                
                await alert_channel.send(
                    mention_text,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=[mention_role] if mention_role else [])
                )
        
        # Send questionnaire
        result = await self.send_questionnaire(guild, member)
        
        return result
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Check new members for suspicious activity."""
        if member.bot:
            return
        
        settings = await self.config.guild(member.guild).all()
        min_account_age = settings.get("min_account_age", 7)
        
        # Check account age
        account_age = (datetime.now(pytz.utc) - member.created_at.replace(tzinfo=pytz.utc)).days
        
        if account_age < min_account_age:
            # Mark as suspicious
            suspicious_role_id = settings.get("suspicious_role")
            alert_channel_id = settings.get("alert_channel")
            
            if not suspicious_role_id or not alert_channel_id:
                return
            
            suspicious_role = member.guild.get_role(suspicious_role_id)
            alert_channel = member.guild.get_channel(alert_channel_id)
            
            if not suspicious_role or not alert_channel:
                return
            
            # Check permissions
            if not member.guild.me.guild_permissions.manage_roles:
                return
            
            if suspicious_role >= member.guild.me.top_role:
                return
            
            # Add suspicious role
            try:
                await member.add_roles(suspicious_role, reason=f"Account age: {account_age} days")
            except discord.Forbidden:
                return
            except Exception:
                return
            
            # Send alert
            embed = discord.Embed(
                title="⚠️ Suspicious User Detected",
                description=f"New member: {member.mention} ({member.name})",
                color=discord.Color.red(),
                timestamp=datetime.now(pytz.utc)
            )
            embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
            embed.add_field(name="Account Age", value=f"{account_age} days", inline=False)
            embed.add_field(name="Threshold", value=f"{min_account_age} days", inline=False)
            embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=False)
            
            # Always set thumbnail
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Add action buttons with stateless view
            view = SuspiciousUserView(self)
            
            # Get mention role
            mention_role_id = settings.get("mention_role")
            mention_text = ""
            mention_role = None
            if mention_role_id:
                mention_role = member.guild.get_role(mention_role_id)
                if mention_role:
                    mention_text = mention_role.mention
            
            await alert_channel.send(
                mention_text,
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions(roles=[mention_role] if mention_role else [])
            )
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Clean up when a member leaves the server."""
        if member.bot:
            return
        
        # Cancel timeout task if exists
        task_id = f"{member.guild.id}_{member.id}"
        if task_id in self.timeout_tasks:
            self.timeout_tasks[task_id].cancel()
            del self.timeout_tasks[task_id]
        
        # Remove from pending questionnaires and delete ticket
        ticket_channel_id = None
        async with self.config.guild(member.guild).pending_questionnaires() as pending:
            if str(member.id) in pending:
                ticket_channel_id = pending[str(member.id)].get("ticket_channel_id")
                del pending[str(member.id)]
        
        # Delete ticket channel if it exists
        if ticket_channel_id:
            ticket_channel = member.guild.get_channel(ticket_channel_id)
            if ticket_channel:
                try:
                    await ticket_channel.delete(reason="Member left the server")
                except Exception:
                    pass
        
        # Clear saved roles
        await self.config.member(member).saved_roles.set([])
    
    def _create_sus_group(self):
        """Create the sus slash command group."""
        sus_group = app_commands.Group(
            name="sus",
            description="Suspicious user management commands",
        )
        
        @sus_group.command(name="setrole", description="Set the role to assign to suspicious users")
        @app_commands.describe(role="The role to assign to suspicious users")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setrole_slash(interaction: discord.Interaction, role: discord.Role):
            if role >= interaction.guild.me.top_role:
                return await interaction.response.send_message(
                    "The suspicious role must be lower than my highest role in the hierarchy.",
                    ephemeral=True
                )
            await self.config.guild(interaction.guild).suspicious_role.set(role.id)
            await interaction.response.send_message(f"Suspicious role set to {role.mention}.", ephemeral=True)
        
        @sus_group.command(name="setchannel", description="Set the alert/review channel")
        @app_commands.describe(channel="The channel for alerts and questionnaire reviews")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setchannel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
            if not channel.permissions_for(interaction.guild.me).send_messages:
                return await interaction.response.send_message(
                    f"I don't have permission to send messages in {channel.mention}.",
                    ephemeral=True
                )
            await self.config.guild(interaction.guild).alert_channel.set(channel.id)
            await interaction.response.send_message(f"Alert/Review channel set to {channel.mention}.", ephemeral=True)
        
        @sus_group.command(name="setticketcategory", description="Set the category for ticket channels")
        @app_commands.describe(category="The category where ticket channels will be created")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setticketcategory_slash(interaction: discord.Interaction, category: discord.CategoryChannel):
            if not category.permissions_for(interaction.guild.me).manage_channels:
                return await interaction.response.send_message(
                    f"I don't have permission to manage channels in **{category.name}**.",
                    ephemeral=True
                )
            await self.config.guild(interaction.guild).ticket_category.set(category.id)
            await interaction.response.send_message(
                f"Ticket category set to **{category.name}**.\n"
                f"When users have DMs disabled, ticket channels will be created here.",
                ephemeral=True
            )
        
        @sus_group.command(name="setage", description="Set the minimum account age in days")
        @app_commands.describe(days="Minimum account age in days")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setage_slash(interaction: discord.Interaction, days: int):
            if days < 0:
                return await interaction.response.send_message("Please provide a non-negative number of days.", ephemeral=True)
            await self.config.guild(interaction.guild).min_account_age.set(days)
            await interaction.response.send_message(f"Minimum account age set to {days} days.", ephemeral=True)
        
        @sus_group.command(name="setmention", description="Set the role to be mentioned in alerts")
        @app_commands.describe(role="The role to mention in alerts")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setmention_slash(interaction: discord.Interaction, role: discord.Role):
            await self.config.guild(interaction.guild).mention_role.set(role.id)
            await interaction.response.send_message(f"Mention role set to {role.mention}.", ephemeral=True)
        
        @sus_group.command(name="setstaffrole", description="Set the staff role that can use the /suspicious command")
        @app_commands.describe(role="The staff role for questionnaire management")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setstaffrole_slash(interaction: discord.Interaction, role: discord.Role):
            await self.config.guild(interaction.guild).staff_role.set(role.id)
            await interaction.response.send_message(
                f"Staff role set to {role.mention}.\n"
                f"Members with this role (or manage_roles permission) can use `/suspicious`.",
                ephemeral=True
            )
        
        @sus_group.command(name="addquestion", description="Add a question to the questionnaire")
        @app_commands.describe(question="The question to ask users")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def addquestion_slash(interaction: discord.Interaction, question: str):
            if len(question) > 200:
                return await interaction.response.send_message("Question is too long. Maximum 200 characters.", ephemeral=True)
            
            async with self.config.guild(interaction.guild).questionnaire_questions() as questions:
                if len(questions) >= 5:
                    return await interaction.response.send_message(
                        "Maximum of 5 questions allowed (Discord modal limit).",
                        ephemeral=True
                    )
                questions.append(question)
            
            await interaction.response.send_message(f"✅ Added question: **{question}**", ephemeral=True)
        
        @sus_group.command(name="removequestion", description="Remove a question from the questionnaire")
        @app_commands.describe(index="The question number to remove (1-5)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def removequestion_slash(interaction: discord.Interaction, index: int):
            if index < 1 or index > 5:
                return await interaction.response.send_message("Invalid index. Use a number between 1-5.", ephemeral=True)
            
            async with self.config.guild(interaction.guild).questionnaire_questions() as questions:
                if index > len(questions):
                    return await interaction.response.send_message(
                        f"Question {index} doesn't exist. You have {len(questions)} questions configured.",
                        ephemeral=True
                    )
                removed = questions.pop(index - 1)
            
            await interaction.response.send_message(f"✅ Removed question {index}: **{removed}**", ephemeral=True)
        
        @sus_group.command(name="listquestions", description="List all configured questionnaire questions")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def listquestions_slash(interaction: discord.Interaction):
            questions = await self.config.guild(interaction.guild).questionnaire_questions()
            
            if not questions:
                return await interaction.response.send_message(
                    "No questions configured. Use `/sus addquestion` to add questions.",
                    ephemeral=True
                )
            
            embed = discord.Embed(
                title="Questionnaire Questions",
                description="These questions will be asked to suspicious users:",
                color=discord.Color.blue()
            )
            
            for i, question in enumerate(questions, 1):
                embed.add_field(name=f"Question {i}", value=question, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @sus_group.command(name="settings", description="Display current Suspicious User Monitor settings")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def settings_slash(interaction: discord.Interaction):
            settings = await self.config.guild(interaction.guild).all()
            
            suspicious_role_id = settings.get("suspicious_role")
            alert_channel_id = settings.get("alert_channel")
            ticket_category_id = settings.get("ticket_category")
            mention_role_id = settings.get("mention_role")
            staff_role_id = settings.get("staff_role")
            min_account_age = settings.get("min_account_age")
            questions = settings.get("questionnaire_questions", [])
            pending_count = len(settings.get("pending_questionnaires", {}))

            suspicious_role = interaction.guild.get_role(suspicious_role_id) if suspicious_role_id else None
            alert_channel = interaction.guild.get_channel(alert_channel_id) if alert_channel_id else None
            ticket_category = interaction.guild.get_channel(ticket_category_id) if ticket_category_id else None
            mention_role = interaction.guild.get_role(mention_role_id) if mention_role_id else None
            staff_role = interaction.guild.get_role(staff_role_id) if staff_role_id else None

            embed = discord.Embed(
                title="Suspicious User Monitor Settings",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Suspicious Role", 
                value=suspicious_role.mention if suspicious_role else "Not set",
                inline=False
            )
            embed.add_field(
                name="Alert/Review Channel", 
                value=alert_channel.mention if alert_channel else "Not set",
                inline=False
            )
            embed.add_field(
                name="Ticket Category", 
                value=ticket_category.name if ticket_category else "Not set",
                inline=False
            )
            embed.add_field(
                name="Mention Role", 
                value=mention_role.mention if mention_role else "Not set",
                inline=False
            )
            embed.add_field(
                name="Staff Role", 
                value=staff_role.mention if staff_role else "Not set",
                inline=False
            )
            embed.add_field(
                name="Minimum Account Age", 
                value=f"{min_account_age} days",
                inline=False
            )
            embed.add_field(
                name="Questionnaire Questions",
                value=f"{len(questions)}/5 configured" if questions else "Not configured",
                inline=False
            )
            embed.add_field(
                name="Pending Questionnaires",
                value=f"{pending_count} users",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        return sus_group
    
    @app_commands.command(name="suspicious", description="Mark a user as suspicious and send them a questionnaire")
    @app_commands.describe(user="The user to mark as suspicious")
    @app_commands.guild_only()
    async def suspicious_command(self, interaction: discord.Interaction, user: discord.Member):
        # Check permissions
        if not await self.has_staff_role(interaction):
            return await interaction.response.send_message(
                "You don't have permission to use this command. Contact an administrator to set up staff roles.",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        if user.bot:
            return await interaction.followup.send("You cannot mark bots as suspicious.", ephemeral=True)
        
        if user.top_role >= interaction.guild.me.top_role:
            return await interaction.followup.send(
                "I cannot manage this user's roles due to role hierarchy.",
                ephemeral=True
            )
        
        result = await self.mark_user_suspicious(interaction.guild, user, interaction.user)
        await interaction.followup.send(result["message"], ephemeral=True)
