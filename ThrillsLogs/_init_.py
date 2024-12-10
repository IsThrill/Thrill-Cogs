from .thrillslogs import ThrillsLogs

async def setup(bot):
    cog = ThrillsLogs(bot)
    await bot.add_cog(cog)