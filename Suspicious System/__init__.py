from .suspicioususermonitor import SuspiciousUserMonitor

async def setup(bot):
    await bot.add_cog(SuspiciousUserMonitor(bot))
