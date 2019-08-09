#! /usr/bin/env python3

import os
import subprocess

# for filter_pre
import lxml.etree
import lxml.html

# for filter_in
import json
import pandocfilters

class PandocError(Exception):
    def __init__(self, retcode, errs):
        Exception.__init__(self, "pandoc failed with return code %s\nstderr:\n%s" % (retcode, errs))

class ManFilter:
    format = "man"

    def filter_pre(self, instring):
        root = lxml.html.fromstring(instring)

        # force headers to start from level 1
        content = root.cssselect("#bodyContent")[0]
        headers = content.cssselect("h1, h2, h3, h4, h5, h6")
        if len(headers) > 0:
            top_level = int(headers[0].tag[-1])
            for h in headers:
                level = int(h.tag[-1]) - top_level + 1
                h.tag = "h%d" % max(level, 1)

        # add some headers to distinguish divs in output formats like man
        for catlinks in root.cssselect("#catlinks"):
            h = lxml.etree.Element("h1")
            h.text = "Categories"
            catlinks.insert(0, h)
        for footer in root.cssselect("#footer"):
            h = lxml.etree.Element("h1")
            h.text = "Notes"
            footer.insert(0, h)

        return lxml.etree.tostring(root, encoding="unicode", method="html", doctype="<!DOCTYPE html>")

    def filter_in(self, instring):
        def _filter(key, value, format, meta):
            # remove HTML specific stuff
            if key == "Link":
                # remove relative path prefix and .html suffix
                internal, [href, text] = value
                if href.endswith(".html"):
                    href = href[:-5]
# FIXME: this stupid detection will not work
#        or just leave the full path?
#                    if href.startswith("./"):
#                        href = href[2:]
#                    elif href.startswith("../"):
#                        href = href[3:]
                return pandocfilters.Link(internal, [href, text])
            
# TODO: it's implemented in filter_pre, but could be useful anyway since html may not be
#       the only input format; the most generic way should be implemented
#            if key == "Header":
#                level, classes, internal = value
#
#                # record top level
#                if self.heading_top_level == 0:
#                    self.heading_top_level = level
#
#                # ensure we start from h1 in output
#                if level > self.heading_top_level:
#                    level -= self.heading_top_level
#
#                return pandocfilters.Header(level, classes, internal)

        doc = json.loads(instring)
        altered = pandocfilters.walk(doc, _filter, self.format, doc[0]["unMeta"])
        return json.dumps(altered)

    def filter_post(self, instring):
        return instring

class Converter:
    def __init__(self, filter_inst, input_dir, output_dir, output_format):
        self.filter = filter_inst
        self.input_dir = os.path.abspath(input_dir)
        self.output_dir = os.path.abspath(output_dir)
        self.output_format = output_format

        # ensure output directory always exists
        if not os.path.isdir(self.output_dir):
            os.mkdir(self.output_dir)

    def convert(self):
        failed = []

        for path, dirs, files in os.walk(self.input_dir):
            for f in files:
                infile = os.path.join(path, f)
                outdir = os.path.join(self.output_dir, os.path.relpath(path, self.input_dir))
                outfile = os.path.join(os.path.normpath(outdir), f)
                outfile = os.path.splitext(outfile)[0] + "." + self.output_format
                if infile.endswith(".html"):
                    try:
                        self.convert_file(infile, outfile)
                    except PandocError as e:
                        failed.append(infile)
                        print(e)
                        print("  [conv failed] %s" % infile)
                else:
                    print("  [skip conv]   %s" % infile)
        
        if len(failed) > 0:
            print("failed to convert %d pages:" % len(failed))
            for f in failed:
                print("  %s" % f)

    def convert_file(self, infile, outfile):
        print("  [converting]  %s" % infile)

        # ensure that target directory exists (necessary for subpages)
        try:
            os.makedirs(os.path.split(outfile)[0])
        except FileExistsError:
            pass

        content = open(infile, "r").read()
        content = self.filter.filter_pre(content)
        content = self.pandoc_first(content)
        content = self.filter.filter_in(content)
        content = self.pandoc_last(content)
        content = self.filter.filter_post(content)

        f = open(outfile, "w")
        f.write(content)
        f.close()

    def run_pandoc(self, cmd, instring):
        popen = subprocess.Popen(cmd, shell=True, universal_newlines=True,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        outs, errs = popen.communicate(instring)

        if popen.returncode != 0:
            raise PandocError(popen.returncode, errs)

        return outs

    def pandoc_first(self, instring):
        return self.run_pandoc("pandoc -s -f html -t json", instring)

    def pandoc_last(self, instring):
        return self.run_pandoc("pandoc -s -f json -t %s" % self.output_format, instring)

if __name__ == "__main__":
    f = ManFilter()
    c = Converter(f, "./wiki/", "./output/", "man")
    c.convert()
