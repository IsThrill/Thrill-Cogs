import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
from redbot.core import commands, Config, tasks
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box
from datetime import datetime, timedelta
import pytz
import asyncio
import re
import string

class QuestionnaireModal(Modal):
    def __init__(self, cog, guild_id: int, user_id: int, questions: list):
        super().__init__(title="Security Questionnaire", timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.questions = questions
        self.text_inputs = []
        
        for i, question in enumerate(questions[:5]):
            placeholder_text = None
            if len(question) > 45:
                placeholder_text = question[:100]  

            text_input = TextInput(
                label=question[:45],  
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=500,
                placeholder=placeholder_text  
            )
            self.text_inputs.append(text_input)
            self.add_item(text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        ticket_channel_id = None
        
        async with self.cog.config.guild_from_id(self.guild_id).pending_questionnaires() as pending:
            if str(self.user_id) in pending:
                ticket_channel_id = pending[str(self.user_id)].get("ticket_channel_id")
                del pending[str(self.user_id)]
        
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
        
        embed = discord.Embed(
            title="Questionnaire Responses",
            description=f"User: {member.mention} ({member.name})",
            color=discord.Color.blue(),
            timestamp=datetime.now(pytz.utc)
        )
        embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
        
        for i, (question, text_input) in enumerate(zip(self.questions, self.text_inputs), 1):
            answer = text_input.value[:1000]
            embed.add_field(name=f"{i}. {question}", value=answer, inline=False)
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        view = QuestionnaireReviewView(self.cog)
        
        try:
            await review_channel.send(
                embed=embed, 
                view=view,
                allowed_mentions=discord.AllowedMentions.none()
            )
            await interaction.followup.send(
                "✅ Thank you for completing the questionnaire! Staff will review your responses shortly.",
                ephemeral=True
            )
            
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
        guild = interaction.guild
        guild_id = None
        user_id = interaction.user.id
        
        if guild is None:
            if interaction.message and interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if embed.footer and embed.footer.text:
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
            guild_id = guild.id
            target_member = None
            channel = interaction.channel
            
            if hasattr(channel, 'overwrites'):
                for target, overwrite in channel.overwrites.items():
                    if isinstance(target, discord.Member) and target != guild.me:
                        if overwrite.read_messages:
                            target_member = target
                            break
            
            if target_member and target_member != interaction.user:
                user_id = target_member.id
            else:
                user_id = interaction.user.id
        
        pending = await self.cog.config.guild(guild).pending_questionnaires()
        if str(user_id) not in pending:
            await interaction.response.send_message(
                "You don't have a pending questionnaire.", 
                ephemeral=True
            )
            return
        
        questions = await self.cog.config.guild(guild).questionnaire_questions()
        if not questions:
            await interaction.response.send_message(
                "No questions configured.", 
                ephemeral=True
            )
            return
        
        modal = QuestionnaireModal(self.cog, guild_id, user_id, questions)
        await interaction.response.send_modal(modal)

class QuestionnaireReviewView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    async def has_staff_permissions(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_roles:
            return True
        
        settings = await self.cog.config.guild(interaction.guild).all()
        staff_role_id = settings.get("staff_role")
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role and staff_role in interaction.user.roles:
                return True
        
        return False
    
    @discord.ui.button(
        label="Approve", 
        style=discord.ButtonStyle.success, 
        emoji="✅",
        custom_id="questionnaire_approve_persistent"
    )
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_staff_permissions(interaction):
            return await interaction.response.send_message(
                "You don't have permission to review questionnaires.", 
                ephemeral=True
            )
        
        if not interaction.message.embeds:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        
        user_id = None
        for field in embed.fields:
            if field.name == "User ID":
                id_text = field.value.strip('`').strip()
                try:
                    user_id = int(id_text)
                    break
                except ValueError:
                    continue
        
        if not user_id:
            return await interaction.response.send_message("Error: Could not find user ID.", ephemeral=True)
        
        member = interaction.guild.get_member(user_id)
        if not member:
            new_embed = embed.copy()
            new_embed.color = discord.Color.dark_gray()
            new_embed.add_field(name="⚠️ Status", value="User has left the server", inline=False)
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            return
        
        saved_roles = await self.cog.config.member(member).saved_roles()
        suspicious_role_id = await self.cog.config.guild(interaction.guild).suspicious_role()
        
        roles_to_add = []
        for role_id in saved_roles:
            role = interaction.guild.get_role(role_id)
            if role and role < interaction.guild.me.top_role:
                roles_to_add.append(role)
        
        try:
            if suspicious_role_id:
                suspicious_role = interaction.guild.get_role(suspicious_role_id)
                if suspicious_role and suspicious_role in member.roles:
                    await member.remove_roles(suspicious_role, reason=f"Approved by {interaction.user}")
            
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"Approved by {interaction.user}")
            
            await self.cog.config.member(member).saved_roles.set([])
            
            new_embed = embed.copy()
            new_embed.color = discord.Color.green()
            new_embed.add_field(
                name="✅ Approved", 
                value=f"By: {interaction.user.mention}\nRoles restored: {len(roles_to_add)}", 
                inline=False
            )
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            
            try:
                await member.send(
                    f"✅ Your questionnaire for **{interaction.guild.name}** has been approved! "
                    f"Your roles have been restored."
                )
            except discord.Forbidden:
                pass
                
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to manage roles for this user.", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Error approving user: {e}", 
                ephemeral=True
            )
    
    @discord.ui.button(
        label="Reject (Kick)", 
        style=discord.ButtonStyle.danger, 
        emoji="🚫",
        custom_id="questionnaire_reject_persistent"
    )
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_staff_permissions(interaction):
            return await interaction.response.send_message(
                "You don't have permission to review questionnaires.", 
                ephemeral=True
            )
        
        if not interaction.message.embeds:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        
        user_id = None
        for field in embed.fields:
            if field.name == "User ID":
                id_text = field.value.strip('`').strip()
                try:
                    user_id = int(id_text)
                    break
                except ValueError:
                    continue
        
        if not user_id:
            return await interaction.response.send_message("Error: Could not find user ID.", ephemeral=True)
        
        member = interaction.guild.get_member(user_id)
        if not member:
            new_embed = embed.copy()
            new_embed.color = discord.Color.dark_gray()
            new_embed.add_field(name="⚠️ Status", value="User has left the server", inline=False)
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            return
        
        if not interaction.guild.me.guild_permissions.kick_members:
            return await interaction.response.send_message(
                "I don't have permission to kick members.", 
                ephemeral=True
            )
        
        if member.top_role > interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "I cannot kick this user due to role hierarchy.", 
                ephemeral=True
            )
        
        if member.id == interaction.guild.owner_id:
            return await interaction.response.send_message(
                "I cannot kick the server owner.", 
                ephemeral=True
            )
        
        await self.cog.config.member(member).saved_roles.set([])
        
        try:
            try:
                await member.send(
                    f"❌ Your questionnaire for **{interaction.guild.name}** has been rejected. "
                    f"You have been removed from the server."
                )
            except discord.Forbidden:
                pass
            
            await member.kick(reason=f"Questionnaire rejected by {interaction.user}")
            
            new_embed = embed.copy()
            new_embed.color = discord.Color.red()
            new_embed.add_field(
                name="❌ Rejected & Kicked", 
                value=f"By: {interaction.user.mention}", 
                inline=False
            )
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "Failed to kick the user. Check my permissions and role hierarchy.", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Error kicking user: {e}", 
                ephemeral=True
            )

class SuspiciousUserView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    async def has_staff_permissions(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_roles:
            return True
        
        settings = await self.cog.config.guild(interaction.guild).all()
        staff_role_id = settings.get("staff_role")
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role and staff_role in interaction.user.roles:
                return True
        
        return False
    
    @discord.ui.button(
        label="Send Questionnaire",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="sus_send_questionnaire_persistent"
    )
    async def send_questionnaire_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_staff_permissions(interaction):
            return await interaction.response.send_message(
                "You don't have permission to manage suspicious users.", 
                ephemeral=True
            )
        
        if not interaction.message.embeds:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        
        user_id = None
        for field in embed.fields:
            if field.name == "User ID":
                id_text = field.value.strip('`').strip()
                try:
                    user_id = int(id_text)
                    break
                except ValueError:
                    continue
        
        if not user_id:
            return await interaction.response.send_message("Error: Could not find user ID.", ephemeral=True)
        
        member = interaction.guild.get_member(user_id)
        if not member:
            new_embed = embed.copy()
            new_embed.color = discord.Color.dark_gray()
            new_embed.add_field(name="⚠️ Status", value="User has left the server", inline=False)
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        result = await self.cog.mark_user_suspicious(interaction.guild, member, interaction.user)
        await interaction.followup.send(result["message"], ephemeral=True)
        
        if result["success"]:
            new_embed = embed.copy()
            new_embed.add_field(
                name="📝 Questionnaire Sent", 
                value=f"By: {interaction.user.mention}", 
                inline=False
            )
            
            for item in self.children:
                if item.label == "Send Questionnaire":
                    item.disabled = True
            
            await interaction.message.edit(embed=new_embed, view=self)
    
    @discord.ui.button(
        label="Clear Suspicious",
        style=discord.ButtonStyle.secondary,
        emoji="✅",
        custom_id="sus_clear_suspicious_persistent"
    )
    async def clear_suspicious_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_staff_permissions(interaction):
            return await interaction.response.send_message(
                "You don't have permission to manage suspicious users.", 
                ephemeral=True
            )
        
        if not interaction.message.embeds:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        
        user_id = None
        for field in embed.fields:
            if field.name == "User ID":
                id_text = field.value.strip('`').strip()
                try:
                    user_id = int(id_text)
                    break
                except ValueError:
                    continue
        
        if not user_id:
            return await interaction.response.send_message("Error: Could not find user ID.", ephemeral=True)
        
        member = interaction.guild.get_member(user_id)
        if not member:
            new_embed = embed.copy()
            new_embed.color = discord.Color.dark_gray()
            new_embed.add_field(name="⚠️ Status", value="User has left the server", inline=False)
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            return
        
        suspicious_role_id = await self.cog.config.guild(interaction.guild).suspicious_role()
        if suspicious_role_id:
            suspicious_role = interaction.guild.get_role(suspicious_role_id)
            if suspicious_role and suspicious_role in member.roles:
                try:
                    await member.remove_roles(suspicious_role, reason=f"Cleared by {interaction.user}")
                except discord.Forbidden:
                    return await interaction.response.send_message(
                        "I don't have permission to manage roles for this user.", 
                        ephemeral=True
                    )

            ticket_channel_id = None
            async with self.cog.config.guild(interaction.guild).pending_questionnaires() as pending:
                entry = pending.pop(str(user_id), None)
                if entry:
                    ticket_channel_id = entry.get("ticket_channel_id")

            if ticket_channel_id:
                ch = interaction.guild.get_channel(ticket_channel_id)
                if ch:
                    try:
                        await ch.delete(reason=f"Cleared by {interaction.user}")
                    except Exception:
                        pass

            try:
                await self.cog.config.member_from_ids(interaction.guild.id, user_id).saved_roles.set([])
            except Exception:
                pass
        
        new_embed = embed.copy()
        new_embed.color = discord.Color.green()
        new_embed.add_field(
            name="✅ Cleared", 
            value=f"By: {interaction.user.mention}", 
            inline=False
        )
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=new_embed, view=self)
    
    @discord.ui.button(
        label="Kick User",
        style=discord.ButtonStyle.danger,
        emoji="🚫",
        custom_id="sus_kick_user_persistent"
    )
    async def kick_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.has_staff_permissions(interaction):
            return await interaction.response.send_message(
                "You don't have permission to kick users.", 
                ephemeral=True
            )
        
        if not interaction.guild.me.guild_permissions.kick_members:
            return await interaction.response.send_message(
                "I don't have permission to kick members.", 
                ephemeral=True
            )
        
        if not interaction.message.embeds:
            return await interaction.response.send_message("Error: No embed found.", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        
        user_id = None
        for field in embed.fields:
            if field.name == "User ID":
                id_text = field.value.strip('`').strip()
                try:
                    user_id = int(id_text)
                    break
                except ValueError:
                    continue
        
        if not user_id:
            return await interaction.response.send_message("Error: Could not find user ID.", ephemeral=True)
        
        member = interaction.guild.get_member(user_id)
        if not member:
            new_embed = embed.copy()
            new_embed.color = discord.Color.dark_gray()
            new_embed.add_field(name="⚠️ Status", value="User has left the server", inline=False)
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            return
        
        if member.top_role > interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "I cannot kick this user due to role hierarchy.", 
                ephemeral=True
            )
        
        if member.id == interaction.guild.owner_id:
            return await interaction.response.send_message(
                "I cannot kick the server owner.", 
                ephemeral=True
            )
        
        try:
            await member.kick(reason=f"Kicked by {interaction.user} (Suspicious user)")
            
            new_embed = embed.copy()
            new_embed.color = discord.Color.red()
            new_embed.add_field(
                name="🚫 Kicked", 
                value=f"By: {interaction.user.mention}", 
                inline=False
            )
            
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=new_embed, view=self)
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "Failed to kick the user. Check my permissions and role hierarchy.", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"Error kicking user: {e}", 
                ephemeral=True
            )

class SuspiciousUserMonitor(commands.Cog):
    
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
        self.sus_group = None
        self.check_expired_questionnaires.start()
        self.sweeper_task = self.check_expired_questionnaires
    
    async def cog_load(self):
        self.bot.add_view(QuestionnaireReviewView(self))
        self.bot.add_view(SuspiciousUserView(self))
        self.bot.add_view(QuestionnaireButton(self))
        
        if not self.sus_group:
            self.sus_group = self._create_sus_group()
        self.bot.tree.add_command(self.sus_group)
    
    async def cog_unload(self):
        self.check_expired_questionnaires.cancel()
        
        if self.sus_group:
            self.bot.tree.remove_command("sus")
    
    @tasks.loop(seconds=60)
    async def check_expired_questionnaires(self):
        await self.bot.wait_until_ready()
        
        now = datetime.now(pytz.utc)
        all_guilds_data = await self.config.all_guilds()
        
        for guild_id_str, guild_data in all_guilds_data.items():
            guild_id = int(guild_id_str)
            pending = guild_data.get("pending_questionnaires", {})
            

            for user_id_str in list(pending.keys()):
                try:
                    user_id = int(user_id_str)
                    questionnaire_data = pending[user_id_str]
                    
                    expires_at_str = questionnaire_data.get("expires_at")
                    if not expires_at_str:
                        continue
                        
                    expires_at = datetime.fromisoformat(expires_at_str)
                    
                    if now >= expires_at:
                        print(f"User {user_id} in guild {guild_id} expired. Handling kick...")

                        guild = self.bot.get_guild(guild_id)
                        if guild is not None:
                            member = guild.get_member(user_id)
                            if member is not None:
                                suspicious_role_id = await self.config.guild(guild).suspicious_role()
                                if suspicious_role_id:
                                    sus_role = guild.get_role(suspicious_role_id)
                                    if (sus_role is None) or (sus_role not in member.roles):
                                        async with self.config.guild_from_id(guild_id).pending_questionnaires() as p:
                                            entry = p.pop(str(user_id), None)
                                            if entry and entry.get("ticket_channel_id"):
                                                ch = guild.get_channel(entry["ticket_channel_id"])
                                                if ch:
                                                    try:
                                                        await ch.delete(reason="Suspicious role cleared by staff")
                                                    except Exception:
                                                        pass
                                        continue
                        await self.handle_timeout_kick(guild_id, user_id)
                        
                except (ValueError, KeyError, TypeError) as e:
                    print(f"Error processing sweeper task for {user_id_str} in {guild_id}: {e}")
                    continue

    def slugify_channel_name(self, name: str) -> str:
        name = re.sub(r'[^\w\s-]', '', name.lower())
        name = re.sub(r'[\s]+', '-', name)
        name = re.sub(r'-+', '-', name)
        name = name.strip('-')
        allowed = set(string.ascii_lowercase + string.digits + '-')
        name = ''.join(c for c in name if c in allowed)
        if len(name) > 100:
            name = name[:100]
        return name if name else 'suspicious-user'
    
    async def has_staff_role(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_roles:
            return True
        
        staff_role_id = await self.config.guild(interaction.guild).staff_role()
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            if staff_role and staff_role in interaction.user.roles:
                return True
        
        return False
    
    async def send_questionnaire_dm(self, member: discord.Member, guild: discord.Guild) -> bool:
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
            embed.set_footer(text=f"Guild ID: {guild.id}")
            
            view = QuestionnaireButton(self)
            await member.send(embed=embed, view=view)
            return True
            
        except (discord.Forbidden, discord.HTTPException):
            return False
        except Exception:
            return False
    
    async def create_ticket_channel(self, guild: discord.Guild, member: discord.Member):
        settings = await self.config.guild(guild).all()
        category_id = settings.get("ticket_category")
        
        if not category_id:
            return None
        
        category = guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return None
        
        channel_name = self.slugify_channel_name(f"suspicious-{member.name}")
        
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            
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

async def handle_timeout_kick(self, guild_id: int, user_id: int):
    guild = self.bot.get_guild(guild_id)
    if not guild:
        print(f"Failed to find guild {guild_id} for timeout kick.")
        return

    pending_all = await self.config.guild_from_id(guild_id).pending_questionnaires()
    entry = pending_all.get(str(user_id))
    if not entry:

        return

    ticket_channel_id = entry.get("ticket_channel_id")

    member = guild.get_member(user_id)
    target = member or discord.Object(id=user_id)

    if not guild.me.guild_permissions.kick_members:
        await self._send_kick_fail_embed(guild, member, user_id, "Bot lacks kick_members permission")
        return
    if member:
        if member.id == guild.owner_id:
            await self._send_kick_fail_embed(guild, member, user_id, "User is the server owner")
            return
        if member.top_role >= guild.me.top_role:
            await self._send_kick_fail_embed(
                guild, member, user_id,
                f"Role hierarchy (user: {member.top_role.name} ≥ bot: {guild.me.top_role.name})"
            )
            return

    try:
        await guild.kick(target, reason="Failed to complete security questionnaire within 24 hours")

        async with self.config.guild_from_id(guild_id).pending_questionnaires() as pending:
            pending.pop(str(user_id), None)

        if ticket_channel_id:
            ch = guild.get_channel(ticket_channel_id)
            if ch:
                try:
                    await ch.delete(reason="Questionnaire timeout")
                except Exception:
                    pass

        try:
            await self.config.member_from_ids(guild_id, user_id).saved_roles.set([])
        except Exception:
            pass

        await self._send_kick_ok_embed(guild, member, user_id)

    except discord.Forbidden as e:
        await self._send_kick_error_embed(guild, member, user_id, "Permission Denied (Forbidden)", str(e))

    except discord.HTTPException as e:
        await self._send_kick_error_embed(guild, member, user_id, "HTTP error", str(e))

    except Exception as e:
        await self._send_kick_error_embed(guild, member, user_id, "Unexpected error", str(e))

async def _send_kick_ok_embed(self, guild, member, user_id):
    alert_channel_id = await self.config.guild(guild).alert_channel()
    ch = guild.get_channel(alert_channel_id) if alert_channel_id else None
    if not ch:
        return
    mention = (member.mention if member else f"<@{user_id}>")
    emb = discord.Embed(
        title="✅ User Auto-Kicked",
        description=f"{mention} was removed from the server",
        color=discord.Color.green(),
        timestamp=datetime.now(pytz.utc),
    )
    emb.add_field(name="Reason", value="Failed to complete questionnaire within 24 hours", inline=False)
    emb.add_field(name="User ID", value=box(str(user_id)), inline=False)
    await ch.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())

async def _send_kick_fail_embed(self, guild, member, user_id, reason: str):
    alert_channel_id = await self.config.guild(guild).alert_channel()
    ch = guild.get_channel(alert_channel_id) if alert_channel_id else None
    if not ch:
        return
    mention = (member.mention if member else f"<@{user_id}>")
    emb = discord.Embed(
        title="❌ Auto-Kick Failed",
        description=f"Cannot kick {mention}.",
        color=discord.Color.red(),
        timestamp=datetime.now(pytz.utc),
    )
    emb.add_field(name="Reason", value=reason, inline=False)
    emb.add_field(name="User ID", value=box(str(user_id)), inline=False)
    await ch.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())

async def _send_kick_error_embed(self, guild, member, user_id, errtype: str, details: str):
    alert_channel_id = await self.config.guild(guild).alert_channel()
    ch = guild.get_channel(alert_channel_id) if alert_channel_id else None
    if not ch:
        return
    mention = (member.mention if member else f"<@{user_id}>")
    emb = discord.Embed(
        title="❌ Auto-Kick Failed",
        description=f"Cannot kick {mention}.",
        color=discord.Color.red(),
        timestamp=datetime.now(pytz.utc),
    )
    emb.add_field(name="Error Type", value=errtype, inline=False)
    emb.add_field(name="Details", value=details[:1024], inline=False)
    emb.add_field(name="User ID", value=box(str(user_id)), inline=False)
    await ch.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())    
    async def send_questionnaire(self, guild: discord.Guild, member: discord.Member) -> dict:
        questions = await self.config.guild(guild).questionnaire_questions()
        
        if not questions:
            return {"success": False, "message": "No questionnaire questions configured. Use `/sus addquestion` first."}
        
        async with self.config.guild(guild).pending_questionnaires() as pending:
            if str(member.id) in pending:
                return {"success": False, "message": "Questionnaire already sent to this user."}
        
        dm_sent = await self.send_questionnaire_dm(member, guild)
        
        ticket_channel = None
        if not dm_sent:
            ticket_channel = await self.create_ticket_channel(guild, member)
            if not ticket_channel:
                now = datetime.now(pytz.utc)
                expires = now + timedelta(hours=24)
                
                async with self.config.guild(guild).pending_questionnaires() as pending:
                    pending[str(member.id)] = {
                        "sent_at": now.isoformat(),
                        "expires_at": expires.isoformat(),
                        "ticket_channel_id": None,
                        "delivery_failed": True
                    }
                
                alert_channel_id = await self.config.guild(guild).alert_channel()
                if alert_channel_id:
                    alert_channel = guild.get_channel(alert_channel_id)
                    if alert_channel:
                        embed = discord.Embed(
                            title="⚠️ Questionnaire Delivery Failed",
                            description=(
                                f"Failed to send questionnaire to {member.mention} ({member.name}).\n"
                                f"DMs are disabled and ticket creation failed.\n\n"
                                f"**User will still be kicked in 24 hours.**"
                            ),
                            color=discord.Color.orange(),
                            timestamp=datetime.now(pytz.utc)
                        )
                        embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
                        await alert_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                
                return {
                    "success": True,
                    "message": (
                        f"⚠️ Failed to send questionnaire to {member.mention} "
                        f"(DMs disabled and ticket creation failed). "
                        f"User will still be kicked in 24 hours."
                    )
                }
        
        now = datetime.now(pytz.utc)
        expires = now + timedelta(hours=24)
        
        async with self.config.guild(guild).pending_questionnaires() as pending:
            pending[str(member.id)] = {
                "sent_at": now.isoformat(),
                "expires_at": expires.isoformat(),
                "ticket_channel_id": ticket_channel.id if ticket_channel else None
            }
        
        if dm_sent:
            return {"success": True, "message": f"✅ Questionnaire sent to {member.mention} via DM. They have 24 hours to complete it."}
        else:
            return {"success": True, "message": f"✅ Questionnaire ticket created for {member.mention} in {ticket_channel.mention}. They have 24 hours to complete it."}
    
    async def mark_user_suspicious(self, guild: discord.Guild, member: discord.Member, marked_by: discord.Member = None) -> dict:
        settings = await self.config.guild(guild).all()
        
        suspicious_role_id = settings.get("suspicious_role")
        if not suspicious_role_id:
            return {"success": False, "message": "Suspicious role not configured. Use `/sus setrole` first."}
        
        suspicious_role = guild.get_role(suspicious_role_id)
        if not suspicious_role:
            return {"success": False, "message": "Suspicious role not found."}
        
        if not guild.me.guild_permissions.manage_roles:
            return {"success": False, "message": "I don't have permission to manage roles."}
        
        if suspicious_role >= guild.me.top_role:
            return {"success": False, "message": "The suspicious role is higher than my highest role."}
        
        current_roles = [r.id for r in member.roles if r != guild.default_role and not r.managed and r < guild.me.top_role]
        await self.config.member(member).saved_roles.set(current_roles)
        
        try:
            roles_to_remove = [r for r in member.roles if r != guild.default_role and not r.managed and r < guild.me.top_role]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Marked as suspicious")
            await member.add_roles(suspicious_role, reason="Marked as suspicious")
        except discord.Forbidden:
            return {"success": False, "message": "I don't have permission to manage roles for this user."}
        except Exception as e:
            return {"success": False, "message": f"Error managing roles: {e}"}
        
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
                
                embed.set_thumbnail(url=member.display_avatar.url)
                
                mention_role_id = settings.get("mention_role")
                mention_text = ""
                mention_role = None
                if mention_role_id:
                    mention_role = guild.get_role(mention_role_id)
                    if mention_role:
                        mention_text = mention_role.mention
                
                await alert_channel.send(
                    mention_text,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=[mention_role] if mention_role else [])
                )
        
        result = await self.send_questionnaire(guild, member)
        
        return result

    async def handle_timeout_kick(self, guild_id: int, user_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            print(f"Failed to find guild {guild_id} for timeout kick.")
            return

        pending_all = await self.config.guild_from_id(guild_id).pending_questionnaires()
        entry = pending_all.get(str(user_id))
        if not entry:

            return

        ticket_channel_id = entry.get("ticket_channel_id")

        member = guild.get_member(user_id)
        target = member or discord.Object(id=user_id)

        if not guild.me.guild_permissions.kick_members:
            await self._send_kick_fail_embed(guild, member, user_id, "Bot lacks kick_members permission")
            return
        if member:
            if member.id == guild.owner_id:
                await self._send_kick_fail_embed(guild, member, user_id, "User is the server owner")
                return
            if member.top_role >= guild.me.top_role:
                await self._send_kick_fail_embed(
                    guild, member, user_id,
                    f"Role hierarchy (user: {member.top_role.name} ≥ bot: {guild.me.top_role.name})"
                )
                return

        try:
            await guild.kick(target, reason="Failed to complete security questionnaire within 24 hours")

            async with self.config.guild_from_id(guild_id).pending_questionnaires() as pending:
                pending.pop(str(user_id), None)

            if ticket_channel_id:
                ch = guild.get_channel(ticket_channel_id)
                if ch:
                    try:
                        await ch.delete(reason="Questionnaire timeout")
                    except Exception:
                        pass

            try:
                await self.config.member_from_ids(guild_id, user_id).saved_roles.set([])
            except Exception:
                pass

            await self._send_kick_ok_embed(guild, member, user_id)

        except discord.Forbidden as e:
            await self._send_kick_error_embed(guild, member, user_id, "Permission Denied (Forbidden)", str(e))

        except discord.HTTPException as e:
            await self._send_kick_error_embed(guild, member, user_id, "HTTP error", str(e))

        except Exception as e:
            await self._send_kick_error_embed(guild, member, user_id, "Unexpected error", str(e))

    async def _send_kick_ok_embed(self, guild, member, user_id):
        alert_channel_id = await self.config.guild(guild).alert_channel()
        ch = guild.get_channel(alert_channel_id) if alert_channel_id else None
        if not ch:
            return
        mention = (member.mention if member else f"<@{user_id}>")
        emb = discord.Embed(
            title="✅ User Auto-Kicked",
            description=f"{mention} was removed from the server",
            color=discord.Color.green(),
            timestamp=datetime.now(pytz.utc),
        )
        emb.add_field(name="Reason", value="Failed to complete questionnaire within 24 hours", inline=False)
        emb.add_field(name="User ID", value=box(str(user_id)), inline=False)
        await ch.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())

    async def _send_kick_fail_embed(self, guild, member, user_id, reason: str):
        alert_channel_id = await self.config.guild(guild).alert_channel()
        ch = guild.get_channel(alert_channel_id) if alert_channel_id else None
        if not ch:
            return
        mention = (member.mention if member else f"<@{user_id}>")
        emb = discord.Embed(
            title="❌ Auto-Kick Failed",
            description=f"Cannot kick {mention}.",
            color=discord.Color.red(),
            timestamp=datetime.now(pytz.utc),
        )
        emb.add_field(name="Reason", value=reason, inline=False)
        emb.add_field(name="User ID", value=box(str(user_id)), inline=False)
        await ch.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())

    async def _send_kick_error_embed(self, guild, member, user_id, errtype: str, details: str):
        alert_channel_id = await self.config.guild(guild).alert_channel()
        ch = guild.get_channel(alert_channel_id) if alert_channel_id else None
        if not ch:
            return
        mention = (member.mention if member else f"<@{user_id}>")
        emb = discord.Embed(
            title="❌ Auto-Kick Failed",
            description=f"Cannot kick {mention}.",
            color=discord.Color.red(),
            timestamp=datetime.now(pytz.utc),
        )
        emb.add_field(name="Error Type", value=errtype, inline=False)
        emb.add_field(name="Details", value=details[:1024], inline=False)
        emb.add_field(name="User ID", value=box(str(user_id)), inline=False)
        await ch.send(embed=emb, allowed_mentions=discord.AllowedMentions.none())    
        async def send_questionnaire(self, guild: discord.Guild, member: discord.Member) -> dict:
            questions = await self.config.guild(guild).questionnaire_questions()
        
            if not questions:
                return {"success": False, "message": "No questionnaire questions configured. Use `/sus addquestion` first."}
        
            async with self.config.guild(guild).pending_questionnaires() as pending:
                if str(member.id) in pending:
                    return {"success": False, "message": "Questionnaire already sent to this user."}
        
            dm_sent = await self.send_questionnaire_dm(member, guild)
        
            ticket_channel = None
            if not dm_sent:
                ticket_channel = await self.create_ticket_channel(guild, member)
                if not ticket_channel:
                    now = datetime.now(pytz.utc)
                    expires = now + timedelta(hours=24)
                
                    async with self.config.guild(guild).pending_questionnaires() as pending:
                        pending[str(member.id)] = {
                            "sent_at": now.isoformat(),
                            "expires_at": expires.isoformat(),
                            "ticket_channel_id": None,
                            "delivery_failed": True
                        }
                
                    alert_channel_id = await self.config.guild(guild).alert_channel()
                    if alert_channel_id:
                        alert_channel = guild.get_channel(alert_channel_id)
                        if alert_channel:
                            embed = discord.Embed(
                                title="⚠️ Questionnaire Delivery Failed",
                                description=(
                                    f"Failed to send questionnaire to {member.mention} ({member.name}).\n"
                                    f"DMs are disabled and ticket creation failed.\n\n"
                                    f"**User will still be kicked in 24 hours.**"
                                ),
                                color=discord.Color.orange(),
                                timestamp=datetime.now(pytz.utc)
                            )
                            embed.add_field(name="User ID", value=box(str(member.id)), inline=False)
                            await alert_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                
                    return {
                        "success": True,
                        "message": (
                            f"⚠️ Failed to send questionnaire to {member.mention} "
                            f"(DMs disabled and ticket creation failed). "
                            f"User will still be kicked in 24 hours."
                        )
                    }
        
            now = datetime.now(pytz.utc)
            expires = now + timedelta(hours=24)
        
            async with self.config.guild(guild).pending_questionnaires() as pending:
                pending[str(member.id)] = {
                    "sent_at": now.isoformat(),
                    "expires_at": expires.isoformat(),
                    "ticket_channel_id": ticket_channel.id if ticket_channel else None
                }
        
            if dm_sent:
                return {"success": True, "message": f"✅ Questionnaire sent to {member.mention} via DM. They have 24 hours to complete it."}
            else:
                return {"success": True, "message": f"✅ Questionnaire ticket created for {member.mention} in {ticket_channel.mention}. They have 24 hours to complete it."}
    
        async def mark_user_suspicious(self, guild: discord.Guild, member: discord.Member, marked_by: discord.Member = None) -> dict:
            settings = await self.config.guild(guild).all()
        
            suspicious_role_id = settings.get("suspicious_role")
            if not suspicious_role_id:
                return {"success": False, "message": "Suspicious role not configured. Use `/sus setrole` first."}
        
            suspicious_role = guild.get_role(suspicious_role_id)
            if not suspicious_role:
                return {"success": False, "message": "Suspicious role not found."}
        
            if not guild.me.guild_permissions.manage_roles:
                return {"success": False, "message": "I don't have permission to manage roles."}
        
            if suspicious_role >= guild.me.top_role:
                return {"success": False, "message": "The suspicious role is higher than my highest role."}
        
            current_roles = [r.id for r in member.roles if r != guild.default_role and not r.managed and r < guild.me.top_role]
            await self.config.member(member).saved_roles.set(current_roles)
        
            try:
                roles_to_remove = [r for r in member.roles if r != guild.default_role and not r.managed and r < guild.me.top_role]
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Marked as suspicious")
                await member.add_roles(suspicious_role, reason="Marked as suspicious")
            except discord.Forbidden:
                return {"success": False, "message": "I don't have permission to manage roles for this user."}
            except Exception as e:
                return {"success": False, "message": f"Error managing roles: {e}"}
        
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
                
                    embed.set_thumbnail(url=member.display_avatar.url)
                
                    mention_role_id = settings.get("mention_role")
                    mention_text = ""
                    mention_role = None
                    if mention_role_id:
                        mention_role = guild.get_role(mention_role_id)
                        if mention_role:
                            mention_text = mention_role.mention
                
                    await alert_channel.send(
                        mention_text,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=[mention_role] if mention_role else [])
                    )
        
            result = await self.send_questionnaire(guild, member)
        
            return result
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        settings = await self.config.guild(member.guild).all()
        min_account_age = settings.get("min_account_age", 7)
        account_age = (datetime.now(pytz.utc) - member.created_at.replace(tzinfo=pytz.utc)).days
        if account_age >= min_account_age:
            return
        alert_channel_id = settings.get("alert_channel")
        if not alert_channel_id:
            return
        alert_channel = member.guild.get_channel(alert_channel_id)
        if not alert_channel:
            return
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
        embed.set_thumbnail(url=member.display_avatar.url)
        view = SuspiciousUserView(self)
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
        if member.bot:
            return
        
        ticket_channel_id = None
        async with self.config.guild(member.guild).pending_questionnaires() as pending:
            if str(member.id) in pending:
                ticket_channel_id = pending[str(member.id)].get("ticket_channel_id")
                del pending[str(member.id)]
        
        if ticket_channel_id:
            ticket_channel = member.guild.get_channel(ticket_channel_id)
            if ticket_channel:
                try:
                    await ticket_channel.delete(reason=f"{member} left the server")
                except Exception:
                    pass
        
        await self.config.member(member).saved_roles.set([])
    
    def _create_sus_group(self):
        sus_group = app_commands.Group(
            name="sus",
            description="Suspicious User Monitor commands",
            guild_only=True,
            default_permissions=discord.Permissions(administrator=True)
        )
        
        @sus_group.command(name="setrole", description="Set the role to assign to suspicious users")
        @app_commands.describe(role="The role to assign to suspicious users")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setrole_slash(interaction: discord.Interaction, role: discord.Role):
            await self.config.guild(interaction.guild).suspicious_role.set(role.id)
            await interaction.response.send_message(f"Suspicious role set to {role.mention}.", ephemeral=True)
        
        @sus_group.command(name="setchannel", description="Set the alert/review channel")
        @app_commands.describe(channel="The channel for alerts and questionnaire reviews")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setchannel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
            await self.config.guild(interaction.guild).alert_channel.set(channel.id)
            await interaction.response.send_message(f"Alert/review channel set to {channel.mention}.", ephemeral=True)
        
        @sus_group.command(name="setcategory", description="Set the category for questionnaire tickets")
        @app_commands.describe(category="The category for questionnaire ticket channels")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setcategory_slash(interaction: discord.Interaction, category: discord.CategoryChannel):
            await self.config.guild(interaction.guild).ticket_category.set(category.id)
            await interaction.response.send_message(f"Ticket category set to **{category.name}**.", ephemeral=True)
        
        @sus_group.command(name="setaccountage", description="Set minimum account age in days")
        @app_commands.describe(days="Minimum account age in days")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()
        async def setaccountage_slash(interaction: discord.Interaction, days: int):
            if days < 0:
                return await interaction.response.send_message("Days must be 0 or positive.", ephemeral=True)
            await self.config.guild(interaction.guild).min_account_age.set(days)
            await interaction.response.send_message(f"Minimum account age set to {days} days.", ephemeral=True)
        
        @sus_group.command(name="setmention", description="Set the role to mention for alerts")
        @app_commands.describe(role="The role to mention when suspicious users are detected")
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
        if not await self.has_staff_role(interaction):
            return await interaction.response.send_message(
                "You don't have permission to use this command. Contact an administrator to set up staff roles.",
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        if user.bot:
            return await interaction.followup.send("You cannot mark bots as suspicious.", ephemeral=True)
        
        if user.id == interaction.guild.owner_id:
            return await interaction.followup.send("You cannot mark the server owner as suspicious.", ephemeral=True)
        
        if user.top_role > interaction.guild.me.top_role:
            return await interaction.followup.send(
                f"I cannot manage this user's roles due to role hierarchy.\n"
                f"User's top role: {user.top_role.name} (position {user.top_role.position})\n"
                f"My top role: {interaction.guild.me.top_role.name} (position {interaction.guild.me.top_role.position})",
                ephemeral=True
            )
        
        result = await self.mark_user_suspicious(interaction.guild, user, interaction.user)
        await interaction.followup.send(result["message"], ephemeral=True)
