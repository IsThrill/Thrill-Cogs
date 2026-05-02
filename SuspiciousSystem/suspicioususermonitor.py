import asyncio
import logging
import discord
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from discord import app_commands
from discord.ui import Button, Modal, TextInput, View
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box

log = logging.getLogger("red.suspicioususermonitor")


# ─────────────────────────────────────────────────────────────────────────────
# Modal
# ─────────────────────────────────────────────────────────────────────────────


class VerificationModal(Modal):
    def __init__(
        self,
        cog: "SuspiciousUserMonitor",
        guild_id: int,
        questions: list[str],
    ) -> None:
        super().__init__(title="Account Verification", timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.questions = questions[:5]
        self._inputs: list[TextInput] = []

        for i, q in enumerate(self.questions):
            is_url = "vrchat" in q.lower()
            inp = TextInput(
                label=q[:45],
                style=discord.TextStyle.short if is_url else discord.TextStyle.paragraph,
                placeholder=(
                    "https://vrchat.com/home/user/usr_xxxxxxxx-…"
                    if is_url
                    else (q[:100] if len(q) > 45 else None)
                ),
                required=True,
                max_length=300 if is_url else 500,
                row=i,
            )
            self._inputs.append(inp)
            self.add_item(inp)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        guild = self.cog.bot.get_guild(self.guild_id)
        if not guild:
            return await interaction.followup.send(
                "❌ Server not found. Please contact staff directly.", ephemeral=True
            )

        settings = await self.cog.config.guild(guild).all()
        alert_channel_id = settings.get("alert_channel")
        if not alert_channel_id:
            return await interaction.followup.send(
                "❌ Alert channel is not configured. Please contact staff.", ephemeral=True
            )

        alert_channel = guild.get_channel(alert_channel_id)
        if not alert_channel:
            return await interaction.followup.send(
                "❌ Alert channel not found. Please contact staff.", ephemeral=True
            )

        user = interaction.user
        account_age = (
            datetime.now(timezone.utc) - user.created_at.replace(tzinfo=timezone.utc)
        ).days

        embed = discord.Embed(
            title="📋 Verification Submission",
            description=(
                f"**{user}** (`{user.id}`) has submitted their verification.\n"
                "Staff — please review and Approve or Deny below."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User ID", value=box(str(user.id)), inline=True)
        embed.add_field(name="Account Age", value=f"{account_age} days", inline=True)
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(user.created_at, "D"),
            inline=True,
        )

        for i, (q, inp) in enumerate(zip(self.questions, self._inputs), 1):
            val = inp.value or "*No response provided*"
            is_url = "vrchat" in q.lower()
            if is_url and val.strip().startswith("http"):
                display = (
                    f"[🌐 Open VRChat Profile]({val.strip()})\n"
                    f"`{val.strip()[:250]}`"
                )
            else:
                display = val[:1024]
            embed.add_field(name=f"Q{i} — {q[:100]}", value=display, inline=False)

        embed.set_footer(text=f"Server: {guild.name}")

        mention_role: Optional[discord.Role] = None
        mention_role_id = settings.get("mention_role")
        if mention_role_id:
            mention_role = guild.get_role(mention_role_id)

        view = SubmissionReviewView(self.cog)
        try:
            await alert_channel.send(
                content=(
                    f"{mention_role.mention} — New verification submission needs review!"
                    if mention_role
                    else "New verification submission needs review!"
                ),
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    roles=[mention_role] if mention_role else []
                ),
            )
        except Exception as exc:
            log.error("Error posting submission for user %s: %s", user.id, exc)
            return await interaction.followup.send(
                "❌ Could not submit your answers. Please contact staff directly.",
                ephemeral=True,
            )

        async with self.cog.config.guild(guild).pending_verifications() as pv:
            pv.pop(str(user.id), None)

        await interaction.followup.send(
            "✅ Your verification has been submitted!\n"
            "Staff will review your answers and contact you via DM with the outcome.",
            ephemeral=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Persistent Views
# ─────────────────────────────────────────────────────────────────────────────


class VerificationView(View):
    def __init__(self, cog: "SuspiciousUserMonitor") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Begin Verification",
        style=discord.ButtonStyle.primary,
        emoji="🔐",
        custom_id="sus:begin_verification",
    )
    async def begin(self, interaction: discord.Interaction, button: Button) -> None:
        user_id = interaction.user.id

        guild_id: Optional[int] = None
        for g in self.cog.bot.guilds:
            pv = await self.cog.config.guild(g).pending_verifications()
            if str(user_id) in pv:
                guild_id = g.id
                break

        if guild_id is None:
            return await interaction.response.send_message(
                "❌ Your verification session has expired or was already submitted.\n"
                "If you believe this is an error, please contact the server staff directly.",
                ephemeral=True,
            )

        guild = self.cog.bot.get_guild(guild_id)
        if not guild:
            return await interaction.response.send_message(
                "❌ Server not found.", ephemeral=True
            )

        questions = await self.cog.config.guild(guild).questionnaire_questions()
        if not questions:
            return await interaction.response.send_message(
                "❌ No verification questions are set up yet. Please contact staff.",
                ephemeral=True,
            )

        modal = VerificationModal(self.cog, guild_id, questions)
        await interaction.response.send_modal(modal)


class SubmissionReviewView(View):
    def __init__(self, cog: "SuspiciousUserMonitor") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @staticmethod
    def _extract_user_id(msg: discord.Message) -> Optional[int]:
        if not msg.embeds:
            return None
        for field in msg.embeds[0].fields:
            if field.name == "User ID":
                try:
                    return int(field.value.strip("`").strip())
                except (ValueError, AttributeError):
                    pass
        return None

    async def _check_staff(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        staff_role_id = await self.cog.config.guild(interaction.guild).staff_role()
        if staff_role_id:
            role = interaction.guild.get_role(staff_role_id)
            if role and role in interaction.user.roles:
                return True
        await interaction.response.send_message(
            "❌ You need the configured staff role to use this.", ephemeral=True
        )
        return False

    async def _resolve_user(self, user_id: int) -> Optional[discord.User]:
        user = self.cog.bot.get_user(user_id)
        if not user:
            try:
                user = await self.cog.bot.fetch_user(user_id)
            except Exception:
                pass
        return user

    @discord.ui.button(
        label="✅  Approve",
        style=discord.ButtonStyle.success,
        custom_id="sus:approve_submission",
    )
    async def approve(self, interaction: discord.Interaction, button: Button) -> None:
        if not await self._check_staff(interaction):
            return

        user_id = self._extract_user_id(interaction.message)
        if not user_id:
            return await interaction.response.send_message(
                "❌ Could not read User ID from embed.", ephemeral=True
            )

        await interaction.response.defer()
        guild = interaction.guild
        settings = await self.cog.config.guild(guild).all()

        async with self.cog.config.guild(guild).whitelisted_users() as wl:
            if user_id not in wl:
                wl.append(user_id)

        async with self.cog.config.guild(guild).dm_fail_counts() as dfc:
            dfc.pop(str(user_id), None)
        async with self.cog.config.guild(guild).pending_verifications() as pv:
            pv.pop(str(user_id), None)

        invite_url: Optional[str] = None
        invite_channel_id = settings.get("invite_channel") or settings.get("alert_channel")
        if invite_channel_id:
            ch = guild.get_channel(invite_channel_id)
            if ch:
                try:
                    inv = await ch.create_invite(
                        max_age=86400,
                        max_uses=1,
                        unique=True,
                        reason=f"Approved verification — user {user_id}",
                    )
                    invite_url = inv.url
                except Exception as exc:
                    log.warning("Could not create invite for approved user %s: %s", user_id, exc)

        user = await self._resolve_user(user_id)
        if user:
            try:
                dm_embed = discord.Embed(
                    title="✅ Verification Approved!",
                    description=(
                        f"Your verification for **{guild.name}** has been reviewed "
                        f"and **approved** by staff!\n\n"
                        f"You have been whitelisted — you may rejoin the server at any time."
                    ),
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc),
                )
                if invite_url:
                    dm_embed.add_field(
                        name="🔗 Rejoin Link",
                        value=(
                            f"[Click here to rejoin **{guild.name}**]({invite_url})\n"
                            f"*(Single-use · Expires in 24 hours)*"
                        ),
                        inline=False,
                    )
                dm_embed.set_footer(
                    text=guild.name,
                    icon_url=guild.icon.url if guild.icon else None,
                )
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                log.warning("Could not DM approved user %s — DMs closed.", user_id)

        embed = interaction.message.embeds[0].copy()
        embed.color = discord.Color.green()
        embed.add_field(
            name="✅ Approved",
            value=(
                f"By {interaction.user.mention}\n"
                f"{discord.utils.format_dt(datetime.now(timezone.utc), 'R')}"
            ),
            inline=False,
        )
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        log.info(
            "Verification approved: user %s in %s by %s", user_id, guild, interaction.user
        )

    @discord.ui.button(
        label="❌  Deny & Ban",
        style=discord.ButtonStyle.danger,
        custom_id="sus:deny_submission",
    )
    async def deny(self, interaction: discord.Interaction, button: Button) -> None:
        if not await self._check_staff(interaction):
            return

        user_id = self._extract_user_id(interaction.message)
        if not user_id:
            return await interaction.response.send_message(
                "❌ Could not read User ID from embed.", ephemeral=True
            )

        await interaction.response.defer()
        guild = interaction.guild

        async with self.cog.config.guild(guild).pending_verifications() as pv:
            pv.pop(str(user_id), None)

        user = await self._resolve_user(user_id)
        if user:
            try:
                dm_embed = discord.Embed(
                    title="❌ Verification Denied",
                    description=(
                        f"Your verification for **{guild.name}** was reviewed and **denied** by staff.\n\n"
                        f"As a result, you have been permanently banned from the server."
                    ),
                    color=discord.Color.dark_red(),
                    timestamp=datetime.now(timezone.utc),
                )
                dm_embed.set_footer(
                    text=guild.name,
                    icon_url=guild.icon.url if guild.icon else None,
                )
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        try:
            await guild.ban(
                discord.Object(id=user_id),
                reason=f"Verification denied by {interaction.user}",
                delete_message_days=0,
            )
        except discord.Forbidden:
            log.warning("Missing permissions to ban user %s in %s.", user_id, guild)
        except Exception as exc:
            log.error("Ban error for user %s: %s", user_id, exc)

        embed = interaction.message.embeds[0].copy()
        embed.color = discord.Color.dark_red()
        embed.add_field(
            name="❌ Denied & Banned",
            value=(
                f"By {interaction.user.mention}\n"
                f"{discord.utils.format_dt(datetime.now(timezone.utc), 'R')}"
            ),
            inline=False,
        )
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        log.info(
            "Verification denied + banned: user %s in %s by %s",
            user_id, guild, interaction.user,
        )


class FlaggedAlertView(View):
    def __init__(self, cog: "SuspiciousUserMonitor") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @staticmethod
    def _extract_user_id(msg: discord.Message) -> Optional[int]:
        if not msg.embeds:
            return None
        for field in msg.embeds[0].fields:
            if field.name == "User ID":
                try:
                    return int(field.value.strip("`").strip())
                except (ValueError, AttributeError):
                    pass
        return None

    async def _check_staff(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.ban_members:
            return True
        staff_role_id = await self.cog.config.guild(interaction.guild).staff_role()
        if staff_role_id:
            role = interaction.guild.get_role(staff_role_id)
            if role and role in interaction.user.roles:
                return True
        await interaction.response.send_message(
            "❌ You need the configured staff role to use this.", ephemeral=True
        )
        return False

    @staticmethod
    async def _is_banned(guild: discord.Guild, user_id: int) -> bool:
        try:
            await guild.fetch_ban(discord.Object(id=user_id))
            return True
        except discord.NotFound:
            return False
        except Exception:
            return False

    @discord.ui.button(
        label="🔨  Ban User",
        style=discord.ButtonStyle.danger,
        custom_id="sus:alert_ban",
    )
    async def ban_btn(self, interaction: discord.Interaction, button: Button) -> None:
        if not await self._check_staff(interaction):
            return

        user_id = self._extract_user_id(interaction.message)
        if not user_id:
            return await interaction.response.send_message(
                "❌ User ID not found in embed.", ephemeral=True
            )

        if await self._is_banned(interaction.guild, user_id):
            return await interaction.response.send_message(
                "ℹ️ This user is already banned.", ephemeral=True
            )

        await interaction.response.defer()
        try:
            await interaction.guild.ban(
                discord.Object(id=user_id),
                reason=f"Banned by {interaction.user} via suspicious-user alert",
                delete_message_days=0,
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to ban this user.", ephemeral=True
            )
        except Exception as exc:
            return await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)

        embed = interaction.message.embeds[0].copy()
        embed.add_field(
            name="🔨 Manually Banned",
            value=(
                f"By {interaction.user.mention}\n"
                f"{discord.utils.format_dt(datetime.now(timezone.utc), 'R')}"
            ),
            inline=False,
        )
        for child in self.children:
            if child.custom_id == "sus:alert_ban":
                child.disabled = True
                child.label = "🔨  Banned"
            elif child.custom_id == "sus:alert_unban":
                child.disabled = False
        await interaction.message.edit(embed=embed, view=self)
        log.info(
            "User %s manually banned in %s by %s", user_id, interaction.guild, interaction.user
        )

    @discord.ui.button(
        label="🔓  Unban User",
        style=discord.ButtonStyle.secondary,
        custom_id="sus:alert_unban",
        disabled=True,
    )
    async def unban_btn(self, interaction: discord.Interaction, button: Button) -> None:
        if not await self._check_staff(interaction):
            return

        user_id = self._extract_user_id(interaction.message)
        if not user_id:
            return await interaction.response.send_message(
                "❌ User ID not found in embed.", ephemeral=True
            )

        await interaction.response.defer()
        try:
            await interaction.guild.unban(
                discord.Object(id=user_id),
                reason=f"Unbanned by {interaction.user}",
            )
        except discord.NotFound:
            return await interaction.followup.send(
                "ℹ️ This user is not currently banned.", ephemeral=True
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to unban.", ephemeral=True
            )
        except Exception as exc:
            return await interaction.followup.send(f"❌ Error: {exc}", ephemeral=True)

        embed = interaction.message.embeds[0].copy()
        embed.add_field(
            name="🔓 Unbanned",
            value=(
                f"By {interaction.user.mention}\n"
                f"{discord.utils.format_dt(datetime.now(timezone.utc), 'R')}"
            ),
            inline=False,
        )
        for child in self.children:
            if child.custom_id == "sus:alert_ban":
                child.disabled = False
                child.label = "🔨  Ban User"
            elif child.custom_id == "sus:alert_unban":
                child.disabled = True
        await interaction.message.edit(embed=embed, view=self)
        log.info(
            "User %s unbanned in %s by %s", user_id, interaction.guild, interaction.user
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main Cog
# ─────────────────────────────────────────────────────────────────────────────


class SuspiciousUserMonitor(commands.Cog):
    __version__ = "2.0.0"
    __author__ = "custom"

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=9182736450, force_registration=True
        )

        default_guild: dict = {
            "alert_channel": None,
            "verification_channel": None,
            "invite_channel": None,
            "staff_role": None,
            "mention_role": None,
            "min_account_age": 7,
            "questionnaire_questions": [],
            "pending_verifications": {},
            "whitelisted_users": [],
            "dm_fail_counts": {},
        }
        self.config.register_guild(**default_guild)
        self._dm_warn_tasks: dict[str, asyncio.Task] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def cog_load(self) -> None:
        self.bot.add_view(VerificationView(self))
        self.bot.add_view(SubmissionReviewView(self))
        self.bot.add_view(FlaggedAlertView(self))
        log.info(
            "SuspiciousUserMonitor v%s loaded — persistent views registered.",
            self.__version__,
        )

    async def cog_unload(self) -> None:
        for task in self._dm_warn_tasks.values():
            task.cancel()
        self._dm_warn_tasks.clear()
        log.info("SuspiciousUserMonitor unloaded.")

    async def red_delete_data_for_user(
        self, *, requester: str, user_id: int
    ) -> None:
        all_guilds = await self.config.all_guilds()
        uid_str = str(user_id)
        for gid, data in all_guilds.items():
            gcfg = self.config.guild_from_id(int(gid))
            if uid_str in data.get("pending_verifications", {}):
                async with gcfg.pending_verifications() as pv:
                    pv.pop(uid_str, None)
            if uid_str in data.get("dm_fail_counts", {}):
                async with gcfg.dm_fail_counts() as dfc:
                    dfc.pop(uid_str, None)
            if user_id in data.get("whitelisted_users", []):
                async with gcfg.whitelisted_users() as wl:
                    try:
                        wl.remove(user_id)
                    except ValueError:
                        pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _try_send_verification_dm(
        self, member: discord.Member, guild: discord.Guild
    ) -> bool:
        questions = await self.config.guild(guild).questionnaire_questions()
        if not questions:
            log.warning(
                "No questions configured in %s — cannot send verification DM.", guild
            )
            return False

        embed = discord.Embed(
            title="🔒 Account Verification Required",
            description=(
                f"Your account has been flagged as **suspicious** in **{guild.name}** "
                f"because your account age is below our minimum threshold.\n\n"
                f"**To regain access you must complete a short verification form.**\n"
                f"Press **Begin Verification** below to open it.\n\n"
                f"You may be asked to provide your VRChat profile URL and other details "
                f"so our staff can confirm your identity."
            ),
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="Server", value=guild.name, inline=True)
        embed.add_field(name="Questions", value=str(len(questions)), inline=True)
        embed.set_footer(text="This is an automated message — do not reply here.")

        try:
            await member.send(embed=embed, view=VerificationView(self))
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False
        except Exception as exc:
            log.error("Unexpected error sending DM to %s: %s", member, exc)
            return False

    async def _send_staff_alert(
        self,
        guild: discord.Guild,
        member: discord.Member,
        account_age: int,
        reason: str,
        *,
        is_banned: bool = False,
    ) -> None:
        settings = await self.config.guild(guild).all()
        alert_channel_id = settings.get("alert_channel")
        if not alert_channel_id:
            return
        alert_channel = guild.get_channel(alert_channel_id)
        if not alert_channel:
            return

        embed = discord.Embed(
            title="🚨 Suspicious Account Flagged & Removed",
            description=(
                f"**{member}** (`{member.id}`) was automatically removed from the server."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User ID", value=box(str(member.id)), inline=True)
        embed.add_field(name="Account Age", value=f"{account_age} days", inline=True)
        embed.add_field(
            name="Threshold",
            value=f"< {settings.get('min_account_age', 7)} days",
            inline=True,
        )
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(member.created_at, "D"),
            inline=True,
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text="Use the buttons below to ban or unban this user by ID.")

        mention_role: Optional[discord.Role] = None
        mention_role_id = settings.get("mention_role")
        if mention_role_id:
            mention_role = guild.get_role(mention_role_id)

        view = FlaggedAlertView(self)
        if is_banned:
            for child in view.children:
                if child.custom_id == "sus:alert_ban":
                    child.disabled = True
                    child.label = "🔨  Already Banned"
                elif child.custom_id == "sus:alert_unban":
                    child.disabled = False

        await alert_channel.send(
            content=(
                f"{mention_role.mention} — Suspicious account flagged!"
                if mention_role
                else None
            ),
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(
                roles=[mention_role] if mention_role else []
            ),
        )

    async def _handle_dm_disabled(self, member: discord.Member) -> None:
        guild = member.guild
        settings = await self.config.guild(guild).all()
        account_age = (
            datetime.now(timezone.utc) - member.created_at.replace(tzinfo=timezone.utc)
        ).days

        # 1. Post 60-second warning mention
        warn_message: Optional[discord.Message] = None
        vchan_id = settings.get("verification_channel")
        if vchan_id:
            vchan = guild.get_channel(vchan_id)
            if vchan:
                try:
                    warn_message = await vchan.send(
                        f"{member.mention} — ⚠️ **Your account has been flagged as suspicious.**\n"
                        f"Please **enable your Discord DMs** from this server within **1 minute** "
                        f"so we can send you a verification message. "
                        f"Failure to do so will result in your removal from the server."
                    )
                except discord.Forbidden:
                    log.warning(
                        "Cannot post DM-warning in verification channel of %s.", guild
                    )

        # 2. Wait 60 seconds
        await asyncio.sleep(60)

        # 3. Delete the warning
        if warn_message:
            try:
                await warn_message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

        # 4. Confirm member still present
        member = guild.get_member(member.id)
        if not member:
            return

        # 5. Retry DM
        dm_sent = await self._try_send_verification_dm(member, guild)

        if dm_sent:
            async with self.config.guild(guild).pending_verifications() as pv:
                pv[str(member.id)] = {"sent_at": datetime.now(timezone.utc).isoformat()}
            try:
                await guild.kick(
                    member,
                    reason=(
                        "Suspicious account — verification DM sent "
                        "(member re-enabled DMs within the 1-minute window)."
                    ),
                )
            except Exception as exc:
                log.error("Failed to kick %s after delayed DM: %s", member, exc)
            await self._send_staff_alert(
                guild, member, account_age,
                "Account age below threshold — verification DM sent "
                "(member re-enabled DMs within the 1-minute window).",
            )
            return

        # 6. DMs still closed — increment strike counter
        async with self.config.guild(guild).dm_fail_counts() as dfc:
            count = dfc.get(str(member.id), 0) + 1
            dfc[str(member.id)] = count

        if count >= 5:
            reason = (
                f"Permanently banned: refused to enable DMs for verification "
                f"on {count} separate join attempts."
            )
            try:
                await member.send(
                    f"You have been **permanently banned** from **{guild.name}** "
                    f"for refusing to enable your DMs for verification "
                    f"across {count} join attempts."
                )
            except Exception:
                pass
            try:
                await guild.ban(member, reason=reason, delete_message_days=0)
                log.info(
                    "Auto-banned %s in %s after %d DM failures.", member, guild, count
                )
            except Exception as exc:
                log.error("Failed to auto-ban %s: %s", member, exc)
            await self._send_staff_alert(
                guild, member, account_age,
                f"**Auto-banned**: DMs disabled on {count} consecutive join attempts (limit: 5).",
                is_banned=True,
            )
        else:
            try:
                await guild.kick(
                    member,
                    reason=(
                        f"Suspicious account — DMs disabled, could not verify "
                        f"(attempt {count}/5 before auto-ban)."
                    ),
                )
                log.info(
                    "Kicked %s from %s — DMs disabled (failure %d/5).", member, guild, count
                )
            except Exception as exc:
                log.error("Failed to kick %s: %s", member, exc)
            await self._send_staff_alert(
                guild, member, account_age,
                f"DMs disabled — could not deliver verification "
                f"(attempt **{count} / 5** before auto-ban).",
            )

    # ── Event listeners ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return

        guild = member.guild
        settings = await self.config.guild(guild).all()
        min_age: int = settings.get("min_account_age", 7)
        whitelisted: list = settings.get("whitelisted_users", [])

        if member.id in whitelisted:
            return

        account_age = (
            datetime.now(timezone.utc) - member.created_at.replace(tzinfo=timezone.utc)
        ).days

        if account_age >= min_age:
            return

        log.info(
            "Flagging %s in %s — account age %d days (threshold: %d).",
            member, guild, account_age, min_age,
        )

        dm_sent = await self._try_send_verification_dm(member, guild)

        if dm_sent:
            async with self.config.guild(guild).pending_verifications() as pv:
                pv[str(member.id)] = {"sent_at": datetime.now(timezone.utc).isoformat()}
            try:
                await guild.kick(
                    member,
                    reason=(
                        "Account age below threshold — verification DM sent. "
                        "Member may rejoin after completing the form."
                    ),
                )
            except Exception as exc:
                log.error("Failed to kick %s after DM: %s", member, exc)
            await self._send_staff_alert(
                guild, member, account_age,
                "Account age below threshold — verification DM sent, member kicked.",
            )
        else:
            key = f"{guild.id}:{member.id}"
            old = self._dm_warn_tasks.pop(key, None)
            if old:
                old.cancel()
            task = asyncio.create_task(self._handle_dm_disabled(member))
            self._dm_warn_tasks[key] = task
            task.add_done_callback(lambda _t: self._dm_warn_tasks.pop(key, None))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return
        key = f"{member.guild.id}:{member.id}"
        task = self._dm_warn_tasks.pop(key, None)
        if task:
            task.cancel()
        async with self.config.guild(member.guild).pending_verifications() as pv:
            pv.pop(str(member.id), None)

    # ── Hybrid command group ──────────────────────────────────────────────────

    @commands.hybrid_group(
        name="sus",
        description="Suspicious User Monitor — configuration commands",
    )
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def sus(self, ctx: commands.Context) -> None:
        """Suspicious User Monitor configuration. Use a subcommand or /sus <sub>."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @sus.command(name="setchannel", description="Set the staff alert and review channel")
    @app_commands.describe(channel="Channel for staff alerts and submission reviews")
    async def sus_setchannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Set the channel where staff receive alerts and review verification submissions."""
        await self.config.guild(ctx.guild).alert_channel.set(channel.id)
        await ctx.send(f"✅ Alert / review channel set to {channel.mention}.", ephemeral=True)

    @sus.command(
        name="setverificationchannel",
        description="Set the channel to @mention DM-disabled members in",
    )
    @app_commands.describe(channel="Channel where members with DMs off are warned")
    async def sus_setverificationchannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Set the channel the bot uses to warn members who have DMs disabled."""
        await self.config.guild(ctx.guild).verification_channel.set(channel.id)
        await ctx.send(f"✅ DM-warning channel set to {channel.mention}.", ephemeral=True)

    @sus.command(
        name="setinvitechannel",
        description="Set the channel used to generate single-use invite links on approval",
    )
    @app_commands.describe(channel="Channel from which invites are created")
    async def sus_setinvitechannel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Set the channel the bot generates single-use invite links from on approval."""
        await self.config.guild(ctx.guild).invite_channel.set(channel.id)
        await ctx.send(f"✅ Invite generation channel set to {channel.mention}.", ephemeral=True)

    @sus.command(name="setstaffrole", description="Set the staff role for button access")
    @app_commands.describe(role="The staff / moderator role")
    async def sus_setstaffrole(
        self, ctx: commands.Context, role: discord.Role
    ) -> None:
        """Set the role granted access to review buttons and sus configuration commands."""
        await self.config.guild(ctx.guild).staff_role.set(role.id)
        await ctx.send(f"✅ Staff role set to {role.mention}.", ephemeral=True)

    @sus.command(
        name="setmentionrole",
        description="Set the role @mentioned on every suspicious alert",
    )
    @app_commands.describe(role="Role pinged when a suspicious account is flagged")
    async def sus_setmentionrole(
        self, ctx: commands.Context, role: discord.Role
    ) -> None:
        """Set the role that is @mentioned every time a suspicious account is flagged."""
        await self.config.guild(ctx.guild).mention_role.set(role.id)
        await ctx.send(f"✅ Mention / alert role set to {role.mention}.", ephemeral=True)

    @sus.command(name="setage", description="Set the minimum account age threshold in days")
    @app_commands.describe(days="Accounts younger than this number of days are flagged")
    async def sus_setage(self, ctx: commands.Context, days: int) -> None:
        """Set the minimum account age in days. Accounts younger than this trigger the flow."""
        if days < 0:
            return await ctx.send("❌ Days must be 0 or greater.", ephemeral=True)
        await self.config.guild(ctx.guild).min_account_age.set(days)
        await ctx.send(f"✅ Minimum account age set to **{days} day(s)**.", ephemeral=True)

    @sus.command(name="addquestion", description="Add a question to the verification form (max 5)")
    @app_commands.describe(question="Question text shown in the modal form (max 100 characters)")
    async def sus_addquestion(self, ctx: commands.Context, *, question: str) -> None:
        """
        Add a verification question (up to 5 total).

        Include "vrchat" in any question to auto-render it as a URL field.
        Example: `Provide your VRChat profile URL (vrchat.com/home/user/…)`
        """
        if len(question) > 100:
            return await ctx.send(
                "❌ Questions must be **100 characters or fewer**.", ephemeral=True
            )
        async with self.config.guild(ctx.guild).questionnaire_questions() as questions:
            if len(questions) >= 5:
                return await ctx.send(
                    "❌ Maximum of **5 questions** allowed.", ephemeral=True
                )
            questions.append(question)
            count = len(questions)
        await ctx.send(f"✅ Question {count} added:\n> {question}", ephemeral=True)

    @sus.command(name="removequestion", description="Remove a verification question by number")
    @app_commands.describe(number="Question number to remove (1–5)")
    async def sus_removequestion(self, ctx: commands.Context, number: int) -> None:
        """Remove a question by its position in the list."""
        async with self.config.guild(ctx.guild).questionnaire_questions() as questions:
            if not 1 <= number <= len(questions):
                return await ctx.send(
                    f"❌ Invalid number. You have {len(questions)} question(s).",
                    ephemeral=True,
                )
            removed = questions.pop(number - 1)
        await ctx.send(f"✅ Removed question {number}:\n> {removed}", ephemeral=True)

    @sus.command(name="listquestions", description="List all configured verification questions")
    async def sus_listquestions(self, ctx: commands.Context) -> None:
        """Show all questions currently in the verification questionnaire."""
        questions = await self.config.guild(ctx.guild).questionnaire_questions()
        if not questions:
            return await ctx.send(
                "❌ No questions configured. Use `sus addquestion` to add some.",
                ephemeral=True,
            )
        embed = discord.Embed(
            title="📋 Verification Questions",
            description="\n".join(f"**{i}.** {q}" for i, q in enumerate(questions, 1)),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"{len(questions)} / 5 slots used")
        await ctx.send(embed=embed, ephemeral=True)

    @sus.command(name="whitelist", description="Whitelist a user ID to bypass the age check")
    @app_commands.describe(user_id="Discord user ID to whitelist")
    async def sus_whitelist(self, ctx: commands.Context, user_id: str) -> None:
        """Whitelist a user ID — they will pass the age check without triggering the flow."""
        try:
            uid = int(user_id)
        except ValueError:
            return await ctx.send("❌ Invalid user ID.", ephemeral=True)
        async with self.config.guild(ctx.guild).whitelisted_users() as wl:
            if uid in wl:
                return await ctx.send(f"ℹ️ `{uid}` is already whitelisted.", ephemeral=True)
            wl.append(uid)
        await ctx.send(f"✅ User `{uid}` has been whitelisted.", ephemeral=True)

    @sus.command(name="unwhitelist", description="Remove a user ID from the whitelist")
    @app_commands.describe(user_id="Discord user ID to remove from the whitelist")
    async def sus_unwhitelist(self, ctx: commands.Context, user_id: str) -> None:
        """Remove a user from the whitelist — age check applies again on next join."""
        try:
            uid = int(user_id)
        except ValueError:
            return await ctx.send("❌ Invalid user ID.", ephemeral=True)
        async with self.config.guild(ctx.guild).whitelisted_users() as wl:
            if uid not in wl:
                return await ctx.send(f"ℹ️ `{uid}` is not whitelisted.", ephemeral=True)
            wl.remove(uid)
        await ctx.send(f"✅ Removed `{uid}` from the whitelist.", ephemeral=True)

    @sus.command(name="resetfails", description="Reset the DM-fail strike counter for a user")
    @app_commands.describe(user_id="Discord user ID whose DM-fail count should be reset")
    async def sus_resetfails(self, ctx: commands.Context, user_id: str) -> None:
        """
        Reset a user's DM-fail strike counter.
        Users are auto-banned after 5 strikes. Use this if they've fixed their settings.
        """
        try:
            uid = int(user_id)
        except ValueError:
            return await ctx.send("❌ Invalid user ID.", ephemeral=True)
        async with self.config.guild(ctx.guild).dm_fail_counts() as dfc:
            if str(uid) not in dfc:
                return await ctx.send(
                    f"ℹ️ No DM-fail record found for `{uid}`.", ephemeral=True
                )
            del dfc[str(uid)]
        await ctx.send(f"✅ DM-fail counter reset for `{uid}`.", ephemeral=True)

    @sus.command(name="settings", description="Show the current configuration")
    async def sus_settings(self, ctx: commands.Context) -> None:
        """Display the full current configuration for this server."""
        s = await self.config.guild(ctx.guild).all()

        def fmt_ch(cid: Optional[int]) -> str:
            ch = ctx.guild.get_channel(cid) if cid else None
            return ch.mention if ch else "❌ Not set"

        def fmt_role(rid: Optional[int]) -> str:
            r = ctx.guild.get_role(rid) if rid else None
            return r.mention if r else "❌ Not set"

        questions: list = s["questionnaire_questions"]
        dm_fails: dict = s["dm_fail_counts"]
        pending: dict = s["pending_verifications"]
        whitelisted: list = s["whitelisted_users"]

        embed = discord.Embed(
            title="⚙️  Suspicious User Monitor — Settings",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Alert / Review Channel", value=fmt_ch(s["alert_channel"]), inline=True)
        embed.add_field(name="DM-Warning Channel", value=fmt_ch(s["verification_channel"]), inline=True)
        embed.add_field(name="Invite Channel", value=fmt_ch(s["invite_channel"]), inline=True)
        embed.add_field(name="Staff Role", value=fmt_role(s["staff_role"]), inline=True)
        embed.add_field(name="Mention / Alert Role", value=fmt_role(s["mention_role"]), inline=True)
        embed.add_field(name="Min Account Age", value=f"{s['min_account_age']} days", inline=True)
        embed.add_field(name="Questions Configured", value=f"{len(questions)} / 5", inline=True)
        embed.add_field(name="Whitelisted Users", value=str(len(whitelisted)), inline=True)
        embed.add_field(name="Pending Verifications", value=str(len(pending)), inline=True)

        if questions:
            embed.add_field(
                name="Verification Questions",
                value="\n".join(f"`{i}.` {q}" for i, q in enumerate(questions, 1)),
                inline=False,
            )

        if dm_fails:
            top = list(dm_fails.items())[:10]
            fails_text = "\n".join(f"`{uid}` — {cnt} strike(s)" for uid, cnt in top)
            if len(dm_fails) > 10:
                fails_text += f"\n*…and {len(dm_fails) - 10} more*"
            embed.add_field(name="DM-Fail Strikes (Top 10)", value=fails_text, inline=False)

        embed.set_footer(text=f"SuspiciousUserMonitor v{self.__version__}")
        await ctx.send(embed=embed, ephemeral=True)
