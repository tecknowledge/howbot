#!/usr/bin/python
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

import markovify
from markovify import Chain
from markovify import Text

import json
from textblob import TextBlob as tb

adminuser = 'cb'
speak_rate = 50
speak_sleep = 10

nickname = 'phrack'
ircserver = 'irc.freenode.net'
ircport = 6667
ircchannel = '#tecknowledge'
cmdchar = '!'

markov_length = 1
markov_ratio = .7
markov_overlap = 15
sent_length = 60
markov_tries = 100
last_spoke = 0

question_rate = 1

inputfiles = ['/t/phrack2.txt']

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
    
    self.data = { 'admin': adminuser,
                  'cmdchar': cmdchar,
                  'rate': speak_rate,
                  'sleep': speak_sleep,
                  'markov': markov_length,
                  'length': sent_length,
                  'tries': markov_tries,
                  'spoken': 0
                }
    
    self.markovify = mark
    self.last_message = []

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
      
      #print "%s:\t\t%s" % (user, msg)

      if msg[0] == self.data['cmdchar']:
        
        inp = msg[1:].split(' ')
        
        args = inp[1:] 
        cmd = inp[0]
        args = inp[1:] 
        
        if user == adminuser:
          if cmd == 'set':
            pass
        
        self.msg(channel, '-- cmdchar:%s user:%s cmd:%s args:%s --' % ( self.data['cmdchar'], user, cmd, args ))
        
      if random.randint(0,200) <= question_rate and user not in ['reddit','twitter']:
        out = re.sub(r'[^A-Za-z0-9]','',msg.split()[-1]) + '?'
        #print self.nickname + ":\t\t" + out
        self.data['last'] = time.time()
        return self.say(channel,out)
      
      if msg.find(self.nickname) > 1 or (random.randint(0,100) <= self.rate and \
        (time.time() - self.data['last'] > self.data['sleep'])):
        
        for x in xrange(markov_tries):
          markovText = self.markovify.make_short_sentence(sent_length,max_overlap_total=markov_overlap,max_overlap_ratio=markov_ratio,tries=markov_tries)
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
        

        self.last_message = output.split()
        #print "%s:\t\t%s" % (self.nickname, output)
        self.msg(channel, str(output))
        self.data['last'] = time.time()
      
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
