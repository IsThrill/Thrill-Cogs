import discord
from redbot.core import commands, app_commands
import random

class Smelly(commands.Cog):
    """A cog that determines how smelly you are."""

    def __init__(self, bot):
        self.bot = bot

    # Hybrid command (both prefix and slash support)
    @commands.hybrid_command(name="smelly", description="Determine how smelly you are!")
    @app_commands.describe(target="The user you want to check smelliness for")
    async def smelly(self, ctx: commands.Context, target: discord.Member = None):
        target = target or ctx.author  # If no target is provided, default to the command invoker

        smelliness = random.randint(0, 100)

        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{target.mention}, your smelliness level is **{smelliness}%**! 🌸",
            color=discord.Color.random()
        )

        await ctx.send(embed=embed)
