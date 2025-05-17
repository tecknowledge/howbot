from logging import info, debug, error
import asyncio, json
from discord.ext import voice_recv
from discord import Member as discordMember
from datetime import datetime as dt
#import whisper
import os, lameenc
import util.oai as oai


class VoiceSink(voice_recv.AudioSink):
  def __init__(self, bot, public, loop):
    super().__init__()
    self.bot = bot
    self.public = public
    self.loop = loop
    self.audio_data = []
    self.members_speaking = set()
    
    self.lame = lameenc.Encoder()
    #self.lame.set_bit_rate(64)
    #self.lame.set_quality(7)
    #self.lame.set_channels(1)
    
    info('Voice: Initiated')

  def encode(self, fn):
    try:
      mp3 = self.lame.encode(open(fn,'rb').read())
    except Exception as e:
      error(f'Encoding (reading): {e}')
    try:
      with open(os.path.splitext(fn)[0] + '.mp3','wb') as f:
        f.write(mp3)
    except Exception as e:
      error(f'Encoding (writing): {e}')

  def wants_opus(self):
    return False

  def write(self, user, data):
    if data.pcm and user.id in self.members_speaking: # type: ignore
      self.audio_data.append(data.pcm)

  def cleanup(self):
    if not self.audio_data:
      return
    audio_data = b''.join(self.audio_data)

    if not len(audio_data.strip()):
      return
    
    info('Finished recording.')

    user = self.last_spoke
    date = dt.now().strftime('%Y_%m_%d_%H_%M_%S')
    fn = f'audio/{user}_{date}.wav'

    try:
      if not os.path.exists(fn):
        with open(fn, 'xb') as f:
          f.write(audio_data)
    except Exception as e:
      error('Writing: {e}')

    debug(f'Wrote: {fn} {len(audio_data)} bytes')

    try:
      self.encode(fn)
      newfn = os.path.splitext(fn)[0] + '.mp3'
      response = self.public.tts.transcribe(newfn)['text']
      debug(f'Response: {response}')
    except Exception as e:
      error(f'Transcoding: {e}')
      return

    if not self.bot.cfg.voice_all:
      if not response.strip().lower().startswith('halo'):
        return

    try:
      messages = [['system', self.bot.cfg.persona]]
      if 'user' in self.bot.cfg.memory:
        ctx = self.bot.get_channel(self.bot.cfg.homeid)
        history = asyncio.run(self.bot.messages(cmd='get', user=user, ctx=ctx))
      else:
        history = self.bot.chatlog[-(int(self.bot.cfg.msgcontext)):]
      
      try:
        for msgs in history[-(int(self.bot.cfg.msgcontext)):]:
          messages.append(['user', f"{user}: {msgs['msg']}"])
          if 'user' in self.bot.cfg.memory:
            messages.append(['assistant', msgs['response']])
          elif msgs['user'] == 'howsy':
            messages.append(['assistant', msgs['msg']])

      except Exception as e:
        error(f'History: {e}')
        debug(json.dumps(messages))
      finally:
        messages.append(['user', response])
        output = asyncio.run(self.public.generate(messages, system=self.bot.cfg.persona,
                                                  process=False))
        debug('Output:' + json.dumps(output))

      if not len(output) or len(output) < 4:
        debug('No output: {output}')
        return
    except Exception as e:
      error(f'ERROR (process_msg): {e}')
      return

    try:
      async def coro():
        debug(f'Output: {output}')
        ctx = self.bot.get_channel(self.bot.cfg.homeid)
        await ctx.send(output)
        await self.public.playtext(output)
      asyncio.run_coroutine_threadsafe(coro(), self.loop)
    except Exception as e:
      error(f'ERROR (process_output): {e}')
      return


  @voice_recv.AudioSink.listener()
  def on_voice_member_speaking_start(self, member: discordMember):
    if member.id not in self.members_speaking:
      info(f"{member} started speaking.")
      self.members_speaking.add(member.id)
      self.last_spoke = member.name

  @voice_recv.AudioSink.listener()
  def on_voice_member_speaking_stop(self, member: discordMember):
    if member.id in self.members_speaking:
      info(f"{member} stopped speaking.")
      self.last_spoke = member.name
      self.members_speaking.remove(member.id)
      self.cleanup()
      self.audio_data.clear()
