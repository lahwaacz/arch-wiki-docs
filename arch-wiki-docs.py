#! /usr/bin/env python

# TODO: categories browsing
# TODO: handle redirects (create symlinks?)
# TODO: write simple index.html (list available Main pages + Table of Contents)
# TODO: test parser options: preview, disablepp
# TODO: hide "[edit]" links next to headings

import os
import sys
import re
import urllib.request

from simplemediawiki import MediaWiki

output_directory = "wiki"

query_allpages = {
    "action": "query",
    "list": "allpages",
    "apfilterredir": "nonredirects",
    "apnamespace": "0",
    "prop": "info",
    "continue": "",
}
#query_allpages.update({"continue": "-||info", "apcontinue": "Applications"})

links_re = re.compile("((?<=href=\")\\/index\\.php\\/)([^\\s#]+(?=[\"#]))")

css_links = {
    "https://wiki.archlinux.org/load.php?debug=false&lang=en&modules=mediawiki.legacy.commonPrint%2Cshared%7Cskins.archlinux&only=styles&skin=archlinux&*": "ArchWikiOffline.css",
    "https://wiki.archlinux.org/skins/archlinux/IE60Fixes.css": "IE60Fixes.css",
    "https://wiki.archlinux.org/skins/archlinux/IE70Fixes.css": "IE70Fixes.css",
}

css_replace = {
    "https://wiki.archlinux.org/load.php?debug=false&amp;lang=en&amp;modules=mediawiki.legacy.commonPrint%2Cshared%7Cskins.archlinux&amp;only=styles&amp;skin=archlinux&amp;*": "./ArchWikiOffline.css",
    "/skins/archlinux/IE60Fixes.css?303": "./IE60Fixes.css",
    "/skins/archlinux/IE70Fixes.css?303": "./IE70Fixes.css",
}

def query_continue(query):
    while True:
        result = wiki.call(query)
        if 'error' in result:
            raise Exception(result['error'])
        if 'warnings' in result:
            print(result['warnings'])
        if 'query' in result:
            yield result['query']
        if 'continue' not in result:
            break
        query.update(result["continue"])

def get_namespaces_map():
    result = wiki.call({"action": "query", "meta": "siteinfo", "siprop": "namespaces"})
    if "error" in result:
        raise Exception(result["error"])
    if "warnings" in result:
        print(result["warnings"])
    return result["query"]["namespaces"]

def print_namespaces():
    nsmap = get_namespaces_map()
    print("Available namespaces:")
    for ns in sorted(nsmap.keys(), key=int):
        if "canonical" in nsmap[ns]:
            name = nsmap[ns]["canonical"]
        else:
            name = "Main"
        print("  %2d -- %s" % (int(nsmap[ns]["id"]), name))

def sanitize_links(text):
    return re.sub(links_re, "./\\g<2>.html", text)

def update_css_links(text):
    for a, b in css_replace.items():
        text = text.replace(a, b)
    return text

def save_page(title, head, text, catlinks):
    # subpages need to be handled separately (especially the "/dev/shm" title anomally)
    if title.startswith("/"):
        title = title[1:]
    subpage_parts = title.split("/")
    directory = os.path.join(output_directory, *subpage_parts[:-1])

    try:
        os.makedirs(directory)
    except FileExistsError:
        pass

    f = open(os.path.join(output_directory, title + ".html"), "w")

    # sanitize header for offline use (replace stylesheets, remove scripts)
    head = update_css_links(head)
    head = re.sub("^(.*)(https?://)(.*)$", "", head, flags=re.MULTILINE)
    f.write(head)

    # write div containers to "emulate" MediaWiki layout
    # this is necessary if we want to use the same CSS as upstream
    f.write("""<div id="globalWrapper" class="mw-body-primary" role="main" style="width: 100%%">
<div id="content" class="mw-body-primary" role="main" style="margin: 2em">
<a id="top"></a>
<h1 lang="en" class="firstHeading" id="firstHeading"><span dir="auto">%s</span></h1>""" % title)
    f.write("""<div id="bodyContent" class="mw-body">
<div id="siteSub">From ArchWiki</div>
<div id="contentSub"></div>
<div id="jump-to-nav" class="mw-jump">Jump to: <a href="#column-one">navigation</a>, <a href="#searchInput">search</a></div>
<div id="mw-content-text" class="mw-content-ltr">""")

    f.write(sanitize_links(text))

    # close <div id="mw-content-text">
    f.write("</div>")

    # write categories links
    f.write(sanitize_links(catlinks))

    # close divs, body, html
    for i in range(6):
        f.write("</div>\n")
    f.write("</body>\n</html>")

    f.close()

def process_namespace(namespace):
    print("Processing namespace %s..." % namespace)

    # TODO: categories cannot be handled the same as regular pages, because the wiki text is usually empty
    if namespace == "14":   # categories
        print("TODO: handling of categories is not done yet...")
        return

    query = query_allpages.copy()
    query["apnamespace"] = namespace
    for pages_snippet in query_continue(query):
        for page in pages_snippet["allpages"]:
            title = page["title"]
            print(title)
            pageid = page["pageid"]
            contents = wiki.call({"action": "parse", "pageid": pageid, "prop": "text|headhtml|categorieshtml|links"})
            head = contents["parse"]["headhtml"]["*"]
            links = contents["parse"]["links"]
            text = contents["parse"]["text"]["*"]
            catlinks = contents["parse"]["categorieshtml"]["*"]
            save_page(title, head, text, catlinks)

def download_css():
    print("Downloading CSS...")
    for link, dest in css_links.items():
        urllib.request.urlretrieve(link, os.path.join(output_directory, dest))
    

# ensure output directory always exists
if not os.path.exists(output_directory):
    os.mkdir(output_directory)

download_css()

wiki = MediaWiki('https://wiki.archlinux.org/api.php')
print_namespaces()
for ns in ["0", "4", "12", "14"]:
    process_namespace(ns)
