from logging import debug, info, warning, error
from discord.ext import commands, tasks, voice_recv
import discord

import logging
import random, time, re, os, io, json
#from json_repair import json_repair as json
from datetime import timedelta, datetime as dt
from importlib import reload as reloadlib
import base64, tempfile
import requests, asyncio
from PIL import Image

from emoji import emojize, demojize
#from txtai import Embeddings
import humanize
#import whisper

import util.oaia as oai
import ollama
from ollama import AsyncClient
import util.txt as txt
import util.webgpt as webgpt
import util.comfyapi as comfyapi
import util.news as news

from util.ytsum import ytsum
#from util.voice import VoiceSink


class Public(commands.Cog):
  def __init__(self, bot):
    self.bot = bot

  @commands.Cog.listener()
  async def on_ready(self):
    if self.bot.cfg.voice:
      await self.startvoice()

  # transcribe to wav file and play it on the voice channel
  async def startvoice(self):
    self.tts = '' #whisper.load_model(self.bot.cfg.tts_model)
    self.voice_channel = self.bot.get_channel(self.bot.cfg.voiceid)
    self.vc = await self.voice_channel.connect(cls=voice_recv.VoiceRecvClient)
      
    loop = asyncio.get_event_loop()
    self.voicesink = '' # VoiceSink(self.bot, self, loop)
    self.vc.listen(self.voicesink)

  # TODO: move to voice?
  async def playtext(self, text):
    if not self.bot.cfg.voice:
      return
    
    if text and len(text):
      info(f'Playing text: "{text}"')
    else:
      return
    
    try:
      res = requests.post(self.bot.cfg.piper_api, data=text).content
    except Exception as e:
      error(f'Fetching voice: {e}')
      return

    try:
      date = dt.now().strftime('%Y_%m_%d_%H_%M_%S')
      temp = tempfile.NamedTemporaryFile(delete=False, prefix=f'{self.cfg.nickname}-{date}-', suffix='.wav', dir='/data/sd/howsy/audio')
      temp.write(res)
      temp.seek(0)
      #files = {'audio_data': base64.b64encode(res)}
      #res = requests.post('http://localhost:8000/v1/audio/transcriptions', json=files).text

      self.vc.play(discord.FFmpegPCMAudio(source=temp.name))
      self.vc.source = discord.PCMVolumeTransformer(self.vc.source)
      self.vc.source.volume = .5
      
      while self.vc.is_playing():
        try: await asyncio.sleep(0.5)
        except: time.sleep(0.5)
      
      temp.close()
    except Exception as e:
      error(f'Sending voice message: {e}')

  @commands.Cog.listener()
  async def on_message(self, ctx):
    user = str(ctx.author.name)
    msg = demojize(str(ctx.content))
    channel = str(ctx.channel)
    output = None

    if self.bot.cfg.alerts_on:
      if channel in self.bot.cfg.alerts:
        for usr in self.bot.cfg.alerts[channel]:
          if any([item in msg for item in self.bot.cfg.alerts[channel][usr]]):
            return await ctx.channel.send(f'<@{usr}>')

    # ignore messages unless directly addressed, messaged, or if the channel is whitelisted
    if not ((self.bot.nickname.lower() in msg.lower()) or (channel in self.bot.cfg.channels) or (channel.startswith('Direct Message with'))):
      return

    # ignore bots and users in the ignore list
    if ctx.author.bot or (user in self.bot.cfg.ignore_list):
      return
    
    if msg:
      info(self.bot.irclog(ctx))
    else:
      return
    
    # ignore messages with '.' (default)
    if msg.startswith(self.bot.cfg.ignorechar):
      return
    
    self.bot.lastmessaged = time.time()

    if (msg[0] == self.bot.cfg.cmdchar and len(msg) > 2) and self.bot.is_adminrole(ctx.author.roles):
      output = await self.process_cmd(msg, user, ctx)

    # howbot chats freely on his homechannel, or responds if mentioned
    elif (self.bot.cfg.mode in ['bot'] and (channel == self.bot.cfg.homechannel) or (self.bot.nickname in msg)) and (len(msg) > 4):
      if ctx.attachments:
        debug('Image found!')
        img2txt = imgtext = ''

        # TODO: Use the text from the message as the prompt? or What?
        if self.bot.cfg.use_llava and self.bot.cfg.backend == 'ollama':
          for image in ctx.attachments:
            response = requests.get(image.url)

            if response.status_code == 200:
              b_img = base64.b64encode(response.content)
              res = await AsyncClient().chat(
                model = self.bot.cfg.model,
                messages = [
                  {
                    'role':'user',
                    'content': 'Describe this image',
                    'images': [ b_img ] 
                  }
                ]
              )
            img2txt += res['message']['content']
        else:
          try:
            img2txt = await comfyapi.interrogate(ctx.attachments[0].url)
            debug('Caption: '+img2txt)
          except:pass
          try:
            imgtext = await txt.tesseract(ctx.attachments[0].url)
            debug('Text on image: '+imgtext)
          except:pass

        if len(img2txt):
          msg += f', an image described by "{img2txt}"'
        if len(imgtext):
          msg += f', with the text "{imgtext}" on it'

        info(f'[image attachment] Got: {msg}')
      output = await self.process_msg(user, msg, ctx)

    await self.process_output(output, user, msg, ctx)

  # process output text
  async def process_output(self, output, user, msg, ctx):
    if output and type(output) == str:
      if self.bot.cfg.persona == 'data':
        try:
          data = json.loads(output)
          output = '\ntopic: `%s` entities: `%s`' % (data['topic'], ', '.join(data['entities']))
          output += '\ntone: `%s` feeling: `%s` emotion: `%s`' % (data['tone'], data['feeling'], data['emotion'])
          output += '\nthoughts: `%s` abstracts: `%s`\n' % (', '.join(data['thoughts']), ', '.join(data['abstracts']))
          
          if 'response' in data:
            output += '> ' + data['response']
        except Exception as e:
          error(f'Data: {e}')
      
      if output.find('<think>') != -1:
        debug(f'Show_Thought: {self.bot.cfg.show_thought}')
        if self.bot.cfg.show_thought:
          debug('Showing thought')
          output = re.sub(r'(?=\s*<think>)(.*?)(?=</think>\s*)',
                          lambda m: '\n'.join(f'-# {line}' if line.strip() else '- ' for line in m.group(1).strip().split('\n')), 
                          output, 
                          flags=re.DOTALL|re.MULTILINE)
        else:
          debug('Hiding thought')
          output = re.sub(r'\s*<think>.*?</think>\s*','', output, flags=re.DOTALL|re.MULTILINE)

      if output[0] not in [self.bot.cfg.cmdchar, self.bot.cfg.ignorechar]:
        if len(output) > self.bot.cfg.max_line:
          output_b = txt.sentence_split(output, self.bot.cfg.max_line)
          
          while len(output_b):
            try: self.bot.lastmessage = await ctx.channel.send(output_b.pop(0))
            except: self.bot.lastmessage = await ctx.send(output_b.pop(0))
        else:
          m = emojize(output)
          try: self.bot.lastmessage = await ctx.channel.send(m)
          except Exception as e:
            error(f'process_output ??:{e}')
            self.bot.lastmessage = await ctx.send(m)
          info(self.bot.irclog(self.bot.lastmessage))

        await self.bot.messages(cmd='add', user=user, msg=msg, ctx=ctx,
                                response=self.bot.lastmessage.content)
        
        if int(self.bot.cfg.voice):
          await self.playtext(output)

        #if 'summary' in self.bot.cfg.memory:
        #  self.bot.summaries[user] = await self.bot.messages(cmd='summarize', user=user, ctx=ctx)
      else:
        debug('Not adding command to messages')


  # process text generation
  async def process_msg(self, user, msg, ctx=None):
    if self.bot.cfg.backend == 'memgpt':
      if self.bot.memclient == None:
        if 'memgpt_client' not in globals():
          from memgpt import create_client as memgpt_client
        
        self.bot.memclient = memgpt_client(base_url=self.bot.cfg.memgptapi,
                                           token=self.bot.cfg.memgpt_token)
      output = await self.generate(msg, ctx=ctx)
    else:
      prompt = msg
      try:
        persona = self.bot.cfg.persona
        messages = [['system', persona]]
        
        if 'user' in self.bot.cfg.memory:
          history = await self.bot.messages(cmd='get', user=user, ctx=ctx)
        else:
          history = self.bot.chatlog[-(int(self.bot.cfg.msgcontext)):]

        # should do this automatically in self.bot.messages(),
        # and add to self.bot.summaries[user], then add that if it has content
        if 'summary' in self.bot.cfg.memory:
          if history and len(history) % int(self.bot.cfg.msgcontext) == 0:
            debug('Summarizing conversation...')
            system = self.bot.cfg.summary_prompt
            if user in self.bot.summaries and len(self.bot.summaries[user]):
              system += '\nPrevious summary:\n' + self.bot.summaries[user]

            hist=''
            
            for msgs in history[-(int(self.bot.cfg.msgcontext)):]:
              hist += f"{msgs['user']}: {msgs['msg']}\n"
              
              if 'user' in self.bot.cfg.memory:
                hist += f"{self.cfg.nickname}: {msgs['response']}\n"
            
            self.bot.summaries[user] = await self.generate(hist, system=system, temperature=0)
            
            if len(self.bot.summaries[user]):
              debug('Summary: ' + self.bot.summaries[user])
              messages[0][1] += '\n' + 'Conversation summary:\n' + self.bot.summaries[user]
      
        if history and len(history) > int(self.bot.cfg.msgcontext):
          if 'context' in self.bot.cfg.memory:
            if 'emb' not in self.bot.keys():
              self.bot.emb = '' # Embeddings(path='sentence-transformers/nli-mpnet-base-v2')
            
            context = ''
            context_history = []
            
            for msg in history:
              context_history.append('{} {} said: {}'.format(humanize.naturaltime(dt.fromtimestamp(msg['time'])), msg['user'], msg['msg']))
              if 'user' in self.bot.cfg.memory:
                context_history.append('{} {} said: {}'.format(humanize.naturaltime(dt.fromtimestamp(msg['time'])), self.cfg.nickname, msg['response']))

            context_search = '' # self.bot.emb.similarity(prompt, context_history)

            if len(context_search):
              try:
                for i in context_search:
                  if len(context) < 2048:
                    context += context_history[i[0]] + '\n'
              except Exception as e:
                error(f'Context Error: {e}')
            i
            nfo(f'Context search results: {context_history}')
            
            if len(context):
                messages[0][1] += '\n' + 'Conversation context:\n' + context

        if 'history' in self.bot.cfg.memory and len(history):
          try:
            for msgs in history[-(int(self.bot.cfg.msgcontext)):]:
              messages.append(['user', f"{user}: {msgs['msg']}"])
              if 'user' in self.bot.cfg.memory:
                messages.append(['assistant', msgs['response']])
              elif msgs['user'] == self.cfg.nickname:
                messages.append(['assistant', msgs['msg']])
          except Exception as e:
            error(f'Getting history: {e}')

        if self.bot.cfg.append_user:
          messages.append(['user', f'{user}: {prompt}'])
        else:
          messages.append(['user', prompt])
       
        topicprompt="""You are a JSON sentance analyser who will only respond in properly formatted JSON code to specification. For the following input, return a JSON document with the following fields:
           - sentiment: The overall sentiment of the statement, either negative, positive, or neutral
           - topic: The topic of the statement, a short phrase
           - keywords: Unique keywords in the statement
           - names: Names, places, and people in the statement
           - phrases: Phrases that stand out in the statement
           - type: Type of phrase
        """
        #info(await oai.q(prompt,system=topicprompt,temperature=0,length=128))

        output = await self.generate(messages, ctx=ctx)
        #messages = [['system',persona], ['assistant',output1]]
        #messages.append(['user','Improve your last response. Make sure not to repeat yourself. Do not comment on your improvement.'])
        #output = await self.generate(messages, ctx=ctx)
        #info('Output1: '+output)
        #info('Output2: '+output1)

      except Exception as e:
        output = await self.errormsg('process_msg', e)

    return output


  # process user commands invoked with '!' (default)
  async def process_cmd(self, msg, user, ctx):
    # split '!cmd stuff things => [cmd, stuff, things]'
    inp = msg[1:].split(' ')
    cmd = inp[0]
    args = inp[1:]
    val = ''
    output = ''

    if len(args):
      val = args[0]

    if cmd == 'help':
      output = f'{self.bot.cfg.nickname} version {self.bot.version} - <{self.bot.sourceurl}>\n'
      output += '`' + open(self.bot.helpfile).read() + '`'

    elif cmd == 'models':
      model_list = ollama.list()['models']
      total_size = 0
      embed = discord.Embed(title="**Ollama Models:**",
                            description=f"Currently available models", color=0x9C84EF)
      
      for model in model_list:
        text = '%s - %s\n%s, %s' % (model['details']['family'],
                                    humanize.naturalsize(model['size']))
        total_size += model['size']
        embed.add_field(name=model['model'], value=text)

      total_size = humanize.naturalsize(total_size) 
      embed.set_footer(text=f'Total disk space used: {total_size} in {len(model_list)} models')

      await ctx.channel.send(embed=embed)

    # query/change the model
    elif cmd == 'model':
      if len(val) and self.bot.cfg.backend == 'ollama':
        if val in [ x['model'] for x in ollama.list()['models'] ]:
          self.bot.cfg.oldmodel = self.get_model()
          self.bot.cfg.model = val
        else:
          if self.bot.cfg.oldmodel:
            self.bot.cfg.model = self.bot.cfg.oldmodel
      else:
        self.get_model()
      output = f'Current llama model: `{self.bot.cfg.model}` [backend: `{self.bot.cfg.backend}`]'

    # update discord presence string
    # send 1 of the 4 statuses to switch, or another string to set
    elif cmd == 'presence' and args:
      if val in ['invisible','dnd','idle','online']:
        debug(f'Status: {val}')
        await self.bot.setpresence(status=val)
      else:
        await self.bot.setpresence(activity=' '.join(args))

    # show all preset sampler settings
    elif cmd == 'presets':
      embed = discord.Embed(title="**Sampler Presets:**",
                            description='LLM Sampler Settings', color=0x9C84EF)
      for i, preset in enumerate(self.bot.cfg.presets):
        text = ''

        for var in self.bot.cfg.presets[preset]:
          text += f'{var}: `{self.bot.cfg.presets[preset][var]}`\n'
        embed.add_field(name=preset, value=text)

      await ctx.channel.send(embed=embed)

    # load chat setting presets from config/presets.yaml (default)
    elif cmd == 'preset':
      if len(val) and val in self.bot.cfg.presets:
        #for key in self.bot.cfg.presets[val]:
        #  vars(self.bot.cfg)[key] = self.bot.cfg.presets[val][key]
        self.bot.cfg.preset = val
        output = f'Preset changed to `{val}`'

      else:
        output = 'Available Presets: ' + ', '.join(list(self.bot.cfg.presets.keys()))
        output = output.replace(self.bot.cfg.preset, f'`{self.bot.cfg.preset}`')

    elif cmd == 'reload' and self.bot.is_adminrole(ctx.author.roles):
      info(f'Reloading config ({ctx.author})')
      
      for f in os.listdir("./cogs"):
        if f.endswith(".py"):
          try:
            await self.bot.reload_extension("cogs." + f[:-3])
          except Exception as e:
            debug(f'[cog] {f[:-3]} Error: {e})')

      self.bot.loadcfg()
      reloadlib(oai)
      await oai.generate([[''],['no','??reload']])
      reloadlib(comfyapi)
      reloadlib(webgpt)
      reloadlib(news)
      reloadlib(txt)

    elif cmd == 'restart' and self.bot.is_adminrole(ctx.author.roles):
      warning(f'Restart ({ctx.author})')

      if self.bot.cfg.voice:
        try: await self.vc.disconnect()
        except: pass
      
      await self.bot.setpresence(status='dnd')
      await self.bot.savelogs()
      await self.bot.close()
      await asyncio.sleep(2)
      await sys.exit()
    
    elif cmd == 'say':
      if self.bot.cfg.voice:
        text = ' '.join(args)
        await self.playtext(text)

    elif cmd == 'video':
      output = await ytsum(val)

    elif cmd == 'show':
      if self.bot.cfg.backend in ['llamacpp', 'ollama']:
        if user in self.bot.msgs and ctx.channel.name in self.bot.msgs[user]:
          total = len(self.bot.chatlog)
          msgs = len(self.bot.msgs[user][ctx.channel.name])
          ctxlen = len(''.join(x['msg'] for x in self.bot.msgs[user][ctx.channel.name]))
          ctxlen += len(''.join(x['response'] for x in self.bot.msgs[user][ctx.channel.name]))
          history = await self.bot.messages(cmd='get', user=user, ctx=ctx)
          output = f'Context history is currently {humanize.naturalsize(ctxlen)} in {msgs} messages ({len(history)} total)\n'
          output += f'`Total chat history: {total} lines`'
        
        if 'summary' in self.bot.cfg.memory and user in self.bot.summaries and len(self.bot.summaries[user]):
          output += f'\nSummary: `{self.bot.summaries[user]}`'

    elif cmd == 'forget':
      if 'user' in self.bot.cfg.memory:
        try:
            self.bot.msgs[user][ctx.channel.name] = []
          #del self.bot.summaries[user]
        except Exception as e:
          error('Forget: {e}')
        output = 'Forget what? :)'
      else:
        output = 'No per user memory enabled.'

    # Show or switch personas. Can be a full system prompt or a persona name.
    elif cmd == 'persona':
      if len(val):
        self.bot.cfg.persona = ' '.join(args).strip()
        try: del self.bot.msgs[user][ctx.channel.name]
        except: pass
        
        output = await self.generate(f'Say this in a more appropriate way, and keep your response short and concise: Hmm.. I am now in a {val} mood..', length=64)
      else:
        output = f'My current persona is that of _{self.bot.cfg.persona.strip()}_'

    elif cmd == 'personas':
      output = 'Available personas: ' + await oai.generate([[''],['no','??personas']])
      output = output.replace(self.bot.cfg.persona, f'`{self.bot.cfg.persona}`')

    elif cmd == 'serverinfo':
      roles = [role.name for role in ctx.guild.roles]
      if len(roles) > 50:
        roles = roles[:50]
        roles.append(f">>>> Displaying[50/{len(roles)}] Roles")
      
      roles = ", ".join(roles)

      embed = discord.Embed( title="**Server Name:**", description=f"{ctx.guild}", color=0x9C84EF)
      
      if ctx.guild.icon is not None:
        embed.set_thumbnail(url=ctx.guild.icon.url)

      embed.add_field(name="Server ID", value=ctx.guild.id)
      embed.add_field(name="Member Count", value=ctx.guild.member_count)
      embed.add_field(name="Text/Voice Channels", value=f"{len(ctx.guild.channels)}")
      embed.add_field(name=f"Roles ({len(ctx.guild.roles)})", value=roles)
      embed.set_footer(text=f"Created at: {ctx.guild.created_at}")

      await ctx.channel.send(embed=embed)

    elif cmd == 'sysinfo':
      try:
        output = os.popen("neofetch os host kernel uptime cpu gpu memory disk --disk_show '/data' '/data2'").read()
      except:
        pass

    elif cmd == 'uptime':
      up = timedelta(seconds=self.bot.cfg.totaluptime)
      output = f'I have been online for {up}'
    
    elif cmd == 'dream': 
      output = await self.dream()

    elif cmd == 'dreamall': # make it come up with random interesting images forever
      self.bot.cfg.mode = 'repeat'

      await ctx.channel.send(f'Drawing images until bot mode is changed from "repeat"')
      self._dream.start(ctx)

    elif cmd == 'stop':
      self._dream.stop()
      selt.bot.cfg.mode = 'on'
      await ctx.channel.send(f'Time to wake up ...')
      

    elif cmd == 'drawall':
      self.bot.cfg.mode = 'repeat'

      await ctx.channel.send(f'Drawing images until bot mode is changed from "repeat"')
      prompt = ' '.join(args)
      self._dream.start(ctx, prompt)

    elif cmd == 'draw':
      prompt = ' '.join(args)
      [ret, images] = await self.comfyui_image(prompt, ctx=ctx)
      output = 'Workflow: %s   Style: %s   Steps: %s   Seed: %s\n' % (ret['workflow'], ret['style'], ret['steps'], ret['seed'])
      output += '_' + ret['prompt'] + '_'
      await ctx.channel.send(f'{prompt}:', files=images)

    elif cmd == 'imagine':
      prompt = ' '.join(args)
      [ret, images] = await self.comfyui_image(prompt, enhance=True, ctx=ctx)
      output = 'Workflow: %s   Style: %s   Steps: %s   Seed: %s\n' % (ret['workflow'], ret['style'], ret['steps'], ret['seed'])
      output += '_' + ret['prompt'] + '_'
      await ctx.channel.send(f'{prompt}:', files=images)

    elif cmd == 'google':
      query = ' '.join(args)
      results = webgpt.process(query, backend=self.bot.cfg.backend, chatbot=self.bot)

      embed = discord.Embed(title=f'**Search results:**', description=f'{query}', color=0x9C84EF)
      i, links, text = 1 , '', ''
      
      for result in results:
        links += f'[{i}. {result["link"]}]({result["link"]})\n'
        text += result['summary'][:300]
        embed.add_field(name=f'{i} {result["title"]}', value=f'{result["summary"][:150]} ..', inline=False)
        i = i + 1
      
      output = await self.generate(f'Given the search query "{query}" with the results "{text}", concisely answer the query.', system='librarian', length='400')

      embed.add_field(name='Links', value=links, inline=False)
      await ctx.channel.send(embed=embed)

    # FIXME: use url grabber
    elif cmd == 'search':
      query = ' '.join(args)
      debug(f'Search query: {query}')
      try:
        output = webgpt.simple_search(query)
      except Exception as e:
        output = f'No results? Odd? ({e})'

    elif cmd == 'latest':
      output = news.get_summary()
    
    elif cmd == 'random':
      r = self.bot.get_cog('Random')
      if r:
        output = await r.randomness(show=False, topic=' '.join(args))
      else:
        info('WTF? No random output')
    elif cmd == 'ping':
      output = await self.ping()

    elif cmd == 'mode':
      if val in ['bot','off','game','on', 'repeat']:
        if val == 'on':
          self.bot.connection_errors = 0
          val = 'bot'
        self.bot.cfg.mode = val
        await self.bot.setpresence(mode=val)
      else:
        output = f'__Mode__: {self.bot.cfg.mode}'

    elif cmd == 'get':
      if val in vars(self.bot.cfg).keys():
        output = f'"{val}" = "{vars(self.bot.cfg)[val]}"'
      else:
        output = 'Invalid variable.'

    elif cmd == 'set':
      if val in vars(self.bot.cfg).keys():
        try:
          oldval = vars(self.bot.cfg)[val]
          vars(self.bot.cfg)[val] = ' '.join(args[1:])
          newval = vars(self.bot.cfg)[val]
          output = f'(set) {user} changed "{val}" from "{oldval}" to "{newval}"'
        except Exception as e:
          output =  f'set: {e} {args}'
      else:
        output = '__Settings__: '
        i = 0
        #'mode cmdchar ignorechar persona temperature length multiline'.split(' '):
        for v in sorted(vars(self.bot.cfg)):
          if v in ['prompts','presets','personas','alerts','errormessages','dreamprompts',
                   'finalerror', 'model','summary_prompt','cmdchar','length','msgcontext',
                   'memory','temperature', 'memgptapi','memgpt_agent','memgpt_token']:
            continue
          
          output += f'*{v}*: `{vars(self.bot.cfg)[v]}`\t'
          if not i % 3: output += '\n'
          i += 1

        output += f'\ncmdchar: `{self.bot.cfg.cmdchar}` '
        output += f'length: `{self.bot.cfg.length}` '
        output += f'memory: `{self.bot.cfg.memory}` '
        output += f'msgcontext: `{self.bot.cfg.msgcontext}` '
        output += f'\ntemperature: `{self.bot.cfg.temperature}` '
        output += f'model: `{self.bot.cfg.model}`'

    if output:
      return output

  def get_model(self):
    if self.bot.cfg.backend in ['llamacpp', 'memgpt']:
      self.bot.cfg.model = oai.get_model(api_base=self.bot.cfg.llama_api)

    elif self.bot.cfg.backend == 'ollama':
      try:model = ollama.ps()['models'][0]['model']
      except:
        if self.bot.cfg.oldmodel:
          model = self.bot.cfg.oldmodel
        else:
          model = 'unkn0wn'
      self.bot.cfg.model = model
    
    return self.bot.cfg.model

  # create an image through the comfyui API or koboldcpp SD API
  async def comfyui_image(self, prompt, style='sai-photographic', enhance=False, ctx=None):
    images = []
    imgn = 0
    if self.bot.cfg.imgapi == 'sd':
      prompt, res = comfyapi.sdimg(prompt, enhance=enhance, chatbot=self.bot)
      res = [res]

    elif self.bot.cfg.imgapi == 'comfy':
      ret = await comfyapi.generate_image(prompt, enhance=enhance, workflow=self.bot.cfg.comfyui_workflow, chatbot=self.bot.cfg)

      res = ret['images']
      prompt = ret['prompt']

    for img in res:
      with io.BytesIO() as image_binary:
        img.save(image_binary, 'PNG')
        image_binary.seek(0)
        imgn += 1
        new_embed = discord.File(image_binary, filename=f'image{imgn}.png')
        images.append(new_embed)
    return [ret, images]


  async def generate(self, prompt, length=None, system=None,
                     temperature=None, process=True, ctx=None):
    if not length:
      length = self.bot.cfg.length
    
    if not system:
      system = self.bot.cfg.persona
    
    if not temperature:
      temperature = self.bot.cfg.temperature
    
    try:
      if self.bot.cfg.backend == 'llamacpp':
        if ctx:
          try: await ctx.channel.typing()
          except: pass
        output = await oai.q(prompt, length=length, temperature=temperature,
                             system=system, api_base=self.bot.cfg.llama_api)
      elif self.bot.cfg.backend == 'memgpt':
        if ctx:
          try: await ctx.channel.typing()
          except: pass
        output = await self.memgpt_generate(prompt)
      elif self.bot.cfg.backend == 'ollama':
        if ctx:
          try: await ctx.channel.typing()
          except: pass
        output = await self.ollamachat(prompt, temperature=temperature,
                                       length=length, system=system)
      else:
        output = f'ERROR: Invalid backend {self.bot.cfg.backend}'

    except Exception as e:
      error(f'Generating: {e}')
      output = await self.errormsg('generate', e)

    try:
      if process and output:
        output = self.process_text(output, ctx)
    except Exception as e:
      error(f'Entering process: {e}')
      output = await self.errormsg('entering process', e)

    self.bot.lastspoke = time.time()

    return output

  
  async def ollamachat(self, prompt, system=None, temperature=None, length=None):
    if self.bot.cfg.model == 'unkn0wn':
      self.get_model()
    
    if system:
      system = self.bot.cfg.persona

    options = self.bot.cfg.presets[self.bot.cfg.preset]

    if temperature:
      options['temperature'] = float(temperature)

    if length:
      options['num_predict'] = int(length)
    
    try:
      text = await AsyncClient(self.bot.cfg.ollama_api).chat(
                               model=self.bot.cfg.model,
                               messages=oai.prep(prompt, system=system),
                               options=options)
    except Exception as e:
      error(f'OllamaChat: {e}')
      return ''

    return text['message']['content']

  async def memgpt_generate(self, prompt):
    responses = self.bot.memclient.user_message(agent_id=self.bot.cfg.memgpt_agent, message=prompt).messages

    for message in responses:
      if 'function_call' in message:
        if message['function_call']['name'] == 'send_message':
          return json.loads(message['function_call']['arguments'])['message']
#          for message in response:
#      if 'assistant_message' in message:
#        return message['assistant_message']


  # fixes the text up, takes a response array and message object
  def process_text(self, output, ctx=None):
    # remove the errant replies
    # e.g. 'terbo: hi howbot: whats up: terbo ...'
    if False and ctx and f'{ctx.author.name}: ' in output:
      n = self.bot.nickname.lower()
      c = ctx.author.name.lower()

      for name in [n, c, n, c]:
        #debug(f'Before {name}: {output}')

        try:
          if name in output.lower():
            tmp = ''
            #tmp = output.split(f'{name}: ')
            tmp = re.split(re.escape(f'{name}: '), output, flags=re.IGNORECASE)

            if len(tmp):
              #if len(tmp[0]) > 4:
              #  output = tmp[0]
              #else:
              output = tmp[1]
        except Exception as e:
          debug(f'Skipped passed splitting: {e} on {output}')
          pass
    return output

  async def errormsg(self, src, e):
    self.bot.connection_errors += 1
    error(f'ERROR({self.bot.connection_errors}): {src} - {e}')

    if self.bot.connection_errors > self.bot.cfg.max_errors:
      self.bot.cfg.mode = 'off'
      await self.bot.setpresence(mode='off')
      output = 'My circuits are currently undergoing scheduled maintenance. I will need to take a short nap.\n*BBL*.'
    else:
      output = random.choice(self.bot.cfg.errormessages)

    return output

  async def dream(self):
    prefix = random.choice(['make up','tell me','come up with','conjure up','what is','give me'])
    persona = random.choice(['halo','howsy','quantum'])
    return await self.generate(f'{prefix} an abstract totally random short entry from your dream journal.', system=persona)
      
  @tasks.loop(count=None)
  async def _dream(self, ctx, prompt=None):
    if self.bot.cfg.mode == 'repeat':
      if not prompt:
        prompt = random.choice(self.bot.cfg.dreamprompts)
      else:
        info('Dream prompt: ' + prompt)
      prompt += '@detail=0.15 @steps=15 @model=fast'
      [ret, images] = await self.comfyui_image(prompt, enhance=True, ctx=ctx)
      output = 'Workflow: %s   Style: %s   Steps: %s   Seed: %s\n' % (ret['workflow'], ret['style'], ret['steps'], ret['seed'])
      output += '_' + ret['prompt'] + '_'
      await ctx.channel.send(f'{prompt}:', files=images)
      asyncio.sleep(1)

  # return chat/llm latency 
  async def ping(self):
    chat_ping = time.time()
    if self.bot.cfg.backend in ['llamacpp', 'memgpt']:
      oai.get_model()
    elif self.bot.cfg.backend == 'ollama':
      ollama.ps()
    chat_ping = (time.time() - chat_ping) * 1000 

    return f'Pong! *Discord* `{round(self.bot.latency * 1000, 1)}ms` *Chat* `{round(chat_ping, 1)}ms`'

async def setup(bot):
  await bot.add_cog(Public(bot))

# vim:ts=2:sw=2
