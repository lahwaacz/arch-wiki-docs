#! /usr/bin/env python

import os
import sys
import re
import urllib.request
import datetime

from simplemediawiki import MediaWiki

from ArchWikiOfflineOptimizer import ArchWikiOfflineOptimizer

output_directory = "wiki"

query_allpages = {
    "action": "query",
    "generator": "allpages",
    "gaplimit": "500",
    "gapfilterredir": "nonredirects",
    "gapnamespace": "0",
    "prop": "info",
    "inprop": "url",
    "continue": "",
}
#query_allpages.update({"continue": "-||info", "apcontinue": "Applications"})

query_allimages = {
    "action": "query",
    "list": "allimages",
    "ailimit": "500",
    "aiprop": "url|timestamp",
    "aimaxsize": "10000",
    "continue": "",
}

css_links = {
    "https://wiki.archlinux.org/load.php?debug=false&lang=en&modules=mediawiki.legacy.commonPrint%2Cshared%7Cskins.archlinux&only=styles&skin=archlinux&*": "ArchWikiOffline.css",
}

def query_continue(query):
    while True:
        result = wiki.call(query)
        if "error" in result:
            raise Exception(result["error"])
        if "warnings" in result:
            print(result["warnings"])
        if "query" in result:
            yield result["query"]
        if "continue" not in result:
            break
        query.update(result["continue"])

def print_namespaces():
    nsmap = wiki.namespaces()
    nsmap[0] = "Main"   # force main namespace to have name instead of empty string
    print("Available namespaces:")
    for ns in sorted(nsmap.keys()):
        print("  %2d -- %s" % (ns, nsmap[ns]))

# return file name where the given page should be stored
def get_local_filename(title):
    # MediaWiki treats uses '_' in links instead of ' '
    title = title.replace(" ", "_")

    # handle anomalous titles beginning with '/' (e.g. "/dev/shm")
    if title.startswith("/"):
        title = title[1:]

    # pages from File namespace already have an extension
    if not title.startswith("File:"):
        title += ".html"

    return os.path.join(output_directory, title)

# determine if it is necessary to download a page
# TODO: handle incompatible updates to this script
def needs_update(title, timestamp):
    fname = get_local_filename(title)
    if not os.path.exists(fname):
        return True
    local = datetime.datetime.fromtimestamp(os.path.getmtime(fname))
    if local < timestamp:
        return True
    return False

def process_namespace(namespace):
    print("Processing namespace %s..." % namespace)

    query = query_allpages.copy()
    query["gapnamespace"] = namespace
    for pages_snippet in query_continue(query):
        for page in pages_snippet["pages"].values():
            title = page["title"]
            timestamp = wiki.parse_date(page["touched"])
            if needs_update(title, timestamp):
                print("  [downloading] %s" % title)
                fullurl = page["fullurl"]

                # FIXME: this is hack to avoid weird caching issues on ArchWiki
                fullurl += "?printable=yes"

                html = urllib.request.urlopen(fullurl)
                awoo = ArchWikiOfflineOptimizer(html, get_local_filename(title), output_directory)
                awoo.optimize()
            else:
                print("  [up-to-date]  %s" % title)

def download_css():
    print("Downloading CSS...")
    for link, dest in css_links.items():
        print(" ", dest)
        urllib.request.urlretrieve(link, os.path.join(output_directory, dest))

def download_images():
    print("Downloading images...")
    query = query_allimages.copy()
    for images_snippet in query_continue(query):
        for image in images_snippet["allimages"]:
            title = image["title"]
            timestamp = wiki.parse_date(image["timestamp"])
            if needs_update(title, timestamp):
                print("  [downloading] %s" % title)
                url = image["url"]
                urllib.request.urlretrieve(url, os.path.join(output_directory, title))
            else:
                print("  [up-to-date]  %s" % title)
    

# ensure output directory always exists
if not os.path.exists(output_directory):
    os.mkdir(output_directory)


wiki = MediaWiki("https://wiki.archlinux.org/api.php")
print_namespaces()
for ns in ["0", "4", "12", "14"]:
    process_namespace(ns)

download_images()
download_css()
