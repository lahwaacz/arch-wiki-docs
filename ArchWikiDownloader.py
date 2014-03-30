#! /usr/bin/env python

import os
import datetime
import urllib.request

from simplemediawiki import MediaWiki

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

    def __init__(self, wikiurl, output_directory, epoch, cb_download=urllib.request.urlretrieve):
        """ Parameters:
            @wikiurl:       url of the wiki's api.php
            @output_directory:  where to store the downloaded files
            @epoch:         force update of every file older than this date (must be instance
                            of 'datetime')
            @cb_download:   callback function for the downloading itself
                            it must accept 2 parameters: url and (full) destination path
        """

        self.wiki = MediaWiki(wikiurl)
        self.output_directory = output_directory
        self.epoch = epoch
        self.cb_download = cb_download

        # ensure output directory always exists
        if not os.path.isdir(self.output_directory):
            os.mkdir(self.output_directory)

        # list of valid files
        self.files = []

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

    def needs_update(self, fname, timestamp):
        """ determine if it is necessary to download a page
        """

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
                fname = self.get_local_filename(title)
                self.files.append(fname)
                timestamp = self.wiki.parse_date(page["touched"])
                if self.needs_update(fname, timestamp):
                    print("  [downloading] %s" % title)
                    fullurl = page["fullurl"]

                    # FIXME: this is hack to avoid weird caching issues on ArchWiki
                    # it is probably useful anyway as it provides a permalink in #printfooter
                    fullurl += "?printable=yes"

                    self.cb_download(fullurl, fname)
                else:
                    print("  [up-to-date]  %s" % title)

    def download_css(self):
        print("Downloading CSS...")
        for link, dest in self.css_links.items():
            print(" ", dest)
            fname = os.path.join(self.output_directory, dest)
            self.files.append(fname)
            urllib.request.urlretrieve(link, fname)

    def download_images(self):
        print("Downloading images...")
        query = self.query_allimages.copy()
        for images_snippet in self.query_continue(query):
            for image in images_snippet["allimages"]:
                title = image["title"]
                fname = self.get_local_filename(title)
                self.files.append(fname)
                timestamp = self.wiki.parse_date(image["timestamp"])
                if self.needs_update(fname, timestamp):
                    print("  [downloading] %s" % title)
                    url = image["url"]
                    urllib.request.urlretrieve(url, fname)
                else:
                    print("  [up-to-date]  %s" % title)

    def clean_output_directory(self):
        """ Walk output_directory and delete all files not found on the wiki.
            Should be run _after_ downloading, otherwise all files will be deleted!
        """

        print("Deleting unwanted files (deleted/moved on the wiki)...")
        valid_files = self.files.copy()

        for path, dirs, files in os.walk(self.output_directory, topdown=False):
            # handle files
            for f in files:
                fpath = os.path.join(path, f)
                if fpath not in valid_files:
                    print("  [deleting]    %s" % fpath)
                    os.unlink(fpath)

            # remove empty directories
            if len(os.listdir(path)) == 0:
                print("  [deleting]    %s/" % path)
                os.rmdir(path)
