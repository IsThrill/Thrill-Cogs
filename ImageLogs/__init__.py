from redbot.core import commands

from .imagedeletelogger import ImageDeleteLogger

async def setup(bot: commands.Bot):

    image_logger = ImageDeleteLogger(bot)
    
    # Add the cog to the bot
    await bot.add_cog(image_logger)
