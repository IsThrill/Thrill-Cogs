from redbot.core import commands

from .imagedeletelogger import ImageDeleteLogger

async def setup(bot: commands.Bot):
    """Setup function for the cog, adding it to the bot."""
    image_logger = ImageDeleteLogger(bot)
    await bot.add_cog(image_logger)
