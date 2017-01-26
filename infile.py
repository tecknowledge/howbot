import itertools
import os

def infile(f_):
  try:
    record = ''
    f = open(f_, 'rb')
    fd = f.fileno()
    for i in itertools.count():
      newrecord = os.read(fd, 1048576) or False
      if not newrecord:
        break
      record += newrecord
  except Exception as e:
    error(e.message)

  return record
