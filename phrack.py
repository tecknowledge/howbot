#!/usr/bin/python
version = '0.1c'
sourceurl = 'http://github.com/tecknowledge/howbot'

# markov chain expression kit v.01
# cbterry 12/28/2015
# 
# irc bot based on markovify
# 
# TODO: Add IRC Bot module
#   Figure out how to load/save json brains
#    and compress them on the fly.
#
#  add command line, file, and other inputs
#
#  MERGE IN SEUSSBOT FOR POETRY
#
#   Ahh forgot t big feature...
#
#   need better parts of speech tagging!
#   nltk is not effecient, either stanford
#   as a server or ...
#
#   add advanced sentence processing
#   add learning from input in privmsg. . .

# ideas:
#
#  try and look for nouns if we can do POS
#  try and look for most important words,
#  or more important words like TF-IDF on our learned corpus

#  differnet kinds of responses:
#  pick a word, synonym? antonym? definition? some wordnet?
#  RHYME

import os, sys, re, random, signal, time

from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor

import datetime as dt

import markovify
from markovify import Chain
from markovify import Text

import json
from textblob import TextBlob as tb
from search import search,_search

admins = ['cb','terbo']
speak_rate = 60 # percentage
speak_sleep = 25 # seconds

nickname = 'phrack'
ircserver = 'irc.freenode.net'
ircport = 6667
ircchannel = '#tkot,#tecknowledge'
cmdchar = '!'

verbose = 0
logging = 1

markov_length = 1
markov_ratio = .7
markov_overlap = 15
sent_length = 60
markov_tries = 100
last_spoke = 0

question_rate = 1

inputfiles = ['/t/phrack.txt']
#inputfiles = ['/t/aesop.txt', '/t/fortunes.txt', '/t/thoreau.txt','/t/marktwain.txt', '/t/spyguide.txt','/t/realsocialdynamics-theblueprint.txt','/t/improvised.txt','/t/swfqw.txt', '/t/nasrudin.txt','/t/phrack.txt']
text = ''

def signal_handler(signal, frame):
    print('Exit recieved..')
    
    time.sleep(1)
    sys.exit(1)

signal.signal(signal.SIGINT, signal_handler)


def punct():
  """ return random punctuation """
  punct_ = [ '.','.','.','.','.', '.', '.', '.','.','.', \
            '?', '!', '..','?','!','?', '!', '...', \
            ':)', ';)', ':|', ':/', ':D', '=D' \
            '.', '.', '.', '.', '.', '.']
  random.seed(random.random()*len(punct_))
  out = random.choice(punct_)

  if len(str(out)) >= 2:
    out = ' ' + out
  return out

class MyBot(irc.IRCClient):
  def __init__(self):
    
    self.starttime = time.time()
    
    self.data = { 'admins': admins,
                  'noauth': True,
                  'cmds': [ 'stats','config','set','get','last','persona','google','search','version','remind','seen'],
                  'ignorelist': [],
                  'trigger': cmdchar,
                  'rate': speak_rate,
                  'sleep': speak_sleep,
                  'markov': markov_length,
                  'length': sent_length,
                  'tries': markov_tries,
                  'self': True,
                  'logging': True,
                  'last': 0,
                }
    self.searchengines = ['duckduckgo', 'google', 'amazon', 'bbcnews', 'discogs', \
               'piratebay', 'wolfram', 'youtube', 'stack', 'acronym', \
               'bing', 'rfc', 'scholar']

    self.log = []
    self.verbose = 0
    self.persona = inputfiles
    self.markovify = mark
    self.last_message = []

    self.userlist = []

    self.version = version
    self.sourceurl = sourceurl

    print 'Got ' + str(len(self.markovify.chain.model)) + ' chains'

    self.nickname = nickname or 'howdy'
    print 'launching `%s`' % (self.nickname)
    return

  def _get_nickname(self):
      return self.factory.nickname
  

  def signedOn(self):
      self.join(self.factory.channel)
      print "Signed on as %s." % (self.nickname,)

  def joined(self, channel):
      print "Joined %s." % (channel,)

# print out public chat
# don't react unless 3 words or more
# list of words to react to
# question interpretation?

  def privmsg(self, user, channel, msg):
      if not user:
          return
  
      user = user.split('!', 1)[0]
      
      if user not in self.userlist:
        self.userlist.append(user)

      if self.verbose:
        print "%s:\t\t%s" % (user, msg)

      if msg[0] == self.data['trigger'] and len(msg) > 2:
        
        inp = msg[1:].split(' ')
        
        args = inp[1:] 
        cmd = inp[0]
        args = inp[1:] 
        val = ''

        if self.data['noauth'] or (user in self.data['admins']):
          if len(args):
            val = args[0]
          
          if cmd == 'help':
            self.msg(channel, '(commands): %s' % ( self.data['cmds'] ) )
         
          if cmd == 'version':
            self.msg(channel, '[TK]: howbot v%s %s' % ( self.version, self.sourceurl ) )

          if cmd == 'stats':
            self.msg(channel, '(stats) recorded %d lines since %s' % ( len(self.log),
                                   dt.datetime.fromtimestamp(self.starttime).strftime('%F %T') ) )
          elif cmd == 'config':
            self.msg(channel, '(config) %s' % self.data )

          elif cmd == 'persona':
            persona = ', '.join([ x.replace('/t/','').replace('.txt','') for x in self.persona ])
            self.msg(channel, '(persona) %s' % persona)
          
          elif cmd == 'set':
            if val in self.data:
              oldval = self.data[val]
              self.data[val] = " ".join(args)
              newval = self.data[val]
              
              self.msg(channel, '(set) updated "%s" from "%s" to "%s" (%s)' % ( val, oldval, newval, user ) )
          
          elif cmd == 'get':
            self.msg(channel, '"%s" is set to "%s"' % ( val, self.data[val] ) )
          
          elif cmd == 'seen':
            pass
          elif cmd == 'last':
            self.msg(channel, '%s (repost)' % ( self.last_message ) )

          elif cmd == 'log':
            if val:
              limit = val
            else:
              limit = 5

            if len(self.log) > limit:
              start = self.log[-limit]
            else:
              start = 0

            for i in range(len(self.log[-limit]), len(self.log) - 1):
              log = self.log[i]
              self.msg(user, '%s <%s:%s> %s' % ( dt.datetime.fromtimestamp(log['timestamp']).strftime('%T'),
                                                 log['channel'], log['user'], log['msg']) )
              
          #elif cmd == 'google':
          #  self.msg(channel,'%s' % ( _search(' '.join(args))))
            
      if random.randint(0,200) <= question_rate and user not in self.data['ignorelist']:
        out = re.sub(r'[^A-Za-z0-9]','',msg.split()[-1]) + '?'
        #print self.nickname + ":\t\t" + out
        self.data['last'] = time.time()
        return self.say(channel,out)
      
      if msg.find(self.nickname) > 1 or (random.randint(0,100) <= self.data['rate'] and \
        (time.time() - self.data['last'] > self.data['sleep'])):
        
        for x in xrange(markov_tries):
          markovText = self.markovify.make_short_sentence(sent_length,
                                              max_overlap_total=markov_overlap,
                                              max_overlap_ratio=markov_ratio,
                                              tries=markov_tries)
          if not markovText or len(markovText) <= 5:
            pass
          txt = re.sub(r'[^A-Za-z\s]','',markovText)
          txt = re.sub(r'\s+',' ',txt)
          txt = txt.split()

          #if len(self.last_message) > 2:
          #  for x in txt:
          #    if rhymes(x, self.last_message[-1]):
          #      break
              #if rhymes(self.last_message[0], txt[0]) or \
              #rhymes(self.last_message[-1], txt[-1]) or \
              #rhymes(self.last_message[0], txt[-1]) or \
              #rhymes(self.last_message[-1], txt[0]):
              #print 'rhyme...'
              #break

        output = re.sub(r'\s*[?.!]?$','', markovText)
        output = re.sub(r'\s,','',output)
        output = re.sub(r"\s'","'",output)
        
        output += punct()

        if random.randint(0,100) <= 15:
          output = user + random.choice([':',' -',',']) + ' ' + output

        self.last_message = output
        #print "%s:\t\t%s" % (self.nickname, output)
        self.msg(channel, str(output))
        self.data['last'] = time.time()
      
      
      if self.data['logging']:
        if self.data['redact']:
          n = 0
          for username in self.userlist:
            n += 1
            if msg.find(username) > -1:
              msg.replace(username,'user_%d' % n)
        
        self.log.append({'timestamp': time.time(),
                         'channel':channel,
                         'user':'user_%s' % self.userlist.index(user),
                         'msg':msg})

      
class MyBotS(protocol.ClientFactory):
    protocol = MyBot

    def __init__(self, channel, nickname):
        self.channel = channel
        self.nickname = nickname
        
    def clientConnectionLost(self, connector, reason):
        print "Lost connection (%s), reconnecting." % (reason,)
        time.sleep(speak_sleep * 3)
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        print "Could not connect: %s" % (reason,)

    def noticed(self, user, channel, message):
        pass

    def action(self, user, channel, msg):
        self.privmsg(user, channel, msg)

    def irc_INVITE(self, prefix, params):
       # well, we've been invited to params[1]...
       self.join(params[2])

if __name__ == "__main__":
  if(os.access(nickname+'.json',os.F_OK)):
    print 'reading json ..'
    with open(nickname + '.json') as f:
      json = f.read()
    print 'got ' + str(len(json)) + ' bytes.'
    print 'reading text ..'
    for f_ in inputfiles:
      with open(f_) as f:
        text += f.read()
    print 'got ' + str(len(text)) + ' bytes.'
    mychain = Chain(corpus=None, state_size=markov_length, model=Chain.from_json(json).model)
    mark = markovify.Text(input_text=text, state_size=markov_length, chain=mychain)
  else:
    print 'reading text ..'
    for f_ in inputfiles:
      with open(f_) as f:
        text += f.read()
    print 'got ' + str(len(text)) + ' bytes.'
    mark = markovify.Text(text, state_size=markov_length)

  s = {}
  reactor.connectTCP(ircserver, ircport,  MyBotS(ircchannel,nickname))
  reactor.run()
