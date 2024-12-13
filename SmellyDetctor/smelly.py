import discord
from discord.ext import commands
from redbot.core import commands
import random

class Smelly(commands.Cog):
    """A cog that determines how smelly you are."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Cog {self.__class__.__name__} is ready.")

    @commands.slash_command(name="smelly", description="Find out how smelly you are!")
    async def smelly(self, ctx: discord.ApplicationContext):
        """Slash command to determine your smelliness."""
        smelliness = random.randint(0, 100)
        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{ctx.author.mention}, your smelliness level is **{smelliness}%**! 👃",
            color=discord.Color.random()
        )
        await ctx.respond(embed=embed)

