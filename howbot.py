#!/usr/bin/python
version = '0.2a'
sourceurl = 'http://github.com/tecknowledge/howbot'

# markov chain expression kit v.01
# cbterry 12/28/2015
# 
# irc bot based on markovify
# 

# want to do per user stats:
# avg line, total vocab, avg sentiment, grade level,
# readability, total words, total lines, punctuation (! or ?)
# num_questions num_excited

# convert all text to lowercase
# also work on the text filter on input, still gets some random chars

import os, sys, re, time
import logging, gzip, glob
from logging import info, debug, error

logging.basicConfig(format='%(asctime)s %(levelname)s %(funcName)s %(threadName)s(%(lineno)d) -%(levelno)s: %(message)s')
#'%(asctime)s  %(message)s',level=logging.NOTSET)
import random, signal, json
import textacy, ircbot

from pyaml import yaml
from types import SimpleNamespace
from textutils import *

import taggedtext 
from taggedtext import TaggedText as markovify

from importlib import reload
import textacy.preprocess, textacy.preprocessing, textacy.preprocessing.resources

textacy.constants = textacy.preprocessing.resources
reload(textacy)
reload(textacy.preprocess)

CONFIG_FILE='howbot.yaml'
brains=[]

class MyBot(ircbot.BotClient):
  def __init__(self):
    global brains
    self.starttime = time.time()
    self.lastmsg = 0

    self.scriptname = os.path.basename(__file__).replace('.py','')
  
    self.yamlfile = self.scriptname + '.yaml'
    self.corpus = textacy.Corpus(lang='en')
    self.corpus.add_text('And this is how we rewrite right now.')

    if self.yamlfile != CONFIG_FILE:
      self.yamlfile = CONFIG_FILE

    try:
      self._cfg = cfg
      self.cfg = SimpleNamespace(**self._cfg)
    except Exception as e:
      error("Error loading yaml configuration from '%s': %s" % ( self.yamlfile, e))
      return
   
    self.log = []

    self.markovify = markovify(self.corpus, state_size=self.cfg.chainsize)
    
    self.nickname = self.cfg.nickname
    print(self.cfg.brain)
    
    self.brains = self.cfg.brain + brains
    
    debug("Loading %s files" % len(self.brains))

    text= ''
    
    for f_ in self.brains:
      try:
        debug('Loading %s: ' % f_)
        if f_.endswith('.txt'):
          with open(f_) as f:
            text = ''
            while True:
              ntxt = f.read(8192)
              if not ntxt: break
              text += ntxt
            debug(' %d bytes' % len(text))

            self.corpus.add_text(text)
        elif f_.endswith('.bin'):
          self.corpus.add(textacy.Corpus.load(filepath=f_,lang='en'))
          info(self.corpus)

        elif f_.endswith('.json') or f_.endswith('.json.gz'):
          chain = open(f_,'rb').read()
          try: chain = gzip.decompress(chain)
          except Exception as e:
            error('DeCompressing: %s' % e)
          
          chain_js = json.loads(chain)
          debug('Read %s bytes from %s' % (len(chain), f_))
          
          chain = taggedtext.TaggedText.from_chain(chain_json=chain_js['chain'])
          self.markovify.chain = taggedtext.markovify.utils.combine([ chain.chain, self.markovify.chain ])
      except Exception as e:
        error('Error Loading file: %s' % e)
        continue

    info(self.corpus)
    
    self.markovify.chain = taggedtext.markovify.utils.combine([
                            self.markovify.chain, markovify(self.corpus, state_size=self.cfg.chainsize).chain ])
    
    info('Read %s total bytes' % len(self.markovify.chain.to_json()))
    
    return

  def _updatecorpus(self, text):
    if not text or len(text) <= 0:
      return
    
    try:
      text = re.sub(' \*[A-Z]*\*','',
        textacy.preprocess.preprocess_text(text,no_urls=True))

      if len(self.log) > self.cfg.log_limit:
        debug('Writing new brain - %s.' % len(self.log))
        newcorpus = textacy.Corpus(lang='en')
        newcorpus.add_text(text='\n'.join(self.log))
        debug(newcorpus)

        newchain = taggedtext.TaggedText(newcorpus, state_size=self.cfg.chainsize)
        debug(type(newchain))

        self.markovify.chain = taggedtext.markovify.utils.combine([self.markovify.chain, newchain.chain ])
        self.save_state()

        self.log = []
      else:
        self.log.append(text)
    except Exception as e:
      info('Preprocessing2"%s": %s' % (text, e))
      return
  
  def save_state(self):
    # will also save various information ..
    # topics, users, their profiles, total stats,
    # trends?
    
    newsize = oldsize = 0
    try:
      js = self.markovify.chain.to_json()
      outfile = '%s.json.gz' % self.nickname
      
      try: js = gzip.compress(js.encode('utf-8'))
      except Exception as e:
        error('Compressing: %s' % e)
        pass
      
      try:
        if os.path.isfile(outfile):
          newsize = os.stat(outfile).st_size
        oldsize = len(js)
      except Exception as e:
        error('Comparing sizes: %s' % e)
  
      if oldsize >= newsize or (not os.path.isfile(outfile)):
        with open(outfile,'wb') as data:
          data.write(js)
          debug('Wrote %s bytes to %s' % (len(js), outfile))
      else:
        error('New brain smaller than old brain? (%s / %s)' % (oldsize, newsize))
        error('Have you been doing digital drugs?')

    except Exception as e:
      error(e)
      pass

  def privmsg(self, user, channel, msg):
    user = user.split('!', 1)[0]

    if self.cfg.verbose:
      print('<%s> %s' % (user, msg))
    
    if user in self.cfg.ignore_list:
      return
    
    if len(msg) > 10:
      self._updatecorpus(msg)

    if msg.find(self.nickname) > 1 or (random.randint(0,100) <= self.cfg.rate and \
    (time.time() - self.lastmsg > self.cfg.sleep)):
    
      for x in range(0,self.cfg.tries):
        markovText = self.markovify.make_short_sentence(self.cfg.length,
                          max_overlap_total=self.cfg.overlap,
                          max_overlap_ratio=self.cfg.ratio,
                          tries=self.cfg.tries)
        if not markovText or len(markovText) <= 5:
          continue
        if markovText and len(markovText) >= 5:
          break

      if not markovText or len(markovText) < 4:
        return

      output = tonick(user) + fix_text(markovText)
      
      self.lastmsg = time.time()
      self.msg(channel, str(output))
      
      if len(output) > 10:
        self._updatecorpus(msg)

      if self.cfg.verbose:
        print('<%s> %s' % (self.nickname, output))

class BotFactory(ircbot.BotFactory):
  protocol = MyBot
  
  def buildProtocol(self, addr):
    me = MyBot()
    me.factory = self
    self.me = me
    return me

  def clientConnectionLost(self, connector, reason):
    self.save_state()
  
  def save_state(self):
    self.me.save_state()

if __name__ == "__main__":
  if len(sys.argv) > 1:
    CONFIG_FILE=sys.argv[1]
  if len(sys.argv) >= 2:
    brains = sys.argv[2:]
    info('Reading text from %s' % ', '.join(brains))

  info('Using config file %s' % CONFIG_FILE)
  
  try:
    cfg = yaml.load(open(CONFIG_FILE).read())
  except Exception as e:
    error('Loading config file: %s' % e)
    sys.exit(1)
  finally:
    try:
      Bot = BotFactory(cfg['ircchannel'], cfg['nickname'])
      bot = ircbot.reactor.connectTCP(cfg['ircserver'], cfg['ircport'], Bot)
      bot.reactor.run()
    except Exception as e:
      error('uncaught exception: %s' % e)
