#!/usr/bin/python3
# 
# 1. Extrahiere alle interessanten Links nach <url>.links
# 2. Vergleiche diese Liste mit der Liste der bereits heruntergeladenen Links: urls.loaded.
# 3. Wenn neu: Herunterladen und in Datei der Links speichern.

import sys
import checkURL
import os
import glob
from time import gmtime, strftime
import re
import datetime
from pathlib import Path
import boto3, botocore
from boto3.dynamodb.conditions import Key, Attr


import new_downloads
import config
import getArticleThread

def download_webpage(url, targetfile):
    # Check if web page is available
    if not checkURL.checkURL(url) == 200:
        print (url + " is not reachable")
        sys.exit(504)
        return None
    else:
        # Download the web page
        print (url + " is reachable")
        checkURL.downloadall(url, targetfile)
        return targetfile
    
def safe_headline(tablename, runtime, url):
    table = boto3.resource('dynamodb').Table(tablename)
    response = table.put_item( Item={ 'article': url })

def already_downloaded(table, url):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table)
    results = table.query(KeyConditionExpression = Key('article').eq(url))
    print("Count of downloads: " + str(results["ScannedCount"]) + " for url: " + url)
    return results["ScannedCount"]

# Get all articles if not already downloaded
def get_articles(all_urls, runtime, storage, bucket, target):
#    print ("all_urls: " + str(all_urls))
    urlList = []
    tablename = 'news'
    for url in all_urls:
        if url != '':
            if not already_downloaded(tablename, url):
                print ("Get article for:  " + url)
                newArticleThread = getArticleThread.GetArticleThread(tablename, storage, runtime, url, bucket, target)
                newArticleThread.start()
                safe_headline(tablename, runtime, url)
                urlList.append(url)
    return urlList

# Get the list of interesting news of the main page 
def get_news(completepage, revalid, reinvalid, filename, runtime, storage, bucket, target):

    # 1. Get links of news 
    if completepage is not None:
    
        alllinks = []
        with open(completepage) as completepage_file:
            for line in completepage_file:
                isUrl =  revalid.match(line)
                if isUrl:
                    isvalidUrl = reinvalid.search(isUrl.group(1))
                    if not isvalidUrl:
                        alllinks.append(isUrl.group(1))
        completepage_file.close()
    
        # 2. Get the articles of the links
        urlList = get_articles(alllinks, runtime, storage, bucket, target)
    
    return urlList

#################### M A I N #################### 
def lambda_handler(event, context):
    # 1. Read configuration
    local_config = config.Config('./getnews.json')
    
    # 2. Initialize
    curdate = datetime.date.today().strftime('%Y') + '-' + datetime.date.today().strftime('%m') # Short time stamp as used in URL
    revalid = re.compile(eval(local_config.revalid))
    reinvalid = re.compile(eval(local_config.reinvalid))
    runtime = strftime("%Y.%m.%d_%H.%M.%S", gmtime())
    filename = local_config.storage + runtime
    if not os.path.exists(local_config.storage):
        os.makedirs(local_config.storage)

    account_no = boto3.client('sts').get_caller_identity().get('Account')
    bucket = local_config.target + '-' + account_no
    
    # 4. Get news page ...
    completepage = download_webpage(local_config.url, filename + ".actual")
    # 5. ... and news
    urlList = get_news(completepage, revalid, reinvalid, filename, runtime, local_config.storage, bucket, local_config.target)

    return urlList

