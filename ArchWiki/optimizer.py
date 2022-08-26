#! /usr/bin/env python3

import os
import re
import lxml.etree
import lxml.html
import urllib.parse

class Optimizer:
    def __init__(self, wiki, base_directory):
        """ @wiki:           ArchWiki instance to work with
            @base_directory: absolute path to base output directory, used for
                             computation of relative links
        """
        self.wiki = wiki
        self.base_directory = base_directory

    def optimize(self, title, html_content):
        # path relative from the HTML file to base output directory
        relbase = os.path.relpath(self.base_directory, os.path.dirname(title))

        css_path = os.path.join(relbase, "ArchWikiOffline.css")

        # parse the HTML
        root = lxml.html.document_fromstring(html_content)

        # optimize
        self.strip_page(root)
        self.fix_layout(root)
        self.replace_css_links(root, css_path)
        self.update_links(root, relbase)
        self.fix_footer(root)

        # return output
        return lxml.etree.tostring(root,
                                   pretty_print=True,
                                   encoding="unicode",
                                   method="html",
                                   doctype="<!DOCTYPE html>")

    def strip_page(self, root):
        """ remove elements useless in offline browsing
        """

        for e in root.cssselect("#archnavbar, #mw-page-base, #mw-head-base, #mw-navigation"):
            e.getparent().remove(e)

        # strip comments (including IE 6/7 fixes, which are useless for an Arch package)
        lxml.etree.strip_elements(root, lxml.etree.Comment)

        # strip <script> tags
        lxml.etree.strip_elements(root, "script")
        
        # strip <header> tags
        lxml.etree.strip_elements(root, "header")

    def fix_layout(self, root):
        """ fix page layout after removing some elements
        """

        # in case of select-by-id a list with max one element is returned
        for c in root.cssselect("#content"):
            c.set("style", "margin: 0")
        for f in root.cssselect("#footer"):
            f.set("style", "margin: 0")

    def replace_css_links(self, root, css_path):
        """ force using local CSS
        """

        links = root.xpath("//head/link[@rel=\"stylesheet\"]")

        # overwrite first
        links[0].set("href", css_path)

        # remove the rest
        for link in links[1:]:
            link.getparent().remove(link)

    def update_links(self, root, relbase):
        """ change "internal" wiki links into relative
        """

        for a in root.cssselect("a"):
            href = a.get("href")
            if href is not None:
                href = urllib.parse.unquote(href)
                match = re.match("^/title/(.+?)(?:#(.+))?$", str(href))
                if match:
                    title = self.wiki.resolve_redirect(match.group(1))
                    try:
                        title, fragment = title.split("#", maxsplit=1)
                        # FIXME has to be dot-encoded
                        fragment = fragment.replace(" ", "_")
                    except ValueError:
                        fragment = ""
                    # explicit fragment overrides the redirect
                    if match.group(2):
                        fragment = match.group(2)
                    href = self.wiki.get_local_filename(title, relbase)
                    if fragment:
                        href += "#" + fragment
                    a.set("href", href)

        for i in root.cssselect("img"):
            src = i.get("src")
            if src and src.startswith("/images/"):
                src = os.path.join(relbase, "File:" + os.path.split(src)[1])
                i.set("src", src)

    def fix_footer(self, root):
        """ move content from 'div.printfooter' into item in '#footer-info'
            (normally 'div.printfooter' is given 'display:none' and is separated by
            the categories list from the real footer)
        """

        for printfooter in root.cssselect("div.printfooter"):
            printfooter.attrib.pop("class")
            printfooter.tag = "li"
            f_list = root.cssselect("#footer-info")[0]
            f_list.insert(0, printfooter)
            br = lxml.etree.Element("br")
            f_list.insert(3, br)
