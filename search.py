import tempfile
import subprocess
import BeautifulSoup
from bs4 import BeautifulSoup as bsoup
from infile import infile

def search(string, elvis = 'duckduckgo', mr = 10, sniplen = 96):
  """ hacky way with surfraw to search the weeb; filter for _search() """
  results = _search(string)
  title = results.keys()[0]
  print '\t\t\t', title, '\n'
  i = 1
  for res in results[title]:
    url = res[0].encode('utf-8', 'errors=ignore')
    print str(i) + ':', url
    snip = res[1].encode('utf-8', 'errors=ignore')
    snip = re.sub('\\s\\s*', ' ', snip)
    print '\t', re.sub('(' + string + ')', '*\x01*', snip, flags=re.IGNORECASE), '...', '\n'
    mr -= 1
    i += 1
    if not mr:
      return


def _search(string, elvis = 'duckduckgo'):
  """ search with surfraw, return a hash with the title as the key
    use search() to see pretty
  """
  engines = ['duckduckgo',
   'google',
   'amazon',
   'bbcnews',
   'discogs',
   'piratebay',
   'wolfram',
   'youtube',
   'stack',
   'acronym',
   'bing',
   'rfc',
   'scholar']
  if elvis not in engines:
    elvis = 'duckduckgo'
  tmpfile = tempfile.NamedTemporaryFile('w', dir='/tmp', prefix=elvis, suffix='.txt')
  try:
    cmd = ['/usr/bin/surfraw',
     '-o=%s' % tmpfile.name,
     elvis,
     string]
    print 'Executing', cmd
    w = subprocess.Popen(cmd)
    w.wait()
    html = bsoup(infile(tmpfile.name), 'html.parser')
    title = html.title.text
    tmpfile.close()
  except Exception as e:
    return {'Error': 'No results/error: ' + e.message}

  links = [ link.attrs['href'] for link in html.find_all(class_='result-link') ]
  snips = [ snip.text for snip in html.find_all(class_='result-snippet') ]
  output = []
  for i in xrange(len(links)):
    if i >= results:
      break
    output.append([links[i], snips[i]])

  return {title: output}
