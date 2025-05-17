from discord.ext import commands, tasks
from logging import info
import logging

class Cron(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.Cog.listener()
  async def on_ready(self):
    self.cron.start()
    info('Cron task starting')
	
  async def cog_unload(self):
    self.cron.cancel()
  
  @tasks.loop(minutes=1.0)
  async def cron(self):
    if int(self.bot.cfg.debug):
      if logging.root.getEffectiveLevel() != logging.DEBUG:
        info('Setting debug mode.')
        logging.root.setLevel(logging.DEBUG)
    else:
      if logging.root.getEffectiveLevel() != logging.INFO:
        info('Setting debug mode OFF.')
        logging.root.setLevel(logging.INFO)
    try:
      await self.bot.setpresence(mode=self.bot.cfg.mode)
    except Exception as e:
      info(f'Setting presence: {e}')

    await self.bot.savelogs()

async def setup(bot):
    await bot.add_cog(Cron(bot))

# vim:ts=2:sw=2
