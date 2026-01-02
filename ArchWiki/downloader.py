import os
import datetime

from ws.client.api import API

from .optimizer import Optimizer


class Downloader:
    css_links = {
        "https://wiki.archlinux.org/load.php?lang=en&modules=site.styles|skins.vector.icons,styles|zzz.ext.archLinux.styles&only=styles&skin=vector-2022": "ArchWikiOffline.css",
    }

    def __init__(
        self,
        api: API,
        output_directory: str,
        epoch: datetime.datetime,
        optimizer: Optimizer,
    ):
        """
        Parameters:
        @api:               API object for ArchWiki
        @output_directory:  where to store the downloaded files
        @epoch:             force update of every file older than this date (must be instance
                            of 'datetime')
        @optimizer:         Optimizer instance for HTML post-processing
        """

        self.api = api
        self.output_directory = output_directory
        self.epoch = epoch
        self.optimizer = optimizer

        # ensure output directory always exists
        if not os.path.isdir(self.output_directory):
            os.mkdir(self.output_directory)

        # list of valid files
        self.files = []

    def needs_update(self, fname: str, timestamp: datetime.datetime) -> bool:
        """
        Determine if it is necessary to download a page.
        """
        if not os.path.exists(fname):
            return True
        local = datetime.datetime.fromtimestamp(
            os.path.getmtime(fname), tz=datetime.UTC
        )
        if local < timestamp or local < self.epoch:
            return True
        return False

    def process_namespace(self, namespace: str) -> None:
        """
        Enumerate all pages in given namespace, download if necessary
        """
        print(f"Processing namespace {namespace}...")

        allpages = self.api.generator(
            generator="allpages",
            gaplimit="max",
            gapfilterredir="nonredirects",
            gapnamespace=namespace,
            prop="info",
            inprop="url",
        )
        for page in allpages:
            title = page["title"]
            fname = self.optimizer.get_local_filename(title, self.output_directory)
            if not fname:
                print(f"  [skipping] {title}")
                continue
            self.files.append(fname)
            timestamp = page["touched"]
            if self.needs_update(fname, timestamp):
                print(f"  [downloading] {title}")
                fullurl = page["fullurl"]

                r = self.api.session.get(fullurl)
                r.raise_for_status()
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

    def download_css(self) -> None:
        print("Downloading CSS...")
        for link, dest in self.css_links.items():
            print(" ", dest)
            fname = os.path.join(self.output_directory, dest)
            if fname:
                self.files.append(fname)
                r = self.api.session.get(link)
                r.raise_for_status()
                with open(fname, "w") as fd:
                    fd.write(r.text)

    def download_images(self) -> None:
        print("Downloading images...")
        allimages = self.api.list(
            list="allimages", ailimit="max", aiprop="url|timestamp"
        )
        for image in allimages:
            title = image["title"]
            fname = self.optimizer.get_local_filename(title, self.output_directory)
            if not fname:
                print(f"  [skipping] {title}")
                continue
            self.files.append(fname)
            timestamp = image["timestamp"]
            if self.needs_update(fname, timestamp):
                print(f"  [downloading] {title}")
                r = self.api.session.get(image["url"])
                r.raise_for_status()
                with open(fname, "wb") as fd:
                    fd.write(r.content)
            else:
                print(f"  [up-to-date]  {title}")

    def clean_output_directory(self) -> None:
        """
        Walk output_directory and delete all files not found on the wiki.
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
