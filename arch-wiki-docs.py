#! /usr/bin/env python3

import datetime
import argparse
import sys

from simplemediawiki import build_user_agent

import ArchWiki
from ArchWiki.ArchWiki import language_names
    
if __name__ == "__main__":
    aparser = argparse.ArgumentParser(description="Download pages from Arch Wiki and optimize them for offline browsing")
    aparser.add_argument("--output-directory", type=str, required=True, help="Path where the downloaded pages should be stored.")
    aparser.add_argument("--force", action="store_true", help="Ignore timestamp, always download the page from the wiki.")
    aparser.add_argument("--clean", action="store_true", help="Clean the output directory after downloading, useful for removing pages deleted/moved on the wiki. Warning: any unknown files found in the output directory will be deleted!")
    aparser.add_argument("--safe-filenames", action="store_true", help="Force using ASCII file names instead of the default Unicode.")
    aparser.add_argument("--langs", type=str, nargs='+', help="Download only pages of specified languages")
    aparser.add_argument("--list-langs", action="store_true", help="List supported languages")

    args = aparser.parse_args()
    if args.list_langs:
        for lang in language_names.values():
            print(lang['subtag'], lang['english'])
        sys.exit()

    if args.force:
        epoch = datetime.datetime.utcnow()
    else:
        # this should be the date of the latest incompatible change
        epoch = datetime.datetime(2016, 3, 3, 18, 0, 0)

    user_agent = build_user_agent(__file__, ArchWiki.__version__, ArchWiki.__url__)
    aw = ArchWiki.ArchWiki(user_agent=user_agent, safe_filenames=args.safe_filenames, langs=args.langs)
    optimizer = ArchWiki.Optimizer(aw, args.output_directory)

    downloader = ArchWiki.Downloader(aw, args.output_directory, epoch, optimizer=optimizer)
    downloader.download_css()
    aw.print_namespaces()
    for ns in ["0", "4", "12", "14"]:
        downloader.process_namespace(ns)

    downloader.download_images()

    if args.clean:
        downloader.clean_output_directory()
