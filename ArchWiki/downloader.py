#! /usr/bin/env python3

import os
import datetime

import requests
from requests.packages.urllib3.util.retry import Retry

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
        "https://wiki.archlinux.org/load.php?debug=false&lang=en&modules=mediawiki.legacy.commonPrint,shared|mediawiki.sectionAnchor|mediawiki.skinning.interface|skins.vector.styles|skins.vector.styles.responsive|zzz.ext.archLinux.styles&only=styles&skin=vector": "ArchWikiOffline.css",
    }

    def __init__(self, wiki, output_directory, epoch, *, optimizer=None):
        """ Parameters:
            @wiki:          ArchWiki instance to work with
            @output_directory:  where to store the downloaded files
            @epoch:         force update of every file older than this date (must be instance
                            of 'datetime')
            @optimizer:     callback function for HTML post-processing
        """

        self.wiki = wiki
        self.output_directory = output_directory
        self.epoch = epoch
        self.optimizer = optimizer

        # ensure output directory always exists
        if not os.path.isdir(self.output_directory):
            os.mkdir(self.output_directory)

        # list of valid files
        self.files = []

        self.session = requests.Session()
        # granular control over requests' retries: https://stackoverflow.com/a/35504626
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

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

        print(f"Processing namespace {namespace}...")

        query = self.query_allpages.copy()
        query["gapnamespace"] = namespace
        for pages_snippet in self.wiki.query_continue(query):
            for page in sorted(pages_snippet["pages"].values(), key=lambda d: d["title"]):
                title = page["title"]
                fname = self.wiki.get_local_filename(title, self.output_directory)
                if not fname:
                    print(f"  [skipping] {title}")
                    continue
                self.files.append(fname)
                timestamp = self.wiki.parse_date(page["touched"])
                if self.needs_update(fname, timestamp):
                    print(f"  [downloading] {title}")
                    fullurl = page["fullurl"]

                    r = self.session.get(fullurl)
                    if self.optimizer is not None:
                        text = self.optimizer.optimize(fname, r.text)
                    else:
                        text = r.text

                    # ensure that target directory exists (necessary for subpages)
                    os.makedirs(os.path.dirname(fname), exist_ok=True)

                    with open(fname, "w") as fd:
                        fd.write(text)
                else:
                    print(f"  [up-to-date]  {title}")

    def download_css(self):
        print("Downloading CSS...")
        for link, dest in self.css_links.items():
            print(" ", dest)
            fname = os.path.join(self.output_directory, dest)
            if fname:
                self.files.append(fname)
                r = self.session.get(link)
                with open(fname, "w") as fd:
                    fd.write(r.text)

    def download_images(self):
        print("Downloading images...")
        query = self.query_allimages.copy()
        for images_snippet in self.wiki.query_continue(query):
            for image in images_snippet["allimages"]:
                title = image["title"]
                fname = self.wiki.get_local_filename(title, self.output_directory)
                if not fname:
                    print(f"  [skipping] {title}")
                    continue
                self.files.append(fname)
                timestamp = self.wiki.parse_date(image["timestamp"])
                if self.needs_update(fname, timestamp):
                    print(f"  [downloading] {title}")
                    r = self.session.get(image["url"])
                    with open(fname, "wb") as fd:
                        fd.write(r.content)
                else:
                    print(f"  [up-to-date]  {title}")

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
                    print(f"  [deleting]    {fpath}")
                    os.unlink(fpath)

            # remove empty directories
            if len(os.listdir(path)) == 0:
                print(f"  [deleting]    {path}/")
                os.rmdir(path)
