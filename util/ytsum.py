import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi as ytsubs
import util.oaia as oai
import humanize
from datetime import datetime as dt
import re
from logging import debug, info, warning, error

# match a youtube URL and download the subtitles/captions and summarize them
async def ytsum(video_url, length=12000, summarize=True):
  txt = output = '' 
  yt = yt_dlp.YoutubeDL()
  
  try:
    print(f'Fetching {video_url} (yt_dlp)')
    res = yt.extract_info(video_url, download=False)
    duration = humanize.naturaldelta(res['duration'])
    # TODO: Fix posted date
    #posted = humanize.naturaltime(dt.fromtimestamp(res['epoch']))
    header = f"{res['title']} - {duration} ({res['view_count']} views/{res['like_count']} likes/{res['comment_count']} comments)\n"
  
  except Exception as e:
    error(f'Fetching video information for {video_url}: {e}')
    return

  try: 
    videoId = re.match(r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=)?([a-zA-Z0-9_-]{11})', video_url).group(1)
    print(f'Video ID: {videoId}')
    srt = ytsubs.get_transcript(videoId)
    
    for t in srt:
      if len(txt) < length:
        txt += ' ' + t['text']
  
  except:
    # TODO: If this fails, download audio and use whisper, checking for language, then translate
    print('Using yt_dlp')
    capurl = res['automatic_captions']['en'][0]['url']
    captions = requests.get(capurl).json()
    
    for x in captions['events']:
      if 'segs' in x and 'utf8' in x['segs'][0]:
        if len(txt) < length:
          txt += f" {x['segs'][0]['utf8'].strip()}"
  
  finally:
    if summarize:
      output = await oai.q(txt, system='Summarize the following video transcript.', length=550, temperature=0.4)
      return header + output
    else:
      return txt
