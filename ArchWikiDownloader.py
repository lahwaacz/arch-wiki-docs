#! /usr/bin/env python

import os
import datetime
import urllib.request

from simplemediawiki import MediaWiki

from ArchWikiOptimizer import ArchWikiOptimizer

class ArchWikiDownloader:

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

    def __init__(self, wikiurl, output_directory, epoch):
        self.wiki = MediaWiki(wikiurl)
        self.output_directory = output_directory
        self.epoch = epoch

        # ensure output directory always exists
        if not os.path.isdir(self.output_directory):
            os.mkdir(self.output_directory)

    def query_continue(self, query):
        while True:
            result = self.wiki.call(query)
            if "error" in result:
                raise Exception(result["error"])
            if "warnings" in result:
                print(result["warnings"])
            if "query" in result:
                yield result["query"]
            if "continue" not in result:
                break
            query.update(result["continue"])

    def print_namespaces(self):
        nsmap = self.wiki.namespaces()
        nsmap[0] = "Main"   # force main namespace to have name instead of empty string
        print("Available namespaces:")
        for ns in sorted(nsmap.keys()):
            print("  %2d -- %s" % (ns, nsmap[ns]))

    def get_local_filename(self, title):
        """ return file name where the given page should be stored
        """

        # MediaWiki treats uses '_' in links instead of ' '
        title = title.replace(" ", "_")

        # handle anomalous titles beginning with '/' (e.g. "/dev/shm")
        if title.startswith("/"):
            title = title[1:]

        # pages from File namespace already have an extension
        if not title.startswith("File:"):
            title += ".html"

        return os.path.join(self.output_directory, title)

    def needs_update(self, title, timestamp):
        """ determine if it is necessary to download a page
        """

        fname = self.get_local_filename(title)
        if not os.path.exists(fname):
            return True
        local = datetime.datetime.utcfromtimestamp(os.path.getmtime(fname))
        if local < timestamp or local < self.epoch:
            return True
        return False

    def process_namespace(self, namespace):
        """ walk all pages in given namespace, download if necessary
        """

        print("Processing namespace %s..." % namespace)

        query = self.query_allpages.copy()
        query["gapnamespace"] = namespace
        for pages_snippet in self.query_continue(query):
            for page in pages_snippet["pages"].values():
                title = page["title"]
                timestamp = self.wiki.parse_date(page["touched"])
                if self.needs_update(title, timestamp):
                    print("  [downloading] %s" % title)
                    fullurl = page["fullurl"]

                    # FIXME: this is hack to avoid weird caching issues on ArchWiki
                    # it is probably useful anyway as it provides a permalink in #printfooter
                    fullurl += "?printable=yes"

                    html = urllib.request.urlopen(fullurl)
                    awoo = ArchWikiOptimizer(html, self.get_local_filename(title), self.output_directory)
                    awoo.optimize()
                else:
                    print("  [up-to-date]  %s" % title)

    def download_css(self):
        print("Downloading CSS...")
        for link, dest in self.css_links.items():
            print(" ", dest)
            urllib.request.urlretrieve(link, os.path.join(self.output_directory, dest))

    def download_images(self):
        print("Downloading images...")
        query = self.query_allimages.copy()
        for images_snippet in self.query_continue(query):
            for image in images_snippet["allimages"]:
                title = image["title"]
                timestamp = self.wiki.parse_date(image["timestamp"])
                if self.needs_update(title, timestamp):
                    print("  [downloading] %s" % title)
                    url = image["url"]
                    urllib.request.urlretrieve(url, os.path.join(self.output_directory, title))
                else:
                    print("  [up-to-date]  %s" % title)
