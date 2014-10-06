#! /usr/bin/env python

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
    "Български": {"subtag": "bg", "english": "Bulgarian"},
    "Català": {"subtag": "ca", "english": "Catalan"},
    "Česky": {"subtag": "cs", "english": "Czech"},
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
    "Indonesia": {"subtag": "id", "english": "Indonesian"},
    "Italiano": {"subtag": "it", "english": "Italian"},
    "日本語": {"subtag": "ja", "english": "Japanese"},
    "한국어": {"subtag": "ko", "english": "Korean"},
    "Lietuviškai": {"subtag": "lt", "english": "Lithuanian"},
    "Norsk Bokmål": {"subtag": "nb", "english": "Norwegian (Bokmål)"},
    "Nederlands": {"subtag": "nl", "english": "Dutch"},
    "Polski": {"subtag": "pl", "english": "Polish"},
    "Português": {"subtag": "pt", "english": "Portuguese"},
    "Română": {"subtag": "ro", "english": "Romanian"},
    "Русский": {"subtag": "ru", "english": "Russian"},
    "Slovenský": {"subtag": "sk", "english": "Slovak"},
    "Српски": {"subtag": "sr", "english": "Serbian"},
    "Svenska": {"subtag": "sv", "english": "Swedish"},
    "ไทย": {"subtag": "th", "english": "Thai"},
    "Türkçe": {"subtag": "tr", "english": "Turkish"},
    "Українська": {"subtag": "uk", "english": "Ukrainian"},
    "Tiếng Việt": {"subtag": "vi", "english": "Vietnamese"},
    "简体中文": {"subtag": "zh-CN", "english": "Chinese (Simplified)"},
    "正體中文": {"subtag": "zh-TW", "english": "Chinese (Traditional)"}
}
local_categories = [
    "العربية",
    "Български",
    "Català",
    "Česky",
    "Dansk",
    "Ελληνικά",
    "English",
    "Esperanto",
    "Español",
    "Suomi",
    "עברית",
    "Hrvatski",
    "Magyar",
    "Indonesia",
    "Italiano",
    "日本語",
    "한국어",
    "Lietuviškai",
    "Norsk Bokmål",
    "Nederlands",
    "Polski",
    "Português",
    "Русский",
    "Slovenský",
    "Српски",
    "ไทย",
    "Українська",
    "简体中文",
    "正體中文"
]
interlanguage_external = ["de", "fa", "fi", "fr", "ro", "sv", "tr"]
interlanguage_internal = ["ar", "bg", "cs", "da", "el", "en", "es", "he", "hr",
                          "hu", "id", "it", "ja", "ko", "lt", "nl", "pl", "pt",
                          "ru", "sk", "sr", "th", "uk", "zh-cn", "zh-tw"]

def is_ascii(text):
    try:
        text.encode("ascii")
        return True
    except:
        return False

class ArchWiki(MediaWiki):

    def __init__(self, safe_filenames=False, resolve_redirects=True, **kwargs):
        """ Parameters:
            @safe_filenames: force self.get_local_filename() to return ASCII string
            @resolve_redirects: whether to resolve redirects inside self.get_local_filename()
            + all keyword arguments of simplemediawiki.MediaWiki
        """
        super().__init__(url, **kwargs)

        self._safe_filenames = safe_filenames
        self._resolve_redirects = resolve_redirects
        self._namespaces = None
        self._redirects = None

    def query_continue(self, query):
        """ Generator for MediaWiki's query-continue feature.
            ref: https://www.mediawiki.org/wiki/API:Query#Continuing_queries
        """
        while True:
            result = self.call(query)
            if "error" in result:
                raise Exception(result["error"])
            if "warnings" in result:
                print(result["warnings"])
            if "query" in result:
                yield result["query"]
            if "continue" not in result:
                break
            query.update(result["continue"])

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

    def detect_language(self, title):
        """ Detect language of a given title.
        """
        pure_title = title
        detected_language = local_language
        match = re.match("^(.+?)([ _]\(([^\(]+)\))?$", title);
        if match:
            lang = match.group(3)
            if lang in language_names:
                detected_language = lang
                pure_title = match.group(1)
        return pure_title, detected_language

    def get_local_filename(self, title, basepath):
        """ Return file name where the given page should be stored, relative to 'basepath'.
        """
        if self._resolve_redirects is True:
            title = self.resolve_redirect(title)

        title, lang = self.detect_language(title)
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
            langsubtag=language_names[lang]["subtag"],
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
            "gapfilterredir": "redirects",
            "gapnamespace": "0",
            "continue": "",
        }
        namespaces = ["0", "4", "12"]

        self._redirects = []

        for ns in namespaces:
            query = query_allredirects.copy()
            query["gapnamespace"] = ns

            for pages_snippet in self.query_continue(query):
                pages_snippet = sorted(pages_snippet["pages"].values(), key=lambda d: d["title"])
                pageids = [str(page["pageid"]) for page in pages_snippet]
                print("  [fetching redirects] pages %s - %s" % (pages_snippet[0]["title"], pages_snippet[-1]["title"]))
                result = self.call({"action": "query", "redirects": "", "pageids": "|".join(pageids)})
                self._redirects.extend(result["query"]["redirects"])

    def redirects(self):
        if self._redirects is None:
            self._fetch_redirects()
        return self._redirects

    def resolve_redirect(self, title):
        """ Returns redirect target title, or given title if it is not redirect.
            The returned title will always contain spaces instead of underscores.
        """
        def target_title(r):
            if r.get("tofragment"):
                return "%s#%s" % (r.get("to"), r.get("tofragment"))
            return r.get("to")

        # the given title must match the format of titles used in self._redirects
        title = title.replace("_", " ")

        if self._redirects is None:
            self._fetch_redirects()

        try:
            res = next((item for item in self._redirects if item["from"] == title))
            return target_title(res)
        except StopIteration:
            return title
