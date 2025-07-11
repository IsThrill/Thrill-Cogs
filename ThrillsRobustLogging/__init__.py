from .core import ThrillsRobustLogging

async def setup(bot):
    """The setup function for the Thrills Robust Logging cog."""
    await bot.add_cog(ThrillsRobustLogging(bot))