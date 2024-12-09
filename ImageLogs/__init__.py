from redbot.core import commands

from .image_delete_logger import ImageDeleteLogger

async def setup(bot: commands.Bot):

    image_logger = ImageDeleteLogger(bot)
    
    # Add the cog to the bot
    await bot.add_cog(image_logger)
