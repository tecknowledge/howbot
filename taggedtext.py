#!/usr/bin/python
#based on code from https://joshuanewlan.com/spacy-and-markovify

import sys, re, markovify, spacy, textacy, random
from unidecode import unidecode
from importlib import reload
#import textacy.preprocess, textacy.preprocessing, textacy.preprocessing.resources

#textacy.constants = textacy.preprocessing.resources
#reload(textacy)
#reload(textacy.preprocess)

nlp = spacy.load('en')

class TaggedText(markovify.Text):
  def sentence_split(self, corpus):
    """
    Splits full-text string into a list of sentences.
    """
    sentence_list = []

    #pat = re.compile(' \*[A-Z]*\*')
    
    for doc in corpus:
      #for sent in list(doc.sents):
        #sentence_list += re.sub(pat,'', textacy.preprocess.preprocess_text(sent.text,no_urls=True,no_emails=True, no_phone_numbers=True))
      sentence_list += list(doc.sents)
    
    return sentence_list
  
  #split_pat = re.compile(r'\s+')
  def word_split(self, sentence):
    """
    Splits a sentence into a list of words.
    """
    # this is done to use comparisons like in make_sentence_from*
    
    if type(sentence) == str:
      corpus = textacy.Corpus(lang='en')
      corpus.add_text(text=sentence)
      sentence = corpus.docs[0]

    return ["::".join((word.orth_,word.pos_)) for word in sentence]
  
  def word_join(self, words):
    sentence = " ".join(word.split("::")[0] for word in words)
    return sentence

  def test_sentence_input(self, sentence):
    """
    A basic sentence filter. This one rejects sentences that contain
    the type of punctuation that would look strange on its own
    in a randomly-generated sentence. 
    """
    sentence = sentence.text
    reject_pat = re.compile(r"(^')|('$)|\s'|'\s|[\"(\(\)\[\])]")
    # Decode unicode, mainly to normalize fancy quotation marks
    if sentence.__class__.__name__ == "str":
      decoded = sentence
    else:
      decoded = unidecode(sentence)
    # Sentence shouldn't contain problematic characters
    if re.search(reject_pat, decoded): return False
    return True

  def generate_corpus(self, corpus):
    """
    Given a text string, returns a list of lists; that is, a list of
    "sentences," each of which is a list of words. Before splitting into 
    words, the sentences are filtered through `self.test_sentence_input`
    """
    sentences = self.sentence_split(corpus)
    passing = filter(self.test_sentence_input, sentences)
    runs = map(self.word_split, sentences)
    #print(runs[0])
    return runs

if __name__ == '__main__':
  if len(sys.argv) < 2:
    print('Usage: %s corpus' % sys.argv[0])
    sys.exit(2)
