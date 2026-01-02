import hashlib
import os
import re
import urllib.parse

import lxml.etree
import lxml.html
import ws.ArchWiki.lang
from ws.client.api import API


class Optimizer:
    def __init__(
        self,
        api: API,
        base_directory: str,
        safe_filenames: bool = False,
        langs: list[str] | None = None,
    ):
        """
        @api:            API object for ArchWiki
        @base_directory: absolute path to base output directory, used for
                         computation of relative links
        @safe_filenames: force self.get_local_filename() to return ASCII string
        @langs:          language tags for filtering
        """
        self.api = api
        self.base_directory = base_directory
        self.safe_filenames = safe_filenames
        self.langs = langs or ws.ArchWiki.lang.get_language_tags()

    def get_local_filename(self, title: str, basepath: str) -> str | None:
        """Return file name where the given page should be stored, relative to 'basepath'."""
        title, lang = ws.ArchWiki.lang.detect_language(title)
        langsubtag = ws.ArchWiki.lang.tag_for_langname(lang)

        if langsubtag not in self.langs:
            return None

        _title = self.api.Title(title)

        # be safe and use '_' instead of ' ' in filenames (MediaWiki style)
        title = _title.pagename.replace(" ", "_")
        namespace = _title.namespace.replace(" ", "_")

        # force ASCII filename
        if self.safe_filenames and not title.isascii():
            h = hashlib.md5()
            h.update(title.encode("utf-8"))
            title = h.hexdigest()

        # select pattern per namespace
        if namespace == "":
            pattern = "{base}/{langsubtag}/{title}.{ext}"
        elif namespace in [
            "Talk",
            "ArchWiki",
            "ArchWiki_talk",
            "Template",
            "Template_talk",
            "Help",
            "Help_talk",
            "Category",
            "Category_talk",
        ]:
            pattern = "{base}/{langsubtag}/{namespace}:{title}.{ext}"
        elif namespace == "File":
            pattern = "{base}/{namespace}:{title}"
        else:
            pattern = "{base}/{namespace}:{title}.{ext}"

        path = pattern.format(
            base=basepath,
            langsubtag=langsubtag,
            namespace=namespace,
            title=title,
            ext="html",
        )
        return os.path.normpath(path)

    def optimize(self, title: str, html_content: str) -> str:
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
        return lxml.etree.tostring(
            root,
            pretty_print=True,
            encoding="unicode",
            method="html",
            doctype="<!DOCTYPE html>",
        )

    def strip_page(self, root):
        """remove elements useless in offline browsing"""

        for e in root.cssselect(
            "#archnavbar, #mw-navigation, header.mw-header, .vector-sitenotice-container, .vector-page-toolbar, #p-lang-btn"
        ):
            e.getparent().remove(e)

        # strip comments (including IE 6/7 fixes, which are useless for an Arch package)
        lxml.etree.strip_elements(root, lxml.etree.Comment)

        # strip <script> tags
        lxml.etree.strip_elements(root, "script")

    def fix_layout(self, root):
        """fix page layout after removing some elements"""

        # in case of select-by-id a list with max one element is returned
        for c in root.cssselect("#content"):
            c.set("style", "margin: 0")
        for f in root.cssselect("#footer"):
            f.set("style", "margin: 0")

    def replace_css_links(self, root, css_path):
        """force using local CSS"""

        links = root.xpath('//head/link[@rel="stylesheet"]')

        # overwrite first
        links[0].set("href", css_path)

        # remove the rest
        for link in links[1:]:
            link.getparent().remove(link)

    def update_links(self, root, relbase):
        """change "internal" wiki links into relative"""

        for a in root.cssselect("a"):
            href = a.get("href")
            if href is not None:
                href = urllib.parse.unquote(href)
                # matching full URL is necessary for interlanguage links
                match = re.match(
                    "^(https://wiki.archlinux.org)?/title/(?P<title>.+?)(?:#(?P<fragment>.+))?$",
                    str(href),
                )
                if match:
                    title = self.api.redirects.resolve(match.group("title"))
                    if title is None:
                        title = match.group("title")
                    try:
                        title, fragment = title.split("#", maxsplit=1)
                        # FIXME has to be dot-encoded
                        fragment = fragment.replace(" ", "_")
                    except ValueError:
                        fragment = ""
                    # explicit fragment overrides the redirect
                    if match.group("fragment"):
                        fragment = match.group("fragment")
                    href = self.get_local_filename(title, relbase)
                    # get_local_filename returns None for skipped pages
                    if href is None:
                        continue
                    if fragment:
                        href += "#" + fragment
                    a.set("href", href)

        for i in root.cssselect("img"):
            src = i.get("src")
            if src and src.startswith("/images/"):
                src = os.path.join(relbase, "File:" + os.path.split(src)[1])
                i.set("src", src)

    def fix_footer(self, root):
        """
        Move content from 'div.printfooter' into item in '#footer-info'

        (Normally 'div.printfooter' is given 'display:none' and is separated by
        the categories list from the real footer.)
        """

        for printfooter in root.cssselect("div.printfooter"):
            printfooter.attrib.pop("class")
            printfooter.tag = "li"
            f_list = root.cssselect("#footer-info")[0]
            f_list.insert(0, printfooter)
            br = lxml.etree.Element("br")
            f_list.insert(3, br)
