#!/usr/bin/python3
# Author: Emmanuel Odeke <odeke@ualberta.ca>
# Scrap any website for files with target extensions eg pdf, png, gif etc

import re
import os
import sys
import time

from resty import restDriver
from utils import streamPrintFlush, generateBadUrlReport, showStats

pyVersion = sys.hexversion/(1<<24)
if pyVersion >= 3:
  import urllib.request as urlGetter
  encodingArgs = dict(encoding='utf-8')
else:
  import urllib as urlGetter
  encodingArgs = dict()

############################# CONSTANTS HERE ##################################
extensionify = lambda extStr: '([^\s]+)\.(%s)'%(extStr)
DEFAULT_EXTENSIONS_REGEX = 'jpg|png|gif|pdf'
HTTP_HEAD_REGEX  = 'https?://'
URL_REGEX = '(%s[^\s"]+)'%(HTTP_HEAD_REGEX)
REPEAT_HTTP = "%s{2,}"%(HTTP_HEAD_REGEX)
END_NAME = "([^\/\s]+\.\w+)$" #The text right after the last slash '/'

HTTP_DOMAIN = "http://"
HTTPS_DOMAIN = "https://"

DEFAULT_TIMEOUT = 5 # Seconds
__LOCAL_CACHE = dict()

regexCompile = lambda regex : re.compile(regex, re.IGNORECASE|re.UNICODE)

def getFiles(
  url, extCompile, rDriver, recursionDepth=5, httpDomain=HTTPS_DOMAIN
):
  # Args: url, extCompile=> A pattern object of the extension(s) to match
  #      recursionDepth => An integer that indicates how deep to scrap
  #                        Note: A negative recursion depth indicates that you want
  #                          to keep crawling as far as the program can go
  if not recursionDepth: return
  if not hasattr(extCompile, 'search'):
    streamPrintFlush(
     "Expecting a pattern object/result of re.compile(..) for arg 'extCompile'\n"
    , sys.stderr)
    return

  if not re.search(HTTP_HEAD_REGEX, url): 
    url = "%s%s"%(httpDomain, url)
    print("URL ", url)

  try:
    data = urlGetter.urlopen(url)
    if pyVersion >= 3:decodedData = data.read().decode()
    else: decodedData = data.read()
    
  except Exception as e:
    print('exc', e)
  else:
    urls = re.findall(URL_REGEX, decodedData, re.MULTILINE)
    urls = list(map(lambda s : re.sub(REPEAT_HTTP,HTTP_HEAD_REGEX,s), urls))

    plainUrls = []
    matchedFileUrls = []

    for u in urls:
        pathSelector = plainUrls
        regSearch = extCompile.search(u)
        if regSearch:
            rGroup = regSearch.groups(1)
            u = '%s.%s'%(rGroup[0], rGroup[1])
            pathSelector = matchedFileUrls

        pathSelector.append(u)

    #Time to download all the matched files 
    dlResults = map(
       lambda eachUrl: pushUpJob(eachUrl, rDriver, url), set(matchedFileUrls)
    )
    resultsList = list(filter(lambda val: val, dlResults))

    recursionDepth -= 1
    for eachUrl in plainUrls:
      getFiles(eachUrl, extCompile, rDriver, recursionDepth)

class WorkerDriver:
    def __init__(self, ip, port):
        self.__workerId = -1
        self.getDefaultAuthor = restDriver.getDefaultAuthor 
        self.initRestDriver(ip, port)

        self.initWorker()

    def initRestDriver(self, ip, port):
        self.restDriver = restDriver.RestDriver(ip, port)

        wHandler = self.restDriver.registerLiason('Worker', '/jobTable/workerHandler')
        assert(wHandler)

        jHandler = self.restDriver.registerLiason('Job', '/jobTable/jobHandler')
        assert(jHandler)

    def getWorkerId(self):
        return self.__workerId

    def initWorker(self):
        qResponse = restDriver.produceAndParse(self.restDriver.getWorkers, purpose='Crawling', select='id', format='short')
        if qResponse.get('data', None):
            print('Present workers', qResponse)
            self.__workerId = qResponse['data'][0].get('id', -1)
        else:
            cResponse = restDriver.produceAndParse(self.restDriver.newWorker, purpose='Crawling')
            print('Created worker response', cResponse)
            self.__workerId = cResponse.get('data', [{'id', -1}]).get('id', -1)

        print('WorkerId', self.__workerId)

def pushUpJob(url, rDriver, parentUrl=''):
    # First query if this item was already seen by this worker
    if __LOCAL_CACHE.get(url, None) is None:

        # Query if this file is already present 
    
        query = restDriver.produceAndParse(rDriver.restDriver.getJobs, message=url)
        if not (hasattr(query, 'keys') and query.get('data', None) and len(query['data'])):
            saveResponse = rDriver.restDriver.newJob(
                message=url, assignedWorker_id=rDriver.getWorkerId(),
                metaData=parentUrl, author=rDriver.getDefaultAuthor()
            )

            if saveResponse.get('status_code', 400) == 200:
                print('Successfully submitted', url, 'to the cloud')
                __LOCAL_CACHE[url] = True
        else:
            print('Was submitted to the cloud by another crawler', url)
            __LOCAL_CACHE[url] = True

    else:
        print('Already locally memoized as submitted to cloud', url)

def readFromStream(stream=sys.stdin):
  try:
    lineIn = stream.readline()
  except:
    return None, None
  else:
    EOFState = (lineIn == "")
    return lineIn, EOFState

def main():
  wDriver = WorkerDriver('http://192.168.1.83', '8000')
  while True:
    try:
      streamPrintFlush(
        "\nTarget Url: eg [www.example.org or http://www.h.com] ", sys.stderr
      )
      lineIn, eofState = readFromStream()
      if eofState: break

      if lineIn:
        baseUrl = lineIn.strip("\n")

      else:
        continue

      streamPrintFlush(
       "Your extensions separated by '|' eg png|html: ", sys.stderr
      )

      lineIn, eofState = readFromStream()
      if eofState: break
      extensions = lineIn.strip("\n")
      
      streamPrintFlush(
        "\nRecursion Depth(a negative depth indicates you want script to go as far): ", sys.stderr
      )

      lineIn, eofState = readFromStream()
      if eofState: break

      elif lineIn:
        rDepth = int(lineIn.strip("\n") or 1)
      else:
        rDepth = 1

      formedRegex = extensionify(extensions or DEFAULT_EXTENSIONS_REGEX)

      extCompile = regexCompile(formedRegex)

    except ValueError as e:
      print('e', e)
      streamPrintFlush("Recursion depth must be an integer\n", sys.stderr)
    except KeyboardInterrupt:
      streamPrintFlush("Ctrl-C applied. Exiting now..\n",sys.stderr)
      break
    except Exception as e:
      print(e)
      continue
    else:
      if not baseUrl:
        continue

      if extCompile:
        getFiles(baseUrl, extCompile, wDriver, rDepth)

  streamPrintFlush("Bye..\n",sys.stderr)
if __name__ == '__main__':
  try:
    main()
  except Exception as e:
    print('e', e)
