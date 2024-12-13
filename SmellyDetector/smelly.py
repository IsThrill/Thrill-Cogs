import discord
from redbot.core import commands, app_commands
import random

class Smelly(commands.Cog):
    """A cog that determines how smelly you are."""

    def __init__(self, bot):
        self.bot = bot

    # Hybrid command to support both prefix and slash
    @commands.hybrid_command()
    @app_commands.describe(reason="Just a fun way to find out your smelliness!")
    async def smelly(self, ctx: commands.Context, *, reason: str = None):
        """
        Determine how smelly you are with a fun response.
        """
        smelliness = random.randint(0, 100)
        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{ctx.author.mention}, your smelliness level is **{smelliness}%**! 🌸",
            color=discord.Color.random()
        )
        
        if reason:
            embed.add_field(name="Reason:", value=f"{reason}")

        await ctx.send(embed=embed)

    # Slash command-only version if someone uses native slash commands
    @commands.slash_command(name="smelly", description="Determine your smelliness")
    async def smelly_slash(self, ctx: discord.ApplicationContext):
        """
        A slash command version of the smelly detection.
        """
        smelliness = random.randint(0, 100)

        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{ctx.author.mention}, your smelliness level is **{smelliness}%**! 🥸",
            color=discord.Color.green()
        )
        
        await ctx.respond(embed=embed)
