#!python
version = '0.4d'
sourceurl = 'http://github.com/tecknowledge/howbot'

import logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s %(levelname)s %(funcName)s %(threadName)s(%(lineno)d) -%(levelno)s: %(message)s')

import os, sys, time, json, yaml
import random, signal, sqlite3
from logging import info, debug, error, warning
from types import SimpleNamespace
from datetime import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands, tasks

from emoji import emojize, demojize
#from txtai import Embeddings


class Howbot(commands.Bot):
  def __init__(self, *, intents: discord.Intents, command_prefix='/'):
    super().__init__(intents=intents, command_prefix=command_prefix)

    self.version = version
    self.sourceurl = sourceurl
    self.starttime = time.time()
    self.scriptname = os.path.basename(__file__).replace('.py','')
    self.yamlcfg = f'config/{self.scriptname}.yaml'
    self.helpfile = os.path.dirname(__file__) + '/' + f'help/{self.scriptname}.txt'

    self.loadcfg()

    self.nickname = self.cfg.nickname
    self.msgs = {}

    self.chatlog = []
    self._irclog = []
    #self.sqldb = sqlite3.connect('irclog.db')

    self.lastsave = time.time()
    self.lastmessage = None
    self.lastmessaged = None
    self.lastupdate = time.time()
    self.lastspoke = 0
    self.summaries = {}
    self.total_users = 0
    self.total_messages = 0

    self.connection_errors = 0
    self.memclient = None

    #self.tree = app_commands.CommandTree(self)

    #try:
    #  self.emb.load('log')
    #except:
    #  info('Creating new embedding database')
    #  self.emb.index(self.chatlog)

    try:
      self.token = open('.token-discord').read().strip('\n')
    except Exception as e:
      error(f'Opening API key: {e}')
      sys.exit()

  async def setup_hook(self):
    debug(('-' * 10, 'SETUP_HOOK', '-' * 10))
    
    for f in os.listdir("./cogs"):
      if f.endswith(".py"):
        try:
          debug(f'[cog] Loading "{f[:-3]}"')
          await self.load_extension("cogs." + f[:-3])
        except Exception as e:
          error(f'[cog] "{e}"')

    #self.tree.copy_global_to(guild=discord.Object(id=self.cfg.guildid))
    #await self.tree.sync(guild=discord.Object(id=self.cfg.guildid))


  def loadcfg(self):
    info('Using config file %s' % self.yamlcfg)

    self._cfg = yaml.safe_load(open(self.yamlcfg).read(), Loader=yaml.CLoader)
    self.cfg = SimpleNamespace(**self._cfg)

    self.cfg.oldmodel = ''
    self.cfg.model = 'unkn0wn'
    self.logfile = self.cfg.logfile
    self.cfg.personas = yaml.safe_load(open(self.cfg.personafile).read(), Loader=yaml.CLoader)
    self.cfg.totaluptime = 0
    
    self.cfg.presets = yaml.safe_load(open('config/presets.yaml').read(), Loader=yaml.CLoader)

    if os.path.exists(self.logfile):
      self.loadlogs(self.logfile)


  def run(self):
    super().run(self.token)


  def loadlogs(self, cfgfile):
    saved = yaml.safe_load(open(cfgfile).read(), Loader=yaml.CLoader)

    settings = 'mode preset backend persona totaluptime length mulitiline '
    settings += 'temperature voice model debug ignore_list multiline randomness '
    settings += 'logging append_user'

    for s in settings.split():
      if s in saved:
        vars(self.cfg)[s] = saved[s]


  def uptime(self):
    return dt.fromtimestamp(self.starttime).strftime('%F %T')


  def totaluptime(self):
    self.cfg.totaluptime += int(time.time() - self.lastsave)


  # write the entire chatlog to a buffer to be saved to disk ala IrcLog
  def irclog(self, ctx):
    try:
      user = demojize(ctx.author.name).encode('utf-8').decode()
      try: channel = demojize(ctx.channel.name).encode('utf-8').decode()
      except: channel = demojize(str(ctx.channel)).encode('utf-8').decode()
      msg = demojize(ctx.content).strip().encode('utf-8').decode()

      # This is GMT
      ts = ctx.created_at.strftime('%H:%M')
      log = f'[{ts}] <{user}:#{channel}> {msg}'
      
      #if channel in self.cfg.channels:
      #  try:self.emb.upsert([msg])
      #  except Exception as e:
      #      debug(f'Insert: {e}')

      self.chatlog.append({'user': user, 'msg': msg})
      self._irclog.append(log)
      return log
    except Exception as e:
      error(f'ERROR: logging: {e} {msg}')


  # go through cfg vars and save changed ones
  # will eventually save them in original cfg
  async def savelogs(self):
    try:
      self.totaluptime()
      self.lastsave = time.time()

      data = { 'backend': self.cfg.backend,
               'model': self.cfg.model, 
               'debug': bool(self.cfg.debug), 
               'preset': self.cfg.preset, 
               'saved': self.lastsave, 
               'persona': self.cfg.persona,
               'memory': self.cfg.memory,
               'randomness': int(self.cfg.randomness),
               'msgcontext': int(self.cfg.msgcontext),
               'multiline': int(self.cfg.multiline),
               'length': int(self.cfg.length),
               'temperature': float(self.cfg.temperature),
               'totaluptime': self.cfg.totaluptime,
               'voice': bool(self.cfg.voice),
               'append_user': bool(self.cfg.append_user),
               'mode': self.cfg.mode
             }

      log_yaml = yaml.safe_dump(data, sort_keys=False)

      with open(self.logfile, 'w') as log_f:
        log_f.write(log_yaml)

      with open('IrcLog','a') as irclog:
        for line in self._irclog:
          try:
            irclog.write(line.strip()+'\n')
          except Exception as e:
            error(f'irclog {e} on "{line}"')
      #self.emb.save('log')
      self._irclog = []
      self.chatlog = self.chatlog[-128:]

    except Exception as e:
      error(f'ERROR: Saving {self.logfile}: {e:} --- `{self.logfile}`')

    return # await self.setpresence(quiet=True, mode=self.cfg.mode)


  # store and manipulate message history
  # commands: [ add, find, get, save, load ]
  # user -> [ time, channel, message, context ]
  #            context -> [ nouns sentiment tone verbs subject response? ]
  async def messages(self, **k):
    #debug(f'[MSG] Invoked: {k}')

    try:
      if 'cmd' in k:
        if k['cmd'] == 'len':
          total_messages = 0
          total_users = 0
          for user in self.msgs:
            total_users += 1
            for chan in self.msgs[user]:
              total_messages += len(self.msgs[user][chan])

          self.total_users = total_users
          self.total_messages = total_messages
          return 

        if k['cmd'] == 'show':
          return self.msgs

        elif k['cmd'] == 'add' and 'user' in k and 'msg' in k:
          msg = k['msg']

          if msg[0] in [self.cfg.cmdchar, self.cfg.ignorechar]:
            #debug('Ignoring command char')
            return

          user = k['user']
          try: channel = k['ctx'].channel.name
          except: channel = k['ctx'].name

          if 'ctx' in k:
            if user not in self.msgs:
              debug('adding user')
              self.msgs[user] = {}

            if channel not in self.msgs[user]:
              debug('adding channel')
              self.msgs[user] = { channel: [] }

            flan = {}
            #if self.cfg.useflan:
            #  debug('Doing FLAN query')
            #  for q in self.cfg.flanprompts:
            #    flan[q] = await self.flanquery(q, msg)

            rec = {'time': int(k['ctx'].created_at.timestamp()),
                   'user': user,
                   'chan': channel,
                   'msg': msg,
                   'response': k['response']
                   }
            rec = {**rec, **flan}

            self.msgs[user][channel].append(rec)

        elif k['cmd'] == 'summarize' and 'user' in k:
          user = k['user']
          try: channel = k['ctx'].channel.name
          except: channel = k['ctx'].name

          summary_text = ''
          summary = ''
          try:
            if user not in self.msgs or channel not in self.msgs[user] or not len(self.msgs[user][channel]):
              return ''

            for msg in self.msgs[user][channel]:
              summary_text += user + ': ' + msg['msg'] + '\n' + self.nickname + ':' + msg['response'] + '\n'

            if len(summary_text):
              summary = await self.flanquery('summarize this conversation', summary_text[-1500:])
          except Exception as e:
            error(f'ERROR: Summarizing: {e}')
          return f'Summary: {summary}'

        elif k['cmd'] == 'get' and 'user' in k:
          user = k['user']
          try: channel = k['ctx'].channel.name
          except: channel = k['ctx'].name

          if user in self.msgs and channel in self.msgs[user]:
            pass
          else:
            #print('No messages for',user)
            return []

          if 'n' in k:
            #print('getting ',k['n'],' messages.')
            if user in self.msgs:
              #print('for user ',user)
              #if k['n'] < len(self.msgs[user][channel]):
              return self.msgs[user][channel]
              #else:
              #  return self.msgs[user][channel][-(int(k['n'])):]
                #n = int(k['n']) - (len(self.msgs[user][channel]) * 2)
          else:
            #print('Found',len(self.msgs[user][channel]),'messages')
            return self.msgs[user][channel]

    except Exception as e:
      error(f'msg: {e}')


  async def setpresence(self, activity=None, status=None, quiet=False, mode=None):
    #self.get_cog('Public').get_model()
    #self.cfg.model = oai.get_model(api_base=self.cfg.apiurl)
    
    if mode:
      if mode == 'bot':
        status = 'idle'
        if self.cfg.backend in ['llamacpp','ollama']:
          activity = f'{self.cfg.persona}/{self.cfg.model} ({self.total_users} users/{len(self.msgs)} messages)'
        elif self.cfg.backend == 'memgpt':
          activity = f'{self.cfg.nickname}/{self.cfg.model}'
      if mode == 'off':
        status = 'dnd'
        if status:
          activity = f'{status} ({self.total_users} users/{self.total_messages} messages)'
        else:
          activity = f'sleeping.... ({self.total_users} users/{self.total_messages} messages)'
      if mode == 'game':
        status = 'online'
        activity = f'Gaming! ({self.total_users} users/{self.total_messages} messages)'

    if activity:
      activity = discord.Game(name=activity)

    if status:
      if status == 'idle': status = discord.Status.idle
      elif status == 'dnd': status = discord.Status.do_not_disturb
      elif status == 'online': status = discord.Status.online
      elif status == 'invisible': status = discord.Status.invisible

    #if not quiet:
    debug(f'Setting presence to [{activity}] / {status}')

    if status and activity:
      await self.change_presence(status=status, activity=activity)
    elif activity:
      await self.change_presence(activity=activity)
    elif status:
      await self.change_presence(status=status)


  # grandfathered in
  def is_adminrole(self, name):
    #print(str(self.cfg.owner),str(name))
    return str(self.cfg.owner) == str(name) or self.cfg.adminrole in str(name)


  # apparently this is called multiple times on startup, so don't set presence here
  async def on_ready(self):
    #self.cfg.model = oai.get_model(api_base=self.cfg.apiurl)
    info('Up and running!')


  async def errormsg(self, src, e):
    self.connection_errors += 1
    error(f'ERROR({self.connection_errors}): {src} - {e}')

    if self.connection_errors > self.cfg.max_errors:
      self.cfg.mode = 'off'
      await self.setpresence(mode='off')
      output = 'My circuits are currently undergoing scheduled maintenance. I will need to take a short nap.\n*BBL*.'
    else:
      output = random.choice(self.cfg.errormessages)

    return output


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
howbot = Howbot(intents=intents, command_prefix='/')


if __name__ == '__main__':
  howbot.run()

# vim:ts=2:sw=2
