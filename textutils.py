import re, random
version = "0.1.0"

def tonick(nick):
	if random.randint(0,100) <= 11:
		return nick + random.choice([': ',' - ',', ',' ',' ',' ',' ','! ',' ',' .. ', ' ... ', ' ', ' ', ' '])
	return ''

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

def fix_text(line, rev=False):
  if not line:
    return ''
  if not len(line):
    return ''
  if len(line) < 3:
    return line

  if rev:
    #print('Reversing!')
    try:
      line = ' '.join(line.split(' ')[-1::-1])
    except Exception as e:
      print(line)
      print(e)
  
  #print('Before: "%s"' % line)
  line = line.strip()

  line = re.sub(r'[^A-Za-z\s]','', line)
  line = re.sub(r'^\s','', line)
  line = re.sub(r'\s$','', line)
  line = re.sub(r'\s\s',' ', line)
  line = re.sub(r'\s,\s*$','', line)
  line = line.replace('\n',' ')
  line = line.replace('\r','')
  line = line.replace(' , ',", ")
  line = line.replace(' .', '')
  line = line.replace('"','')
  line = line.replace("'",'')
  line = line.replace(' s ',"'s ")
  line = line.replace(' t ',"'t ")
  line = line.replace(' nt ',"'nt ")
  line = line.replace(' re ',"'re ")
  line = line.replace(' ve ',"'ve ")
  line = line.replace(' id '," I'd ")
  line = line.replace("do'nt","don't")
  line = line.replace("wo'nt","won't")
  line = line.replace("did'nt","didn't")
  line = line.replace('y all ',"ya'll ")
  line = line.replace('  ', ' ')
  
  try:
    line = line[0].upper() + line[1:].lower()
  except Exception as e:
    print(line)
    print(e)
  
  #line = tb(line).correct().raw

  #print('After: "%s"' % line)

  return line
