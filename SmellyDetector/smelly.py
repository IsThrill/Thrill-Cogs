import discord
from redbot.core import commands, app_commands
import random

class Smelly(commands.Cog):
    """A cog that determines how smelly you are."""

    def __init__(self, bot):
        self.bot = bot

    # Slash command using app_commands
    @app_commands.command(name="smelly", description="Determine your smelliness")
    async def smelly_slash(self, interaction: discord.Interaction):
        smelliness = random.randint(0, 100)

        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{interaction.user.mention}, your smelliness level is **{smelliness}%**! 🥸",
            color=discord.Color.random()
        )

        await interaction.response.send_message(embed=embed)

    # Hybrid command (both prefix and slash support)
    @commands.hybrid_command()
    async def smelly(self, ctx: commands.Context):
        smelliness = random.randint(0, 100)

        embed = discord.Embed(
            title="Smelliness Detector",
            description=f"{ctx.author.mention}, your smelliness level is **{smelliness}%**! 🌸",
            color=discord.Color.random()
        )

        await ctx.send(embed=embed)
