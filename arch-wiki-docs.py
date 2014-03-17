#! /usr/bin/env python

import os
import sys
import re
import urllib.request

from simplemediawiki import MediaWiki

output_directory = "wiki"

query_allpages = {
    "action": "query",
    "list": "allpages",
    "aplimit": "500",
    "apfilterredir": "nonredirects",
    "apnamespace": "0",
    "prop": "info",
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

# matches all internal wiki links, will be replaced with local relative link
re_internal_links = re.compile("((?<=href=\")\\/index\\.php\\/)([^\\s#]+(?=[\"#]))")
# matches all local relative links except the 'File' namespace, these will be given '.html' extension
re_links_suffix = re.compile("(?<=href=\"\\.\\/)(?!File:)[^\\s#]+(?=[\"#])(?!\\.html)")
# matches links to images ('src' attribute of the <img> tags)
re_images_links = re.compile("((?<=src=\")\\/images\\/([\\S]+\\/)+)([^\\s#]+(?=\"))")

css_links = {
    "https://wiki.archlinux.org/load.php?debug=false&lang=en&modules=mediawiki.legacy.commonPrint%2Cshared%7Cskins.archlinux&only=styles&skin=archlinux&*": "ArchWikiOffline.css",
    "https://wiki.archlinux.org/skins/archlinux/IE60Fixes.css": "IE60Fixes.css",
    "https://wiki.archlinux.org/skins/archlinux/IE70Fixes.css": "IE70Fixes.css",
}

css_replace = {
    "https://wiki.archlinux.org/load.php?debug=false&amp;lang=en&amp;modules=mediawiki.legacy.commonPrint%2Cshared%7Cskins.archlinux&amp;only=styles&amp;skin=archlinux&amp;*": "ArchWikiOffline.css",
    "/skins/archlinux/IE60Fixes.css?303": "IE60Fixes.css",
    "/skins/archlinux/IE70Fixes.css?303": "IE70Fixes.css",
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

def sanitize_links(text):
    text = re.sub(re_internal_links, "./\\g<2>", text)
    text = re.sub(re_links_suffix, "\\g<0>.html", text)
    text = re.sub(re_images_links, "./File:\\g<3>", text)
    return text

def update_css_links(text, css_path):
    # 'css_path' is directory path of the CSS relative to the resulting HTML file
    for a, b in css_replace.items():
        text = text.replace(a, os.path.join(css_path, b))
    return text

def save_page(title, head, text, catlinks):
    # MediaWiki treats uses '_' in links instead of ' '
    title_linksafe = title.replace(" ", "_")

    # subpages need to be handled separately (especially the "/dev/shm" title anomally)
    if title_linksafe.startswith("/"):
        title_linksafe = title_linksafe[1:]
    subpage_parts = title_linksafe.split("/")
    directory = os.path.join(output_directory, *subpage_parts[:-1])

    try:
        os.makedirs(directory)
    except FileExistsError:
        pass

    f = open(os.path.join(output_directory, title_linksafe + ".html"), "w")

    # sanitize header for offline use (replace stylesheets, remove scripts)
    head = update_css_links(head, os.path.relpath(output_directory, directory))
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
        print(dest)
        urllib.request.urlretrieve(link, os.path.join(output_directory, dest))

def download_images():
    print("Downloading images...")
    query = query_allimages.copy()
    for images_snippet in query_continue(query):
        for image in images_snippet["allimages"]:
            title = image["title"]
            print(title)
            url = image["url"]
            urllib.request.urlretrieve(url, os.path.join(output_directory, title))
    

# ensure output directory always exists
if not os.path.exists(output_directory):
    os.mkdir(output_directory)


wiki = MediaWiki("https://wiki.archlinux.org/api.php")
print_namespaces()
for ns in ["0", "4", "12", "14"]:
    process_namespace(ns)

download_css()
download_images()
