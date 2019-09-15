#!/usr/bin/python
# irc bot framework based on twisted

''' import ircbot
    ircbot.nickname = mybotnick
    ircbot.server = myserver
    ircbot.port = myport
    ircbot.channel = myleetchan
    
    class MyBot(ircbot.BotClient):
      def privmsg(self, user, channel, msg):
      # see twisted.words.protocols.irc.IRCClient
    ircbot.connect()
'''

import os, sys, re, random, signal, time
from twisted.words.protocols import irc
from twisted.internet import protocol
from twisted.internet import reactor

nickname = 'testbot'
server = '127.0.0.1'
port = 6667
channel = '#test'

class BotClient(irc.IRCClient):
  def __init__(self):
    self.nickname = nickname
    print('launching `%s`' % (self.nickname))
    return
  
  def _get_nickname(self):
      return self.factory.nickname
  
  def signedOn(self):
      self.join(self.factory.channel)
      print("Signed on as %s." % (self.nickname,))
  
  def joined(self, channel):
      print("Joined %s." % (channel,))

  def privmsg(self, user, channel, msg):
      if not user: return
      user = user.split('!', 1)[0]
      print("%s:\t\t%s" % (user, msg))

class BotFactory(protocol.ClientFactory):
    protocol = BotClient

    def __init__(self, channel, nickname):
        self.channel = channel
        self.nickname = nickname
        
    def clientConnectionLost(self, connector, reason):
        print("Lost connection (%s)" % (reason,))

    def clientConnectionFailed(self, connector, reason):
        print("Could not connect: %s" % (reason,))

    def noticed(self, user, channel, message):
        pass

    def action(self, user, channel, msg):
        self.privmsg(user, channel, msg)

    def buildProtocol(self, addr):
        me = BotClient()
        me.factory = self
        return me

def connect(ircserver=server, ircport=port, ircchannel=channel, nickname=nickname):
  Bot = BotFactory(ircchannel, nickname)
  bot = reactor.connectTCP(ircserver, ircport, Bot)
  return bot

if __name__ == "__main__":
  connect()
