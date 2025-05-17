# TODO: Check for spacy model downloads

import spacy, base64
import pytesseract, requests, io
from PIL import Image
from logging import info, debug

try:
  nlp = spacy.load('en_core_web_sm')
except:
  spacy.cli.download('en_core_web_sm')
  nlp = spacy.load('en_core_web_sm')

def sentence_split(text, max_size=2000):
    # Load the spaCy model
    global nlp
    # Process the text with spaCy
    debug('Splitting:',len(text))
    doc = nlp(text)

    # Split the text into paragraphs
    paragraphs = [str(p) for p in doc.sents if len(str(p).strip()) > 0]

    chunks = []
    current_chunk = ""
    current_size = 0

    for para in paragraphs:
        para_size = len(para.encode('utf-8'))

        if current_size + para_size > max_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_size = 0

        if para_size > max_size:
            # If a single paragraph exceeds max_size, split it
            for i in range(0, len(para), max_size):
                chunk = para[i:i+max_size]
                chunks.append(chunk)
        else:
            current_chunk += para + "\n"
            current_size += para_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

async def tesseract(image_url):
#  if image.endswith(tuple(['.jpg','.jpeg','.png','.webp','.gif'])):
  response = requests.get(image_url)
  if response.status_code == 200:
    img = Image.open(io.BytesIO(response.content))
    text = pytesseract.image_to_string(img)
    if len(text):
      debug('Tesseract: Found text "',text,'"')
      return text
  # TODO: Add a PIL image test, use that ..
  return ''
