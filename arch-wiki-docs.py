#! /usr/bin/env python

import datetime
import argparse

from ArchWikiOptimizer import ArchWikiOptimizer
from ArchWikiDownloader import ArchWikiDownloader
    
if __name__ == "__main__":
    aparser = argparse.ArgumentParser(description="Download pages from Arch Wiki and optimize them for offline browsing")
    aparser.add_argument("--output-directory", type=str, required=True, help="where to store downloaded pages")
    aparser.add_argument("--force", action="store_true", help="ignore timestamp, always download the page from the wiki")

    args = aparser.parse_args()
    if args.force:
        epoch = datetime.datetime.utcnow()
    else:
        # this should be the date of the latest incompatible change
        epoch = datetime.datetime(2014, 3, 20)

    optimizer = ArchWikiOptimizer(args.output_directory)

    downloader = ArchWikiDownloader("https://wiki.archlinux.org/api.php", args.output_directory, epoch, cb_download=optimizer.optimize)
    downloader.print_namespaces()
    for ns in ["0", "4", "12", "14"]:
        downloader.process_namespace(ns)

    downloader.download_images()
    downloader.download_css()
