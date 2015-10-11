#!/usr/bin/env python3
# Author: Emmanuel Odeke <odeke@ualberta.ca>
# Sharded version of 'fileDownloader.py' except that it submits urls to a jobTable
# of which the urls will later be indexed accordingly

import sys

import utils
import RobotParser
from resty import restDriver
from routeUtils import WorkerDriver, Router

__LOCAL_CACHE = dict()

robotParser = RobotParser.RobotParser()
DEFAULT_TIMEOUT = 5 # Seconds

def extractFileUrls(url, extCompile, router, depth=5, httpDomain=utils.HTTPS_DOMAIN):
  # Args: url, extCompile=> A pattern object of the extension(s) to match
  #      depth => An integer that indicates how deep to scrap
  #                        Note: A negative recursion depth indicates that you want
  #                          to keep crawling as far as the program can go
  if not depth:
    return
  elif not restDriver.isCallableAttr(extCompile, 'search'):
    utils.streamPrintFlush(
     "Expecting a regex compiled object/result as arg 'extCompile'\n", sys.stderr
    )
    return

  if not utils.httpHeadCompile.search(url): 
    url = "%s%s"%(httpDomain, url)

  if not robotParser.canVisit(url):
    print('Cannot visit %s due to /robots.txt rules'%(url))
    return
  
  decodedData = utils.dlAndDecode(url)
  if not decodedData:
    return
  else:
    urls = utils.urlCompile.findall(decodedData)
    urls = [utils.repeatHttpHeadCompile.sub(utils.HTTP_HEAD_REGEX, s) for s in urls]

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

    uniqFileUrls = set(matchedFileUrls)
    dlResults = [pushUpJob(eachUrl, router, url) for eachUrl in uniqFileUrls]
    resultsList = [val for val in dlResults if val]

    depth -= 1
    for eachUrl in plainUrls:
      extractFileUrls(eachUrl, extCompile, router, depth)

def pushUpJob(url, router, parentUrl=''):
    # First query if this item was already seen by this worker
    if __LOCAL_CACHE.get(url, None) is not None:
        print('Already locally memoized as submitted to cloud', url)
    else:
        # Query if this file is already present 
        rDriver = router.getWorkerDriver(url)
        query = rDriver.restDriver.getJobs(message=url)
        if (hasattr(query, 'keys') and query.get('data', None) and len(query['data'])):
            print('Was submitted to the cloud by another crawler', url)
            __LOCAL_CACHE[url] = True
        else:
            saveResponse = rDriver.restDriver.newJob(
                message=url, assignedWorker_id=rDriver.getWorkerId(),
                metaData=parentUrl, author=rDriver.getDefaultAuthor()
            )

            if saveResponse.get('status_code', 400) == 200:
                print('Successfully submitted', url, 'to the cloud')
                __LOCAL_CACHE[url] = True

def readFromStream(stream=sys.stdin):
  try:
    lineIn = stream.readline()
  except:
    return None, None
  else:
    EOFState = (lineIn == "")
    return lineIn, EOFState

def main():
  args, options = restDriver.cliParser()

  # Route manager
  router = Router([
      'http://192.168.1.117:8000', 'http://192.168.1.110:8008', 'http://127.0.0.1:8009'
  ])
  while True:
    try:
      utils.streamPrintFlush(
        "\nTarget Url: eg [www.example.org or http://www.h.com] ", sys.stderr
      )
      lineIn, eofState = readFromStream()
      if eofState: break

      if lineIn:
        baseUrl = lineIn.strip("\n")

      else:
        continue

      utils.streamPrintFlush(
       "Your extensions separated by '|' eg png|html: ", sys.stderr
      )

      lineIn, eofState = readFromStream()
      if eofState: break
      extensions = lineIn.strip("\n")
      
      utils.streamPrintFlush(
        "\nRecursion Depth(a negative depth indicates you want script to go as far): ", sys.stderr
      )

      lineIn, eofState = readFromStream()
      if eofState: break

      elif lineIn:
        rDepth = int(lineIn.strip("\n") or 1)
      else:
        rDepth = 1

      formedRegex = utils.extensionify(extensions or utils.DEFAULT_EXTENSIONS_REGEX)
      extCompile = utils.regexCompile(formedRegex)

    except ValueError:
      utils.streamPrintFlush("Recursion depth must be an integer\n", sys.stderr)
    except KeyboardInterrupt:
      utils.streamPrintFlush("Ctrl-C applied. Exiting now..\n", sys.stderr)
      break
    except Exception:
      # TODO: [Informative exceptions]:
      #       + Handle traceback from sys somehow, since using Exception as e won't
      #         is invalid syntax for x <= Python2.5
      print('Generic exception encountered')
      continue
    else:
      if not baseUrl:
        continue

      if extCompile:
        extractFileUrls(baseUrl, extCompile, router, rDepth)

  utils.streamPrintFlush("Bye..\n",sys.stderr)

if __name__ == '__main__':
  try:
    main()
  except Exception: # See TODO: [Informative exceptions]
    sys.stderr.write('During processing, exception encountered.\nExiting now!\n')
