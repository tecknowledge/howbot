# based on webgpt, a command line interface tool that uses the GPT-3 API to generate summaries from the web and provides a link to the source
# TODO: Convert to async
#       Embed/chunk results/RAG

import os
import re
import sys
import time
import util.oai as oai
import ollama
import requests
from bs4 import BeautifulSoup as bs4
from concurrent.futures import ThreadPoolExecutor
from logging import info, error

from langchain_community.utilities import searx_search # import SearxSearchWrapperTask
searx = searx_search.SearxSearchWrapper(searx_host='http://192.168.1.2:8080')
import logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s %(levelname)s %(funcName)s %(threadName)s(%(lineno)d) -%(levelno)s: %(message)s')

# supress warnings
#warnings.filterwarnings("ignore")

query = ''
temperature = 0.5
max_tokens = 500
max_snippet = 2500
min_snippet = 1000
num_results = 12
bot = None

def simple_search(query):
  results = searx.results(query, num_results=5)
  result = ''
  
  for r in results:
    result += '* %s: %s\n<%s>\n' % (r['title'], r['snippet'], r['link'])
  # TODO: Add a custom system prompt to format the results?
  
  return result

def search_searx(query, return_json=False, time_range='year', num=num_results, with_data=True):
  info(f'Searching: {query}')
  results = searx.results(query, num_results=num, time_range=time_range)
  links = [ r['link'] for r in results ]
  
  with ThreadPoolExecutor(max_workers=len(links)) as executor:
    docs = list(executor.map(readurl, links))
  
  for i, result in enumerate(docs):
      if result and len(result):
        results[i]['html'] = result
  
  return results

def readurl(url):
  response = requests.get(url)
  info('Reading %s: %s:' % (url, response.status_code))
  
  if response.status_code == 200:
      soup = bs4(response.content, "html.parser")
      html_string = soup.get_text().replace('\n','')
      
      info('Got %d' % (len(html_string)))
      return html_string

def ollamachat(prompt, system=None, temperature=None, length=None):
  if bot.cfg.model == 'unkn0wn':
    bot.get_model()

  if system == None:
    system = bot.cfg.persona

  options = bot.cfg.presets[bot.cfg.preset]

  if temperature != None:
    options['temperature'] = float(temperature)

  if length != None:
    options['num_predict'] = int(length)

  try:
    text = ollama.chat(model=bot.cfg.model,
                       messages=oai.prep(prompt, system=system),
                       options=options)
  except Exception as e:
    error(f'WebGPT: {e}')

  return text['message']['content']

def process(query, num=6, time_range='year', backend='ollama', chatbot=None):
    if backend == 'openai':
      llm = oai.q
    
    elif backend == 'ollama':
      global bot
      bot = chatbot
      llm = ollamachat

    search_results = search_searx(query, num=num, time_range=time_range)
    results = []

    for i in search_results[:num_results]:
        if 'html' in i and len(i['html']):
          txt = i['html'][:max_snippet]
          if len(txt) < min_snippet:
              continue
        else:
          continue
        prompt = """Given the following question:'"""+query+"""'
        Extract the text from the following content relevant to the question and summarize in detail:

        '"""+txt+"""'

        Extracted summarized content:"""

        try:
          a = {
              'query': query,
              'title': i['title'],
              'link': i['link'],
              'text': txt,
              'summary': llm(prompt=prompt, length=max_tokens, system='librarian')
          }
        except Exception as e:
          print('Query:',query,'Error:',e)
          continue

        results.append(a)
    return results

# This function prints the results in a nice format
# for discord, reformat into markdown/embed
# summarize and answer question overall and refer to each snippet/link numerically
# perform more logic in the search - which links/snippets are relevant, xyz

def output(query, data):
  print('Time:',(time.time() - start))
  print('')
  print('\033[1m' + 'Query:' + '\033[0m', "\x1B[3m" + query + "\x1B[0m")
  print('\033[1m' + 'Results: ' + '\033[0m')

  for i in data:
    print('')
    print('')
    # print('\033[1m' + '' + '\033[0m',)
    print(" - '"+i['summary'].strip()+"'")
    print('['+ '\033[1m' + 'source:' + '\033[0m', '\033[34m' + "\x1B[3m" + i['link'] + "\x1B[0m" + '\033[00m' +']')
    print('')

def run(query):
  data = process(query)
  output(query, data)

if __name__ == '__main__':
  start = time.time()
  sys.argv.pop(0)
  run(' '.join(sys.argv))
