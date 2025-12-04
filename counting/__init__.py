from redbot.core.bot import Red

from .counting import Counting

__red_end_user_data_statement__ = (
    "This cog stores user IDs and counting statistics (count totals and timestamps) "
    "for leaderboard and stats functionality. This data is stored both per-guild "
    "(leaderboard entries) and globally per-user (personal count totals and last count timestamp). "
    "Users can request deletion of their data by contacting the bot owner."
)


async def setup(bot: Red) -> None:
    cog = Counting(bot)
    await bot.add_cog(cog)
