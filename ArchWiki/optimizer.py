#! /usr/bin/env python

import os
import re
import lxml.etree
import lxml.html
import urllib.request
import urllib.parse

class Optimizer:
    def __init__(self, wiki, base_directory):
        """ @wiki:           ArchWiki instance to work with
            @base_directory: absolute path to base output directory, used for
                             computation of relative links
        """
        self.wiki = wiki
        self.base_directory = base_directory 

    def optimize_url(self, url, fout):
        """ @url: input url path
            @fout: output file path
        """
        self.optimize(urllib.request.urlopen(url), fout)

    def optimize(self, fin, fout):
        """ @fin: file name or file-like object with input data
            @fout: output file path
        """

        # path relative from the HTML file to base output directory
        self.relbase = os.path.relpath(self.base_directory, os.path.split(fout)[0])

        # parse HTML into element tree
        self.tree = lxml.html.parse(fin)
        self.root = self.tree.getroot()

        # optimize
        self.strip_page()
        self.fix_layout()
        self.replace_css_links()
        self.update_links()
        self.fix_footer()

        # ensure that target directory exists (necessary for subpages)
        try:
            os.makedirs(os.path.split(fout)[0])
        except FileExistsError:
            pass

        # write output
        f = open(fout, "w")
        f.write(lxml.etree.tostring(self.root,
                                    pretty_print=True,
                                    encoding="unicode",
                                    method="html",
                                    doctype="<!DOCTYPE html>"))
        f.close()

    def strip_page(self):
        """ remove elements useless in offline browsing
        """

        for e in self.root.cssselect("#archnavbar, #column-one, span.mw-editsection, #jump-to-nav, #siteSub"):
            e.getparent().remove(e)

        # strip comments (including IE 6/7 fixes, which are useless for an Arch package)
        lxml.etree.strip_elements(self.root, lxml.etree.Comment)

        # strip <script> tags
        lxml.etree.strip_elements(self.root, "script")

    def fix_layout(self):
        """ fix page layout after removing some elements
        """

        # in case of select-by-id a list with max one element is returned
        for gw in self.root.cssselect("#globalWrapper"):
            gw.set("style", "width: 100%")
        for c in self.root.cssselect("#content"):
            c.set("style", "margin: 2em; margin-bottom: 0")
        for fl in self.root.cssselect("#f-list"):
            fl.set("style", "margin: 0 2em")

    def replace_css_links(self):
        """ force using local CSS
        """

        links = self.root.xpath("//head/link[@rel=\"stylesheet\"]")

        # FIXME: pass css fille name as parameter
        # overwrite first
        links[0].set("href", os.path.join(self.relbase, "ArchWikiOffline.css"))
        
        # remove the rest
        for link in links[1:]:
            link.getparent().remove(link)

    def update_links(self):
        """ change "internal" wiki links into relative
        """

        for a in self.root.cssselect("a"):
            href = a.get("href")
            if href is not None:
                href = urllib.parse.unquote(href)
                match = re.match("^/index.php/(.+?)(#.+)?$", str(href))
                if match:
                    title = match.group(1)
                    fragment = match.group(2)
                    href = self.wiki.get_local_filename(title, self.relbase)
                    if fragment:
                        href += fragment
                    a.set("href", href)

        for i in self.root.cssselect("img"):
            src = i.get("src")
            if src and src.startswith("/images/"):
                src = os.path.join(self.relbase, "File:" + os.path.split(src)[1])
                i.set("src", src)

    def fix_footer(self):
        """ move content from 'div.printfooter' into item in '#f-list'
            (normally 'div.printfooter' is given 'display:none' and is separated by
            the categories list from the real footer)
        """

        for printfooter in self.root.cssselect("div.printfooter"):
            printfooter.attrib.pop("class")
            printfooter.tag = "li"
            f_list = self.root.cssselect("#f-list")[0]
            f_list.insert(0, printfooter)
            br = lxml.etree.Element("br")
            f_list.insert(3, br)
