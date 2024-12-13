import discord
from redbot.core import commands
import random

class Smelly(commands.Cog):
    """A cog that determines how smelly you are."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="smelly")
    async def smelly(self, ctx: commands.Context):
        """Find out how smelly you are."""
        smelliness = random.randint(0, 100)
        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{ctx.author.mention}, your smelliness level is **{smelliness}%**! \ud83d\udc43",
            color=discord.Color.random()
        )
        await ctx.send(embed=embed)
