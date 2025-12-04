"""
MIT License

Copyright (c) 2024-present IsThrill
Originally created by ltzmax (2022-2025)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
from datetime import datetime
from typing import Optional

import discord
from redbot.core import commands
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.views import ConfirmView, SimpleMenu
from tabulate import tabulate


class UserCommands(commands.Cog):
    @commands.hybrid_group()
    @commands.guild_only()
    async def counting(self, ctx: commands.Context) -> None:
        """Commands for the counting game."""

    @counting.command(name="stats")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def stats(self, ctx: commands.Context, user: Optional[discord.Member] = None) -> None:
        """Show counting stats for a user from the guild leaderboard."""
        user = user or ctx.author
        if user.bot:
            return await ctx.send("Bots cannot count.")
        
        guild_settings = await self.settings.get_guild_settings(ctx.guild)
        leaderboard = guild_settings.get("leaderboard", {})
        
        user_count = leaderboard.get(user.id, 0)
        
        if user_count == 0:
            return await ctx.send(f"{user.display_name} has not counted yet in this server.")
        
        # Calculate rank
        sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
        rank = next((i + 1 for i, (uid, _) in enumerate(sorted_leaderboard) if uid == user.id), None)
        
        table = tabulate(
            [
                ["User", user.display_name],
                ["Total Counts", cf.humanize_number(user_count)],
                ["Server Rank", f"#{rank}" if rank else "Unranked"],
            ],
            headers=["Stat", "Value"],
            tablefmt="simple",
            stralign="left",
        )
        await ctx.send(box(table, lang='prolog'))

    @counting.command(name="resetme", with_app_command=False)
    @commands.cooldown(1, 360, commands.BucketType.user)
    async def resetme(self, ctx: commands.Context) -> None:
        """
        Reset your counting stats for this server.

        This will clear your count from the server leaderboard.
        This action cannot be undone, so use it carefully with the confirmation prompt.
        """
        guild_settings = await self.settings.get_guild_settings(ctx.guild)
        leaderboard = guild_settings.get("leaderboard", {})
        
        if ctx.author.id not in leaderboard or leaderboard[ctx.author.id] == 0:
            return await ctx.send("You don't have any counts to reset in this server.")
        
        view = ConfirmView(ctx.author, disable_buttons=True)
        view.message = await ctx.send(
            f"Are you sure you want to reset your {cf.humanize_number(leaderboard[ctx.author.id])} counts? This cannot be undone.", 
            view=view
        )
        await view.wait()
        
        if view.result:
            leaderboard[ctx.author.id] = 0
            await self.settings.update_guild(ctx.guild, "leaderboard", leaderboard)
            await ctx.send("Your server counting stats have been reset.")
        else:
            await ctx.send("Reset cancelled.")

    @counting.command(name="leaderboard", aliases=["lb"])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    @commands.bot_has_permissions(embed_links=True)
    async def leaderboard(self, ctx: commands.Context) -> None:
        """
        Show the counting leaderboard for the server.

        Displays the top users with the highest counts, paginated by 15.
        """
        settings = await self.settings.get_guild_settings(ctx.guild)
        leaderboard = settings.get("leaderboard", {})

        if not leaderboard:
            return await ctx.send(
                "No counts recorded yet. Get counting!\n\n"
                f"If you've been counting before this leaderboard was set up, an admin can use:\n"
                f"`{ctx.clean_prefix}countingset misc buildleaderboard` to scan message history."
            )

        filtered_leaderboard = {}
        for key, count in leaderboard.items():
            if count == 0:
                continue
            if isinstance(key, int):
                filtered_leaderboard[key] = count
            elif isinstance(key, str) and key.isdigit():
                filtered_leaderboard[int(key)] = count

        if not filtered_leaderboard:
            return await ctx.send("No counts recorded yet. Get counting!")

        sorted_items = sorted(filtered_leaderboard.items(), key=lambda x: x[1], reverse=True)
        
        display_names = await self._build_display_names(ctx, [uid for uid, _ in sorted_items])

        pages = []
        page_size = 15
        for i in range(0, len(sorted_items), page_size):
            page_items = sorted_items[i : i + page_size]
            table_data = [
                [
                    str(pos),
                    display_names.get(user_id, f"Unknown User"),
                    cf.humanize_number(count),
                ]
                for pos, (user_id, count) in enumerate(page_items, start=i + 1)
            ]
            table = tabulate(
                table_data,
                headers=["Rank", "User", "Counts"],
                tablefmt="simple",
                stralign="left",
            )
            page_num = (i // page_size) + 1
            total_pages = (len(sorted_items) + page_size - 1) // page_size
            embed = discord.Embed(
                title=f"🏆 Counting Leaderboard - Page {page_num}/{total_pages}",
                description=box(table, lang="prolog"),
                color=await ctx.embed_color(),
            )
            embed.set_footer(text=f"Total counters: {len(filtered_leaderboard)}")
            pages.append(embed)

        await SimpleMenu(pages, disable_after_timeout=True, timeout=120).start(ctx)

    async def _build_display_names(self, ctx: commands.Context, user_ids: list[int]) -> dict:
        """
        Efficiently build a mapping of user_id to display_name.

        Prioritizes guild members, then parallel-fetches missing users via API.
        """
        display_names = {}
        
        member_map = {m.id: m.display_name for m in ctx.guild.members if m.id in set(user_ids)}
        display_names.update(member_map)
        
        missing_ids = [uid for uid in user_ids if uid not in member_map]
        
        if missing_ids:
            fetch_tasks = [self.bot.fetch_user(uid) for uid in missing_ids]
            fetched_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            for result, uid in zip(fetched_results, missing_ids):
                if isinstance(result, (discord.User, discord.Member)):
                    display_names[uid] = result.display_name
                else:
                    display_names[uid] = f"Unknown User"
