#howbot 0.2a

the local drunkbot and cosmic relief

Based on the markovify library - http://github.com/jsvine/markovify

Now python 3 compatible and includes parts of speech text filter from taggedtext.py - https://joshuanewlan.com/spacy-and-markovify

Also regularly updates and saves the markov chain to gzipped JSON

And reads its configuration from yaml, or its brain from a tagged spacy/textacy document corpus

Also uses a slightly modified markovify library

Have fun

#use

edit the yaml file, but you don't have to add anything to the brain: line

launch howbot.py [yaml file] [input:text, textacy corpus, gzipped json markov chain]

this only has to be done once. if you change the name of the yaml file in howbot.py
it doesn't need to be specified. and after it reads the corpus files, it saves them
to json so they only need to be specified once. you can later add more files this way
or [soon] during runtime or switch brains.

So after that, just run howbot.py howbot.yaml howbot.json.gz


Other bots of distinguish:

https://github.com/Agade09/CGBot2 / https://www.codingame.com/blog/markov-chain-automaton2000/ - CGBot, uses techniques to reduce markov memory size

https://github.com/gunthercox/ChatterBot - chatterbot, uses neural net for generation

https://github.com/capnrefsmmat/seuss - the rhyming bot from the future

https://github.com/cjones/madcow - good utility bot, megahal is funny, lots of functions

https://github.com/spion/triplie-ng - another type of markov/ai implementation

https://github.com/bingos/gumbybrain

http://lcamtuf.coredump.cx/c3.shtml - Don't let the age fool you! Its one of the most innovative bots in terms of approach - most of the other bots have a fixed source of input, this bot is more inquisitive... :)
