# TODO: Reload/restart
#       Edit personas
#       View/edit configuration

from discord.ext import commands, tasks
from aiohttp import web
import json
from logging import info, debug
from util.oai import personas


class WebAPI(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  
  @commands.Cog.listener()
  async def on_ready(self):
    if self.bot.cfg.webui:
      await self.start_web_ui()
  
  
  async def start_web_ui(self):
    # TODO: Add an API key
    app = web.Application()
    app.add_routes([
                    web.post('/api/persona', self.edit_persona),
                    web.get('/api/personas', self.list_personas),
                    web.get('/api/config', self.list_config),
                    web.get('/api/logs', self.list_logs)
                   ])
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', self.bot.cfg.webui_port)
    await site.start()
    
    info('Web UI Started on port {}.'.format(self.bot.cfg.webui_port))


  async def list_config(self, request):
      debug(f'Request: {request}')
      return web.Response(text=json.dumps(self.bot.cfg.__dict__))


  async def edit_persona(self, request):
      with await request.json() as res:
        new_persona = res['persona']
        new_text = res['text']
        
        debug(f'Updating persona "{new_persona}"')
        self.bot.cfg.persona = new_persona
        self.bot.cfg.personas[new_persona] = new_text
        return web.Response(text=json.dumps({'text': self.bot.cfg.personas[new_persona]}))

  
  async def list_personas(self, request):
      debug(f'Request: {request}')
      return web.Response(text=json.dumps(oai.personas))


  async def list_logs(self, request):
      debug(f'Request: {request}')
      return web.Response(text=json.dumps(self.bot._irclog))


async def setup(bot):
  await bot.add_cog(WebAPI(bot))

# vim:ts=2:sw=2
