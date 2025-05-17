from discord.ext import commands, tasks
from logging import debug, info
import random, time
import logging

class Random(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self.interval = int(self.bot.cfg.randomness)
    self.randomness.change_interval(minutes=self.interval)
    self.randomness.start()

  @commands.Cog.listener()
  async def on_ready(self):
    debug('Randomness task starting')

  async def cog_unload(self):
    self.randomness.cancel()

  @tasks.loop(minutes=30)
  async def randomness(self, topic=None, show=True):
    # wait until we've been up for a minute
    info('Checking randomness...')
    if show and (time.time() - self.bot.starttime < 60):
      return
    output = ''

    #if time.time() - self.bot.lastspoke > (60 * 60 * 6):
    chance = random.randint(0,100)
    #if chance < 25:
    #  output = oai.q('Tell a random joke')
    if chance < 40:
      info('Randomness: Factoid')
      prompt = 'Tell me a random factoid' + f' about {topic}' if topic else ''
      output = await self.bot.get_cog('Public').generate(prompt, system='librarian',length=256)
    #elif chance < 60:
    #  output = oai.q('What is a random important fact?')
    elif chance > 70:
      info('Randomness: Dream Journal')
      output = await self.bot.get_cog('Public').dream()
      
    if len(output):
      if show:
        await self.bot.get_channel(self.bot.cfg.homeid).send(f'... *{output}* ...')
        self.bot.lastspoke = time.time()
      else:
        return output
    else:
      return ''

async def setup(bot):
    await bot.add_cog(Random(bot))

# vim:ts=2:sw=2
