_version = '0.4b'

import os, time, re
import json, random, yaml
import openai, requests, string
from openai import AsyncOpenAI
from datetime import datetime as dt
from urllib.parse import urljoin

# TODO: Make it automatically (via HEAD url checks) work with llama.cpp and python?
# TODO: Move config to yaml
SAVEDIR='.chatlog'
BASEDIR='./'

default_stop = ['<|eot_id|>','<|end_of_text|>','<|end_of_turn|>','<|end|>','<|im_end|>','<|END_OF_TURN_TOKEN|>']
default_api_base = 'http://localhost:8000/v1/'
default_api_key = ''
default_max_tokens = 1024
default_temperature = 1
default_persona = 'howsy'
personas = {}

model = ''
o_prompt = ''
chat_history = []


# query LLM, return response text
# debug: return full response

async def q(prompt, system=default_persona, length=default_max_tokens,
      stop=default_stop, temperature=default_temperature, save=True,
      seed=None, debug=False, api_base=default_api_base, history=False,
      model='gpt-3.5-turbo'):
  global chat_history

  if history:
    chat_history.append(['user',prompt])
    prompt = chat_history
  
  res = await generate(prep(prompt, system=system),
                  temperature=temperature, stop=stop, length=length,
                  seed=seed, save=save, debug=debug, api_base=api_base,
                  model=model)
  if history:
    chat_history.append(['assistant',res])

  return res

# query LLM, print response text

async def p(prompt, system=default_persona, length=default_max_tokens,
      stop=default_stop, temperature=default_temperature, save=True,
      seed=None, debug=False, api_base=default_api_base, history=False,
      model='gpt-3.5-turbo'):
  global chat_history
  
  if history:
    chat_history.append(['user',prompt])
    prompt = chat_history
  
  res = await generate(prep(prompt, system=system),
                 temperature=temperature, stop=stop, length=length,
                 seed=seed, save=save, debug=debug, api_base=api_base,
                 model=model)
  if history:
    chat_history.append(['assistant',res])
  
  print(res)

# prepare response for LLM chat format

def prep(prompt, system=default_persona): 
  global model, o_prompt, personas

  o_prompt = prompt

  nowd = dt.now().strftime('%A, %B %d, %Y')
  nowt = dt.now().strftime('%X %p')
  
  if isinstance(prompt, str):
    #if system in personas:
    #  prompt = [['system', personas[system].format(time=nowt, date=nowd)], ['user', prompt]]
    prompt = [['system', system],['user',prompt]]
    #else:
  else:
    system = prompt[0][1]

  messages=[]
  
  # sent [[role, system], [role, message], ...]
  if system in personas:
    system = personas[system].format(time=nowt, date=nowd)
    messages.append({'role': 'system', 'content': system})
    prompt.pop(0)
  else:
    #messages = [{'role':'system','content':prompt[0][1]}]
    messages = [{'role':'system', 'content': system}]
    prompt.pop(0)
    #print('Unknown persona:',prompt[0][1])
    
  for msg in prompt:
    messages.append({'role': msg[0], 'content': msg[1]})
  
  return messages

def get_url(apiurl):
  try:
    if requests.head(apiurl + 'completion').status_code == 405:
      return f'{apiurl}/completion'
  except Exception as e:
    print('get_url:',e)
  try:
    if requests.head(apiurl + 'v1/completions').status_code == 405:
      return f'{apiurl}/v1/completions'
    else:
      return 'notok'
  except Exception as e:
    print('get_url:',e)
    return e

def get_model(api_base=None, api_key=None):
  global model
  
  if not api_key:  api_key = default_api_key
  if not api_base: api_base = default_api_base
  
  headers = {'accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': api_key } 
  try:
    res = requests.get(urljoin(api_base,'models'), headers=headers)
    if res.status_code == 200:
      model = res.json()['data'][0]['id']
      model = os.path.splitext(os.path.split(model)[-1])[0]
    else:
      model = 'unkn0wn'
  except Exception as e:
    model = 'unkn0wn'
    print('Error:',e)
  return model

async def generate(prompt, api_key=None, api_base=None,
             temperature=default_temperature, length=default_max_tokens,
             stop=default_stop, seed=None, save=True,
             print_prompt=False, verbose=False, debug=False,
             model='gpt-3.5-turbo') -> dict:
  
  if not api_key:  api_key = default_api_key
  if not api_base: api_base = default_api_base

  # server side commands ..
  try:
    if isinstance(prompt,list) and prompt[1][1] == '??personas':
      return ', '.join(list(personas.keys()))
    if isinstance(prompt,list) and prompt[1][1] == '??reload':
      load_data()
      return 'Reloading data.'
  except: pass
  
  openai.base_url = api_base
  openai.api_key = api_key
  
  if not seed:
    random.seed(None, version=2)
    seed = random.randint(1, 18446744073709551614)

  if print_prompt:
    print('--- ', json.dumps(o_prompt))
    print('+++ ', json.dumps(prompt))

  start = time.time()
  
  #res = openai.chat.completions.create(model='any', get_model(api_base=api_base), messages=prompt,
  client = AsyncOpenAI(api_key=api_key, base_url = api_base)

  res = await client.chat.completions.create(model=model, messages=prompt,
                                       temperature=float(temperature), max_tokens=int(length), stop=stop, seed=int(seed))
  end = time.time()

  try:
    res.usage.time = '%0.2f' % (end - start)
    res.usage.tps = '%0.2f' % (float(res.usage.completion_tokens) / float(res.usage.time))

    response = res.choices[0].message.content
    
    if not len(response):
      return ''

    usage = res.usage
    
    if(save):
      save_prompt(prompt, response, seed, temperature, usage)


    if verbose:
      print(usage)
    
    if debug:
      res = res.model_dump()
      res['messages'] = prompt
      return res
    else:
      return response.strip()
  
  except Exception as e:
    print('Error?', e)
    return res

# return an dict with value (token count) and ids
def tokenize(text, api_base=None, api_key=None):
  if not api_key:  api_key = default_api_key
  if not api_base: api_base = default_api_base
  
  headers = {'accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': api_key } 
  
  return requests.post(urljoin(api_base, 'api/extra/tokencount'), json={'prompt': text}, headers=headers).json()

# stream results back with a generator
def stream(prompt, show=False, api_base=None, temperature=1): 
  if not api_key:  api_key = default_api_key
  if not api_base: api_base = default_api_base
  
  headers = {'accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': api_key } 
  
  try:
    with requests.post(urljoin(api_base,'v1/completions'), json={'stream': True,'prompt':prompt,
                       'stop': [''], 'temperature': temperature, 'max_tokens': 8192}, headers=headers, stream=True) as response: 
       for line in response.iter_lines(): 
         if len(str(line.decode())): 
           try:n = json.loads(str(line.decode()).replace('data: ',''))['choices'][0]['text']
           except Exception as e:
             break
           if show:
             print(n,end='',flush=True) 
         yield n
  except Exception as e:
    print(f'Error: {e}')

def sanitize_filename_part(text, replace_spaces=True, length=64):
  invalid_filename_chars = '<>:"/\\|?*\n'
  invalid_filename_prefix = ' '
  invalid_filename_postfix = ' .' 
  re_nonletters = re.compile(r'[\s' + string.punctuation + ']+')
  re_pattern = re.compile(r"(.*?)(?:\[([^\[\]]+)\]|$)")
  re_pattern_arg = re.compile(r"(.*)<([^>]*)>$")

  if text is None:
      return None 

  if replace_spaces:
      text = text.replace(' ', '_')

  text = text.translate({ord(x): '_' for x in invalid_filename_chars})
  text = text.lstrip(invalid_filename_prefix)[:length]
  text = text.rstrip(invalid_filename_postfix)
  return text

def save_prompt(prompt, response, seed, temperature, usage):
  res = {}
  res['prompt'] = prompt[-1]['content']
  res['response'] = response
  res['usage'] = usage.__dict__
  res['seed'] = seed
  res['temperature'] = temperature
  try:
    fname = '%s/%s_%s.json' % (SAVEDIR, dt.now().isoformat(), sanitize_filename_part(res['prompt']))
    with open(fname,'w') as output:
      output.write(json.dumps(res))
  except Exception as e:
    print(f'SAVING to {SAVEDIR}: {e}',e)

def load_data():
  global default_persona, personas
  try:
    personas = yaml.load(open(BASEDIR+'personas.yaml').read(), Loader=yaml.CLoader)
    default_persona = personas['howsy']
  except Exception as e:
    print('Loading personas:',e)
    personas={}

load_data()
