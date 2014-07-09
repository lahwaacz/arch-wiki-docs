#! /usr/bin/env python

import os
import datetime
import urllib.request

class Downloader:
    query_allpages = {
        "action": "query",
        "generator": "allpages",
        "gaplimit": "max",
        "gapfilterredir": "nonredirects",
        "gapnamespace": "0",
        "prop": "info",
        "inprop": "url",
        "continue": "",
    }

    query_allimages = {
        "action": "query",
        "list": "allimages",
        "ailimit": "max",
        "aiprop": "url|timestamp",
        "aimaxsize": "10000",
        "continue": "",
    }

    css_links = {
        "https://wiki.archlinux.org/load.php?debug=false&lang=en&modules=mediawiki.legacy.commonPrint%2Cshared%7Cskins.archlinux&only=styles&skin=archlinux&*": "ArchWikiOffline.css",
    }

    def __init__(self, wiki, output_directory, epoch, cb_download=urllib.request.urlretrieve):
        """ Parameters:
            @wiki:          ArchWiki instance to work with
            @output_directory:  where to store the downloaded files
            @epoch:         force update of every file older than this date (must be instance
                            of 'datetime')
            @cb_download:   callback function for the downloading itself
                            it must accept 2 parameters: url and (full) destination path
        """

        self.wiki = wiki
        self.output_directory = output_directory
        self.epoch = epoch
        self.cb_download = cb_download

        # ensure output directory always exists
        if not os.path.isdir(self.output_directory):
            os.mkdir(self.output_directory)

        # list of valid files
        self.files = []

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
        for pages_snippet in self.wiki.query_continue(query):
            for page in sorted(pages_snippet["pages"].values(), key=lambda d: d["title"]):
                title = page["title"]
                fname = self.wiki.get_local_filename(title, self.output_directory)
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
        for images_snippet in self.wiki.query_continue(query):
            for image in images_snippet["allimages"]:
                title = image["title"]
                fname = self.wiki.get_local_filename(title, self.output_directory)
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
