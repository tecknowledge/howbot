#!/usr/bin/python
version = '0.1d'
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

#from search import search,_search

from yaml import load, dump

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

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
    
    self.irc = config['irc']
    self.persona = config['persona']
    self.markov = config['markov']
    self.speak = config['speak']

    self.searchengines = ['duckduckgo', 'google', 'amazon', 'bbcnews', 'discogs', \
               'piratebay', 'wolfram', 'youtube', 'stack', 'acronym', \
               'bing', 'rfc', 'scholar']

    self.log = []
    self.markovify = mark
    self.last_message = []

    self.userlist = []

    self.version = version
    self.sourceurl = sourceurl
    self.lastspoke = 0

    self.cmds = open('bot.cmds','r').read().split('\n')
    
    print 'Got ' + str(len(self.markovify.chain.model)) + ' chains'

    self.nickname = self.irc['nickname']
    print 'launching `%s`' % (self.nickname)
    return

  def _get_nickname(self):
      return self.factory.nickname

  #def connectionMade(self):
  #    self.nickname = self.nickname
  #    self.realname = self.irc['realname']
  #    super(self).irc.IRCClient.connectionMade(self)

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

      if self.irc['verbose']:
        print '%s <%s:%s> %s' % ( dt.datetime.now().strftime('%T') , channel, user, msg )

      if msg[0] == self.irc['trigger'] and len(msg) > 2:
        self.handle_command(channel, user, msg)
            
      if random.randint(0,200) <= self.speak['question'] and user not in self.irc['ignorelist']:
        out = re.sub(r'[^A-Za-z0-9]','',msg.split()[-1]) + '?'
        
        if self.irc['verbose']:
          print '%s <%s:%s> %s' % ( dt.datetime.now().strftime('%T') , channel, self.nickname, out )
        
        self.lastspoke = time.time()
        self.say(channel,out)
      
      if msg.find(self.nickname) > 1 or (random.randint(0,100) <= self.speak['rate'] and \
        (time.time() - self.lastspoke > self.speak['sleep'])):
        
        for x in xrange(self.markov['tries']):
          markovText = self.markovify.make_short_sentence(self.markov['length'],
                                              max_overlap_total=self.markov['overlap'],
                                              max_overlap_ratio=self.markov['ratio'],
                                              tries=self.markov['tries'])
          if not markovText or len(markovText) <= 5:
            pass
          
          txt = re.sub(r'[^A-Za-z\s]','',markovText)
          txt = re.sub(r'\s+',' ',txt)
          txt = txt.split()

        output = re.sub(r'\s*[?.!]?$','', markovText)
        output = re.sub(r'\s,','',output)
        output = re.sub(r"\s'","'",output)
        
        output += punct()

        if random.randint(0,100) <= 15:
          output = user + random.choice([':',' -',',']) + ' ' + output

        self.last_message = output
      
        if self.irc['verbose']:
          print '%s <%s:%s> %s' % ( dt.datetime.now().strftime('%T') , channel, self.nickname, output )

        self.msg(channel, str(output))
        self.lastspoke = time.time()
      
      
      # need to juse use logging and file rotator ..
      if self.irc['logging']:
        if self.irc['redact']:
          n = 0
          for username in self.userlist:
            n += 1
            if msg.find(username) > -1:
              msg.replace(username,'user_%d' % n)
        
        self.log.append({'timestamp': time.time(),
                         'channel':channel,
                         'user':'user_%s' % self.userlist.index(user),
                         'msg':msg})
        
  def handle_command(self, channel, user, msg):
    inp = msg[1:].split(' ')
      
    args = inp[1:] 
    cmd = inp[0]
    val = ''

    if self.irc['noauth'] or (user in self.irc['admin']):
      if len(args):
        val = args[0]
      
      if cmd == 'help':
        self.msg(user, '(commands): %s' % ( self.cmds ) )
     
      if cmd == 'version':
        self.msg(channel, '[TK]: howbot v%s %s' % ( self.version, self.sourceurl ) )

      if cmd == 'stats':
        self.msg(channel, '(stats) recorded %d lines since %s' % ( len(self.log),
                               dt.datetime.fromtimestamp(self.starttime).strftime('%F %T') ) )
      elif cmd == 'setup':
        self.msg(channel, '(speaking setup) %s' % self.speak )
      
      elif cmd == 'config':
        self.msg(user, '(config) %s' % self.cfg )


      elif cmd == 'persona':
        persona = ', '.join([ x for x in self.persona ])
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

class MyBotS(protocol.ClientFactory):
    protocol = MyBot

    def __init__(self, channel, nickname, realname, config, chain):
        self.cfg = config
        self.channel = channel
        self.nickname = nickname
        self.realname = realname
        self.markovify = chain
        
    def clientConnectionLost(self, connector, reason):
        print "Lost connection (%s), reconnecting." % (reason,)
        time.sleep(config['speak']['sleep'] * 3)
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
  botcfg = os.path.basename(sys.argv[0].replace('.py','.cfg'))
 
  print 'Using %s config' % botcfg
  config = load(open(botcfg))
  
  print 'personas: ',
  
  text = ''
  
  for f_ in config['persona'].values():
    with open(f_) as f:
      print '%s ' % f_,
      text += f.read()
  
  print '-- got ' + str(len(text)) + ' bytes.'
  
  mark = markovify.Text(text)

  irc = config['irc'] 
  
  reactor.connectTCP(irc['server'], irc['port'],
    MyBotS(irc['channel'], irc['nickname'], irc['realname'], config, mark) )
  reactor.run()
