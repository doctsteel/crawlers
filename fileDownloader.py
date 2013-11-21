#!/usr/bin/python3
# Author: Emmanuel Odeke <odeke@ualberta.ca>
# Scrap any website for files with target extensions eg pdf, png, gif etc
# Tested on, and supporting versions: Python2.X and above

import re
import sys

from hashlib import md5

pyVersion = sys.hexversion/(1<<24)
if pyVersion >= 3:
  import urllib.request as urlGetter
  encodingArgs = dict(encoding='utf-8')
else:
  import urllib as urlGetter
  encodingArgs = dict()

DEBUG = False # Set to False to turn off verbosity

dlCache = dict()


################################CONSTANTS HERE#####################################
DEFAULT_EXTENSIONS_REGEX = '\.(jpg|png|gif|pdf)'
HTTP_HEAD_REGEX  = 'https?://'
URL_REGEX = '(%s[^\s"]+)'%(HTTP_HEAD_REGEX)
REPEAT_HTTP = "%s{2,}"%(HTTP_HEAD_REGEX)
END_NAME = "([^\/\s]+)$" #The text right after the last slash '/'

HTTP_DOMAIN = "http://"
HTTPS_DOMAIN = "https://"

regexCompile = lambda regex : re.compile(regex, re.IGNORECASE)

#Writes a message to a stream and flushes the stream
streamPrintFlush = lambda msg,stream=sys.stderr: msg and stream.write(msg) and stream.flush()

def getFiles(url, extCompile, recursionDepth=5, httpDomain=HTTPS_DOMAIN):
  #Args: url, extCompile=> A pattern object of the extension(s) to match
  #      recursionDepth => An integer that indicates how deep to scrap
  #                        Note: A negative recursion depth indicates that you want
  #                          to keep crawling as far as the program can go
  if not recursionDepth: return
  if not hasattr(extCompile, 'search'):
    streamPrintFlush(
     "Expecting a pattern object/result of re.compile(..) for arg 'extCompile'\n"
    , sys.stderr)
    return

  if not re.search(HTTP_HEAD_REGEX,url): 
    url = "%s%s"%(httpDomain, url)

  try:
    data = urlGetter.urlopen(url)  
    if pyVersion >= 3:decodedData = data.read().decode()
    else: decodedData = data.read()
    
  except Exception: pass
  else:
    urls = re.findall(URL_REGEX, decodedData, re.MULTILINE)
    urls = list(map(lambda s : re.sub(REPEAT_HTTP,HTTP_HEAD_REGEX,s), urls))

    matchedFileUrls = filter(lambda s : extCompile.search(s), urls)
    plainUrls = filter(lambda s : s not in matchedFileUrls, urls)

    #Time to download all the matched files 
    dlResults = map(lambda eachUrl: dlData(eachUrl), matchedFileUrls)
    resultsList = list(filter(lambda val: val, dlResults))

    #Report to user successful saves
    streamPrintFlush(
     "For url %s downloaded %d files\n"%(url, len(resultsList)), sys.stderr
    )

    recursionDepth -= 1
    for eachUrl in plainUrls:
      getFiles(eachUrl, extCompile, recursionDepth)

def dlData(url):
 #Args: A url
 #Download the data from the url and write it to memory
 #Returns: True iff the data was successfully written, else: False
 if not (url and re.search(HTTP_HEAD_REGEX,url)): return None

 # Let's check the cache first
 # Computing the url's hash
 
 urlStrHash = None
 try:
   bEncodedUrl = bytes(url, **encodingArgs)
   urlStrHash = md5(bEncodedUrl).hexdigest()
 except:
   streamPrintFlush("Cannot hash the provided URL")
   return None
   
 alreadyIn = dlCache.get(urlStrHash, None) 
 if alreadyIn:
   if DEBUG: streamPrintFlush("\033[32mAlready downloaded %s\033[00m\n"%(url))
   return None

 try: data = urlGetter.urlopen(url)
 except Exception: return False
 else:
   fileSearch = re.findall(END_NAME, url)
   if not fileSearch : return False
  
   fileName = fileSearch[0]
   streamPrintFlush("From url %s\n"%(url), sys.stderr)

   try:
     f = open(fileName,'wb')
     f.write(data.read())
     f.close()
   except: 
     streamPrintFlush("Failed to write %s to memory\n"%(fileName), sys.stderr) 
     return False
   else:
     streamPrintFlush("Wrote %s to memory\n"%(fileName), sys.stderr)
     
     # Let's now cache that url and mark it's content as already visited
     # where the urlString hash is the key and downloaded urls are the values
     markedContent = dlCache.get(urlStrHash, [])
     markedContent.append(url)
     dlCache[urlStrHash] = markedContent

     return True

def main():
  while True:
    try:
      streamPrintFlush(
        "\nTarget Url: eg [www.example.org or http://www.h.com] ", sys.stderr
      )
      lineIn = sys.stdin.readline()
      baseUrl = lineIn.strip("\n")

      streamPrintFlush(
       "Your extensions separated by '|' eg png|html: ", sys.stderr
      )

      lineIn = sys.stdin.readline()
      extensions = lineIn.strip("\n")
      
      streamPrintFlush(
        "\nRecursion Depth(a negative depth indicates you want script to go as far): "
      ,sys.stderr)
      lineIn = sys.stdin.readline()
      rDepth = int(lineIn.strip("\n"))

      if not extensions:
        extCompile = regexCompile(DEFAULT_EXTENSIONS_REGEX)
      else:
        extCompile = regexCompile(extensions)

    except ValueError:
      streamPrintFlush("Recursion depth must be an integer\n", sys.stderr)
    except KeyboardInterrupt:
      streamPrintFlush("Ctrl-C applied. Exiting now..\n",sys.stderr)
      break
    except Exception:
      continue
    else:
      if not baseUrl:
        continue

      if extCompile:
        getFiles(baseUrl, extCompile, rDepth)

  streamPrintFlush("Bye..\n",sys.stderr)
if __name__ == '__main__':
  main()
