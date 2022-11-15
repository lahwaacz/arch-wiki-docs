#! /usr/bin/env python3

""" Module extending generic MediaWiki interface with stuff specific to ArchWiki
    and some convenient generic methods.
"""

import os.path
import re
import hashlib

from simplemediawiki import MediaWiki

__all__ = ["ArchWiki"]

url = "https://wiki.archlinux.org/api.php"
local_language = "English"
language_names = {
    "العربية": {"subtag": "ar", "english": "Arabic"},
    "Bosanski": {"subtag": "bs", "english": "Bosnian"},
    "Български": {"subtag": "bg", "english": "Bulgarian"},
    "Català": {"subtag": "ca", "english": "Catalan"},
    "Čeština": {"subtag": "cs", "english": "Czech"},
    "Dansk": {"subtag": "da", "english": "Danish"},
    "Deutsch": {"subtag": "de", "english": "German"},
    "Ελληνικά": {"subtag": "el", "english": "Greek"},
    "English": {"subtag": "en", "english": "English"},
    "Esperanto": {"subtag": "eo", "english": "Esperanto"},
    "Español": {"subtag": "es", "english": "Spanish"},
    "فارسی": {"subtag": "fa", "english": "Persian"},
    "Suomi": {"subtag": "fi", "english": "Finnish"},
    "Français": {"subtag": "fr", "english": "French"},
    "עברית": {"subtag": "he", "english": "Hebrew"},
    "Hrvatski": {"subtag": "hr", "english": "Croatian"},
    "Magyar": {"subtag": "hu", "english": "Hungarian"},
    "Bahasa Indonesia": {"subtag": "id", "english": "Indonesian"},
    "Italiano": {"subtag": "it", "english": "Italian"},
    "日本語": {"subtag": "ja", "english": "Japanese"},
    "한국어": {"subtag": "ko", "english": "Korean"},
    "Lietuvių": {"subtag": "lt", "english": "Lithuanian"},
    "Norsk Bokmål": {"subtag": "nb", "english": "Norwegian (Bokmål)"},
    "Nederlands": {"subtag": "nl", "english": "Dutch"},
    "Polski": {"subtag": "pl", "english": "Polish"},
    "Português": {"subtag": "pt", "english": "Portuguese"},
    "Română": {"subtag": "ro", "english": "Romanian"},
    "Русский": {"subtag": "ru", "english": "Russian"},
    "Slovenčina": {"subtag": "sk", "english": "Slovak"},
    "Српски": {"subtag": "sr", "english": "Serbian"},
    "Svenska": {"subtag": "sv", "english": "Swedish"},
    "ไทย": {"subtag": "th", "english": "Thai"},
    "Türkçe": {"subtag": "tr", "english": "Turkish"},
    "Українська": {"subtag": "uk", "english": "Ukrainian"},
    "Tiếng Việt": {"subtag": "vi", "english": "Vietnamese"},
    "粵語": {"subtag": "yue", "english": "Cantonese"},
    "简体中文": {"subtag": "zh-hans", "english": "Chinese (Simplified)"},
    "正體中文": {"subtag": "zh-hant", "english": "Chinese (Traditional)"}
}
interlanguage_external = ["de", "fa", "ja", "sv"]
interlanguage_internal = ["ar", "bs", "bg", "cs", "da", "el", "en", "es", "fi", "fr",
                          "he", "hr", "hu", "id", "it", "ko", "lt", "nl", "pl", "pt",
                          "ru", "sk", "sr", "th", "tr", "uk", "zh-hans", "zh-hant"]

def is_ascii(text):
    try:
        text.encode("ascii")
        return True
    except:
        return False

class ArchWiki(MediaWiki):

    def __init__(self, safe_filenames=False, langs=None, **kwargs):
        """ Parameters:
            @safe_filenames: force self.get_local_filename() to return ASCII string
            + all keyword arguments of simplemediawiki.MediaWiki
        """
        super().__init__(url, **kwargs)

        self._safe_filenames = safe_filenames
        self._namespaces = None
        self._redirects = None

        if langs is not None:
            self._language_names = {}
            for lang, metadata in language_names.items():
                if not set(metadata.values()).isdisjoint(langs):
                    self._language_names[lang] = metadata
        else:
            self._language_names = language_names

    def query_continue(self, query):
        """ Generator for MediaWiki's query-continue feature.
            ref: https://www.mediawiki.org/wiki/API:Query#Continuing_queries
        """
        last_continue = {"continue": ""}

        while True:
            # clone the original params to clean up old continue params
            query_copy = query.copy()
            # and update with the last continue -- it may involve multiple params,
            # hence the clean up with params.copy()
            query_copy.update(last_continue)
            # call the API and handle the result
            result = self.call(query_copy)
            if "error" in result:
                raise Exception(result["error"])
            if "warnings" in result:
                print(result["warnings"])
            if "query" in result:
                yield result["query"]
            if "continue" not in result:
                break
            last_continue = result["continue"]

    def namespaces(self):
        """ Force the Main namespace to have name instead of empty string.
        """
        if self._namespaces is None:
            self._namespaces = super().namespaces()
            self._namespaces[0] = "Main"
        return self._namespaces

    def print_namespaces(self):
        nsmap = self.namespaces()
        print("Available namespaces:")
        for ns in sorted(nsmap.keys()):
            print("  %2d -- %s" % (ns, nsmap[ns]))

    def detect_namespace(self, title, safe=True):
        """ Detect namespace of a given title.
        """
        pure_title = title
        detected_namespace = self.namespaces()[0]
        match = re.match("^((.+):)?(.+)$", title)
        ns = match.group(2)
        if ns:
            ns = ns.replace("_", " ")
            if ns in self.namespaces().values():
                detected_namespace = ns
                pure_title = match.group(3)
        return pure_title, detected_namespace

    def detect_language(self, title, *, strip_all_subpage_parts=True):
        """
        Detect language of a given title. The matching is case-sensitive and spaces are
        treated the same way as underscores.

        :param title: page title to work with
        :returns: a ``(pure, lang)`` tuple, where ``pure`` is the pure page title without
            the language suffix and ``lang`` is the detected language in long, localized form
        """
        title_regex = r"(?P<pure>.*?)[ _]\((?P<lang>[^\(\)]+)\)"
        pure_suffix = ""
        # matches "Page name/Subpage (Language)"
        match = re.fullmatch(title_regex, title)
        # matches "Page name (Language)/Subpage"
        if not match and "/" in title:
            base, pure_suffix = title.split("/", maxsplit=1)
            pure_suffix = "/" + pure_suffix
            match = re.fullmatch(title_regex, base)
        # matches "Category:Language"
        if not match:
            match = re.fullmatch(r"(?P<pure>[Cc]ategory[ _]?\:[ _]?(?P<lang>[^\(\)]+))", title)
        if match:
            pure = match.group("pure")
            lang = match.group("lang")
            if lang in self._language_names:
                # strip "(Language)" from all subpage components to handle cases like
                # "Page name (Language)/Subpage (Language)"
                if strip_all_subpage_parts is True and "/" in pure:
                    parts = pure.split("/")
                    new_parts = []
                    for p in parts:
                        match = re.fullmatch(title_regex, p)
                        if match:
                            part_lang = match.group("lang")
                            if part_lang == lang:
                                new_parts.append(match.group("pure"))
                            else:
                                new_parts.append(p)
                        else:
                            new_parts.append(p)
                    pure = "/".join(new_parts)
                return pure + pure_suffix, lang
        return title, local_language

    def get_local_filename(self, title, basepath):
        """ Return file name where the given page should be stored, relative to 'basepath'.
        """
        title, lang = self.detect_language(title)

        if lang is None:
            return None

        title, namespace = self.detect_namespace(title)

        # be safe and use '_' instead of ' ' in filenames (MediaWiki style)
        title = title.replace(" ", "_")
        namespace = namespace.replace(" ", "_")

        # force ASCII filename
        if self._safe_filenames and not is_ascii(title):
            h = hashlib.md5()
            h.update(title.encode("utf-8"))
            title = h.hexdigest()

        # select pattern per namespace
        if namespace == "Main":
            pattern = "{base}/{langsubtag}/{title}.{ext}"
        elif namespace in ["Talk", "ArchWiki", "ArchWiki_talk", "Template", "Template_talk", "Help", "Help_talk", "Category", "Category_talk"]:
            pattern = "{base}/{langsubtag}/{namespace}:{title}.{ext}"
        elif namespace == "File":
            pattern = "{base}/{namespace}:{title}"
        else:
            pattern = "{base}/{namespace}:{title}.{ext}"

        path = pattern.format(
            base=basepath,
            langsubtag=self._language_names[lang]["subtag"],
            namespace=namespace,
            title=title,
            ext="html"
        )
        return os.path.normpath(path)

    def _fetch_redirects(self):
        """ Fetch dictionary of redirect pages and their targets
        """
        query_allredirects = {
            "action": "query",
            "generator": "allpages",
            "gaplimit": "max",
            "gapfilterredir": "nonredirects",
            "prop": "redirects",
            "rdprop": "title|fragment",
            "rdlimit": "max",
        }
        namespaces = ["0", "4", "12", "14"]

        self._redirects = {}

        for ns in namespaces:
            query_allredirects["gapnamespace"] = ns

            for pages_snippet in self.query_continue(query_allredirects):
                pages_snippet = sorted(pages_snippet["pages"].values(), key=lambda d: d["title"])
                for page in pages_snippet:
                    # construct the mapping, the query result is somewhat reversed...
                    target_title = page["title"]
                    for redirect in page.get("redirects", []):
                        source_title = redirect["title"]
                        target_fragment = redirect.get("fragment")
                        if target_fragment:
                            self._redirects[source_title] = "{}#{}".format(target_title, target_fragment)
                        else:
                            self._redirects[source_title] = target_title

    def redirects(self):
        if self._redirects is None:
            self._fetch_redirects()
        return self._redirects

    def resolve_redirect(self, title):
        """ Returns redirect target title, or given title if it is not redirect.
            The returned title will always contain spaces instead of underscores.
        """
        # the given title must match the format of titles used in self._redirects
        title = title.replace("_", " ")

        return self.redirects().get(title, title)
