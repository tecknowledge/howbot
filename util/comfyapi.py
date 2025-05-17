# TODO: Add detail daemon [x]
# TODO: Fix !draw, llm [x]
# TODO: Find loras
"""

I'm currently thinking of how a langchain tool for stable diffusion would work.
I've been using chatgpt to generate images for me and wonder how the process works beneath the surface.

I have an image prompt that works pretty well, but it could be twice as long, as it is 8k, or maybe benefit from a LoRA.

I wonder if it would be better to have a built in tool handle that sort of thing for some uses,
or do have it handled in the UI like it is done with Fooocus?

"""

import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid, json, re, string, io, os, sys, glob, random
import urllib.request, urllib.parse
import requests
from PIL import Image
from typing import Optional
from io import BytesIO
import base64
import util.oai as oai
import ollama
import logging

#from custom_nodes.OneButtonPrompt.build_dynamic_prompt import build_dynamic_prompt

#from langchain_community.utilities import SearxSearchWrapper
import uuid

default_style='photographic'
default_workflow = 'sdxl-basic-api.json'
comfyui_client_id = str(uuid.uuid4())
comfyui_server_address = "localhost:8188"
#search = SearxSearchWrapper(searx_host="http://127.0.0.1:8888")
#image_prompt_text = open('image_prompt.txt').read()

aspect_prompt = '''You are a professional photographer and digital artist. Given the following
image description, choose if the image should be in a wide, square, or portrait
aspect ratio. If the image is of a single subject, choose portrait. If the image
is of multiple subjects side by side, or a landscape or overview, choose wide.
Choose square for a meme or a generic image. If unsure simply return square.
Only return your one word assessment.'''

# TODO: Turn into a list and validate, alternatively read all styles..
style_prompt = '''Based on the following styles, choose one and return it. Do not return anything not on this list.
photographic: To enhance most realistic photographs.
3d-model: For CGI and 3D rendered images.
digital art: For digital art.
line art: For line drawings.
artstyle-surrealist: For surrealist imagery.
artstyle-psychedelic: For trippy psychedelic images.
artstyle-abstract: For abstract art pieces.
artstyle-watercolor: For water color art.
futuristic-cybernetic: For futuristic images.
game-retro game: For old-school retro games.
anime: For anime, manga, and other japanese animation.
comic book: For comic books and action figures
fantasy art: For fantasy and magical illustrated art
'''

bot = None

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": comfyui_client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(comfyui_server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(comfyui_server_address, url_values)) as response:
        return response.read()


def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(comfyui_server_address, prompt_id)) as response:
        return json.loads(response.read())


def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]

    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            images_output = []
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images


async def ollamachat(prompt, system=None, temperature=None, length=None):
  if bot.model == 'unkn0wn':
    bot.get_model()

  if system == None:
    system = bot.persona

  options = bot.presets[bot.preset]

  if temperature != None:
    options['temperature'] = float(temperature)

  if length != None:
    options['num_predict'] = int(length)

  try:
    text = ollama.chat(model=bot.model,
                       messages=oai.prep(prompt, system=system),
                       options=options)
  except Exception as e:
    error(f'WebGPT: {e}')

  return text['message']['content']


def sanitize_filename_part(text, replace_spaces=True):
  invalid_filename_chars = '<>:"/\\|?*\n'
  invalid_filename_prefix = ' '
  invalid_filename_postfix = ' .' 
  re_nonletters = re.compile(r'[\s' + string.punctuation + ']+')
  re_pattern = re.compile(r"(.*?)(?:\[([^\[\]]+)\]|$)")
  re_pattern_arg = re.compile(r"(.*)<([^>]*)>$")
  max_filename_part_length = 128

  if text is None:
      return None 

  if replace_spaces:
      text = text.replace(' ', '_')

  text = text.translate({ord(x): '_' for x in invalid_filename_chars})
  text = text.lstrip(invalid_filename_prefix)[:max_filename_part_length]
  text = text.rstrip(invalid_filename_postfix)
  return text


def find_tags(text):
    # Find all tags in the format @tagname=value
    pattern = r'@(\w+)=([^\s@]+)'
    tags = re.findall(pattern, text)
    
    # Remove the tags from the original text
    cleaned_text = re.sub(pattern, '', text)
    
    # Optionally, remove any extra whitespace left behind
    cleaned_text = ' '.join(cleaned_text.split())

    return cleaned_text, tags


def sdimg(prompt: str, cfg: Optional[int] = 1, steps: Optional[int] = 10, 
          width: Optional[int] = 1024, height: Optional[int] = 1024,
          seed: Optional[int] = -1, sampler: Optional[str] = 'Euler a',
          aspect: Optional[str] = 'square', enhance: Optional[bool] = False,
          apiurl: Optional[str] = 'http://localhost:8000/sdapi/v1/txt2img', bot=None):

  if seed == -1: 
    seed = random.randint(1, 18446744073709551614)

  if enhance:
    aspect = bot.generate(prompt, system=aspect_prompt, temperature=0, length=16)
    # TODO: parse style json and manually add
    # new_style = bot.generate(prompt, system=style_prompt, temperature=0).strip()
    prompt = bot.generate(prompt, system=blind_prompt, temperature=1, length=512)

  #logging.debug('Prompt: %s' % prompt)
  
  if aspect == 'wide':
    width = 1360
    height = 960
  elif aspect == 'portrait':
    width = 768
    height = 1024
  else:
    width = 1024
    height = 1024
  
  data = {'prompt': prompt, 'seed': seed, 'steps': steps, 'cfg_scale': cfg,
          'width': width, 'height': height, 'sampler': sampler }
  
  #logging.debug(f'Dimensions: {str(data["width"])}x{data["height"]}')

  with requests.post(apiurl, json=data) as response:
     img = response.json()['images'][0]
     return [prompt, Image.open(BytesIO(base64.b64decode(img)))]


async def generate_image(prompt, steps=None, enhance=False, num=3, style=default_style, workflow=default_workflow, aspect='square', chatbot=None):
  loras = []
  cfg = ''
  model = ''
  detail = ''

  if chatbot:
    if chatbot.backend == 'openai':
      logging.warn('Using openai')
      llm = oai.q
    elif chatbot.backend == 'ollama':
      logging.warn('Using ollama')
      global bot
      bot = chatbot
      llm = ollamachat
  else:
    llm = oai.q
  
  prompt, tags = find_tags(prompt)

  if tags:
    logging.info(f'Prompt tags: {tags}')
    for tag in tags:
      if tag[0] == 'aspect':
        aspect = tag[1]
      elif tag[0] == 'steps':
        steps = tag[1]
      elif tag[0] == 'cfg':
        cfg = tag[1]
      elif tag[0] == 'lora':
        loras.append(tag[1])
      elif tag[0] == 'seed':
        seed = tag[1]
      elif tag[0] == 'num':
          num = tag[1]
      elif tag[0] == 'detail': # fast, full, real
          detail = tag[1]
      elif tag[0] == 'model': # fast, full, real
          model = tag[1]

  if enhance:
    logging.info('Enhancing image')
    if 'aspect' not in tags:
      sysprompt = f'{aspect_prompt} /no_think'
      new_aspect = await llm(prompt, system=sysprompt)
      aspect = re.sub(r'<think>.*</think>', '', str(new_aspect), flags=re.MULTILINE|re.DOTALL).strip()
    if 'style' not in tags:
      sysprompt = f'{style_prompt} /no_think'
      new_style = await llm(prompt, system=sysprompt)
      style = re.sub(r'<think>.*</think>', '', str(new_style), flags=re.MULTILINE|re.DOTALL).strip()
    new_prompt = await llm(prompt, system=chatbot.personas['artist'])

    prompt = re.sub(r'<think>.*</think>', '', str(new_prompt), flags=re.MULTILINE|re.DOTALL).strip()

    logging.warn(f'New aspect: "{new_aspect}" Style: "{new_style}"')
    
  #logging.info('Prompt: %s (%s)' % (prompt, style))
  #logging.info('Workflow: %s' % default_workflow)

  prompt_workflow = json.load(open(os.path.join('config',workflow)))

  fileprefix = prompt
  
  if len(fileprefix) > 100:
    fileprefix = fileprefix[:100]

  loader_node = prompt_workflow["42"]["inputs"]
  dim_node = prompt_workflow["20"]["inputs"]
  save_node = prompt_workflow["34"]["inputs"]
  seed_node = prompt_workflow["43:0"]["inputs"]
  sampler_node = prompt_workflow["43:2"]["inputs"]
  style_node = prompt_workflow["38"]["inputs"]
  clip_node = prompt_workflow["39"]["inputs"]
  lora_node = prompt_workflow["40"]["inputs"]
  detail_node = prompt_workflow["44"]["inputs"]
  
  if aspect == 'wide':
    dim_node["width"] = 1368
    dim_node["height"] = 960
  elif aspect == 'portrait':
    dim_node["width"] = 768
    dim_node["height"] = 1280
  else:
    dim_node["width"] = 1024
    dim_node["height"] = 1024

  if model == 'fast':
    loader_node['unet_name'] = "flux1-schnell-fp8.safetensors"
    loader_node['weight_dtype'] = "fp8_e4m3fn"
  elif model == 'full':
    loader_node['unet_name'] = "flux1-dev.safetensors"
    loader_node['weight_dtype'] = "fp8_e4m3fn"
  elif model == 'real':
    loader_node['unet_name'] = "realflux10b_10bTransformer.safetensors"
    loader_node['weight_dtype'] = "default"

  #logging.debug(f'Dimensions: {str(dim_node["width"])}x{dim_node["height"]}')
  
  if not 'seed' in tags:
    seed = random.randint(1, 18446744073709551614)
  sampler_node["noise_seed"] = int(seed)
  
  if cfg:
    clip_node["cfg"] = int(cfg)

  if loras:
    lora_num = 2
    
    for lora in loras:
      logging.warn(f'Loading lora #{lora_num}: {lora}')
      lora_key = f'lora_{lora_num}_name'
      lora_node[lora_key] = lora + '.safetensors'
      lora_node["num_loras"] = lora_num
      lora_num = lora_num + 1

  if steps:
    sampler_node["steps"] = int(steps)
  else:
    steps = sampler_node["steps"]
  
  style_node["text_positive"] = prompt
  style_node["style"] = style
  clip_node["clip_l"] = prompt

  if 'detail' in tags:
    detail_node["detail_amount"] = float(detail)

  dim_node["batch_size"] = int(num)
  save_node["filename_prefix"] = sanitize_filename_part(fileprefix)

  ws = websocket.WebSocket()
  ws.connect("ws://{}/ws?clientId={}".format(comfyui_server_address, comfyui_client_id))

  image_nodes = get_images(ws, prompt_workflow)
  images = []

  for node_id in image_nodes:
    for image_data in image_nodes[node_id]:
      images.append(Image.open(io.BytesIO(image_data)))
  
  logging.warn('Got %s images' % len(images))
  
  return {'prompt': prompt,
          'style': style,
          'steps': steps,
          'seed': seed,
          'images': images,
          'workflow': workflow,
          'host': comfyui_server_address }


def interrogate(img, api='sd', apiurl='http://localhost:8000/sdapi/v1/interrogate'):
  if api == 'comfy':
    pass
  elif api == 'sd':
    if str(type(img)) == "<class 'PIL.PngImagePlugin.PngImageFile'>":
      img = img.tobytes()
    elif type(img) == str:
      res = requests.get(img).content
      img = Image.open(io.BytesIO(res)).tobytes()
    else:
      print('Unknown image type:',type(img))

    img_b64 = base64.b64encode(img).decode(encoding='utf-8',errors='strict')
    data = json.dumps({ 'image': img_b64, 'model': 'clip'})
    res = requests.post(apiurl, data=data)
    if res.status_code == 200:
      return res.json()['caption']
    else:
      return res.text
