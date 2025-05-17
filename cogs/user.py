# TODO: Add other commands, /help, ...
from discord.ext import commands
from discord import app_commands
from logging import info
import random

class UserCommands(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  
  @commands.Cog.listener()
  async def on_ready(self):
    #await self.bot.add_command(self.hello)
    synced = await self.bot.tree.sync()
    info(f'Synced {synced} user commands.')
  

  @app_commands.command(name='hello')
  async def hello(self, ctx):
    """ Greet the bot! """
    greetings = "Hello %s, Hiya %s, What's up %s?, wuzza %s, wuzzzaaaa %s, what's happening %s?, what it do %s, howdy %s, %s in the house".split(', ')
    info(dir(ctx))
    greeting = random.choice(greetings)#.replace('%s', ctx.author.name)
    await ctx.send(f'{greeting}\nType `!help` in #howsy-bot for more information!')


async def setup(bot):
  await bot.add_cog(UserCommands(bot))
