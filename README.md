# howbot - the local drunkbot

Updated to work with discord and ollama.
Full documentation to come.

*WORK IN PROGRESS, wait for next version*

## FEATURES

Howbot chats on discord, connecting to either ollama or OpenAI API's.
Essentially it works like ChatGPT but over discord.

It can generate images through Stable Diffusion, search the web with SearX,
look at images, summarize youtube videos, and more.


## INSTALLATION

1. Create a discord bot via [Discord Developer Portal](https://discord.com/developers/applications)
2. Add discord token to `.token-discord`
3. Edit `config/{botname}.yaml.sample` and rename to `config/{botname}.yaml`
4. `uv venv --python=3.11` then `source .venv/bin/activate`
5. Run `python howbot.py`

### Dependencies

Right now the `requirements.txt` is full of various functionality that will be honed down.

For web search functionality, searx is required. A remote search URL can be used.
The ComfyUI image generation tool uses the Flux Dev/Schnell model, a LoRA, and a few extensions.

### Usage

Bot commands are prefixed with `!`:
  `!model` changes LLM models, `!models` lists models available through ollama
  `!personas` lists system prompts, `!persona` sets the prompt
  `!draw` generates an image over comfyui
  `!serverinfo` shows discord server info
  `!set` shows bot settings
  `!help` shows (to-be updated) help text.
  `!video` summarizes a youtube video
  `!search` and `!google` (_being moved to ollama tools_).

#### Models

_Qwen3 14b is the recommended language model due to it's tool following.
and Gemma3 4b/MiniCPM is recommended for visual reasoning._

Mistral Small 3.1 comes in second.

#### Personas

System prompts (personas) are stored in `personas.yaml`.
The current format is `[name]: [system prompt]`.

The following variables will be interpreted in system prompts:
  `{bot}`:  the bots nickname
  `{user}`: the speaking users nickname
  `{time}`: the current time
  `{date}`: the current date

#### ComfyUI

To generate images with stable diffusion (koboldcpp coming), ...

Commands:
  `{draw}`: generate an image. settings are indicated with `@`:
            * `@num=2` `@steps=20` `@model=fast` `@lora=<lora path>`
            * `@aspect=[wide|portrait|square]` `@cfg=[1-7]` `@seed=31337` `@detail=0.20` (detail daemon)
  `{imagine}`: generates an image by enhancing the prompt and choosing the aspect ratio/style.
  `{drawall}`: continually generates images until the mode is changed from `repeat`


More to come soon..
