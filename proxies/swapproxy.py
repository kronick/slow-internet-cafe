from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

from utils import concurrent

import os
import re

import json

from bs4 import BeautifulSoup

from random import choice, random

from config import config

TRANSPARENT = False

collapse_whitespace_rex = re.compile(r'\s+')

swap_strings = {}

options = {
    "replace_chance": 0.2
}

class FreeMaster(controller.Master):
    def __init__(self, server):
        controller.Master.__init__(self, server)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    @concurrent
    def handle_request(self, msg):
        # Process requests from clients to Internet servers
        # -------------------------------------------------

        # Don't allow cached HTML requests, but go ahead and cache CSS, JS, images, etc
        if "text/html" in "".join(msg.headers["accept"]) or "json" in "".join(msg.headers["accept"]) or "javascript" in "".join(msg.headers["accept"]):
            del(msg.headers["if-modified-since"])
            del(msg.headers["if-none-match"])
            #print "NO-CACHE"

        msg.reply()

    @concurrent
    def handle_response(self, msg):
        # Process replies from Internet servers to clients
        # ------------------------------------------------
        #try:
            # Only worry about HTML for now
            content_type = " ".join(msg.headers["content-type"])

            content_headers = [x.strip() for x in content_type.split(";")]
            charset = None
            for head in content_headers:
                if head.startswith("charset="):
                    charset = head[8:].lower()

            if content_type is not None and "text/html" in content_type:
                
                # Decode contents (if gzip'ed)
                contents = msg.get_decoded_content()

                msg.content = process_as_html(contents, charset)
                
                #msg.content = soup

                
                # Force uncompressed response
                msg.headers["content-encoding"] = [""]

                # Force unicode
                msg.content = msg.content.encode("utf-8")
                msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]

            # Handle JSON
            if content_type is not None and "json" in content_type or "javascript" in content_type:
                try:
                    j = json.loads(msg.get_decoded_content(),  encoding = charset)
                except ValueError:
                    # Not really JSON
                    print "this is not jsgon1!!"
                    return

                process_html_in_json(j, charset)

                msg.content = json.dumps(j, sort_keys=True, indent=4, separators=(',', ': '), encoding="utf-8")

                # Force uncompressed response
                msg.headers["content-encoding"] = [""]

                # Force unicode
                msg.content = msg.content.encode("utf-8")
                msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]

            # Never cache response
            msg.headers["Pragma"] = ["no-cache"]
            msg.headers["Cache-Control"] = ["no-cache, no-store"]

        #except Exception as e:
        #    print repr(e)

def process_html_in_json(j, charset):
    try:
        for k in j:
            # Try to process as HTML
            #is_html = False
            try:
                soup = BeautifulSoup(j[k], from_encoding = charset)

                if soup.body and len(soup.body.contents) > 1:
                    #for link in soup.body("a"):
                        #link.strings[0].replace_with("LINK!!!")
                     #   print [s for s in link.strings]
                    soup = process_as_html(soup, charset)
                    j[k] = unicode(u" ".join([unicode(t) for t in soup.body.contents]))

                    print "---> Found some HTML in this JSON!"

                
                    #print j[k]
                else:
                    print u"Just a single value: " + j[k]
                    

            except TypeError as e:
                #print "Trying next level..."

                process_html_in_json(j[k], charset)
                #print j[k]
                #print e    
    except TypeError:
        #print "This is not JSON!"
        #print j
        pass

def find_string_elements(el):
    out = []
    if not el:
        return []

    for string in el.strings:
        stripped_string = collapse_whitespace_rex.sub(' ', unicode(string))
        if stripped_string and stripped_string != " " and string.parent.name not in ["script", "style", "noscript"]:
            #print u"<{0}>{1}</{0}>".format(string.parent.name, string.strip())

            out.append(string)

    return out

            
    #for child in el.descendents:
    #    if child.string:
    #        print "<{}> {}".format(child.name, collapse_whitespace_rex.sub(' ', unicode(child.string)))
    #if el.string:
    #    print "<{}> {}".format(el.name, collapse_whitespace_rex.sub(' ', unicode(el.string)))
    #else:
    #    for child in el.children:
    #        find_string_elements(child)


def process_as_html(contents, charset):
    if type(contents) == BeautifulSoup:
        soup = contents
    else:
        soup = BeautifulSoup(contents, "html5lib", from_encoding = charset)
    # kill all script and style elements
    #for script in soup(["script", "style"]):
    #    script.extract()    # rip it out

    #text = soup.get_text()

    #for child in soup.body.children:
        #print u"-->" + unicode(child)
    #    find_string_elements(child)
    lines = find_string_elements(soup)

    # Need to make a copy of the strings in each tag so we can modify the current page and still use its content later
    line_strings = [unicode(line) for line in lines]

    # Replace some strings with strings of equal length from the database
    for line in lines:
        line_len = len(line.strip())
        if swap_strings.get(line_len):
            replacement_line = choice(swap_strings[line_len])
            if random() < options["replace_chance"] and line_len > 1 and unicode(line).strip() != unicode(replacement_line).strip():
                print u"{} -- becomes --> {}".format(unicode(line).strip(), replacement_line.strip())

                # Preserve spaces before and after
                padded_replacement_line = replacement_line
                if line[0] == u" ":
                    padded_replacement_line = u" " + padded_replacement_line
                if line[-1] == u" ":
                    padded_replacement_line =  padded_replacement_line + u" "

                if line[0:2] == u". ":
                    padded_replacement_line =  u". " + padded_replacement_line
                if line[0:2] == u", ":
                    padded_replacement_line =  u", " + padded_replacement_line

                # TODO: Check if this is a good match because it
                #       a) starts/ends with the same punctuation, if any
                #       b) starts with same case (upper/lowercase)
                #       c) starts/ends with 

                #line.replace_with(u"{}  / {}".format(unicode(line), padded_replacement_line))
                line.replace_with(padded_replacement_line)
                
                # Remove from list
                swap_strings[line_len] = [s for s in swap_strings[line_len] if s != replacement_line]

    # Add strings from the original document to the "database"
    for line in line_strings:
        line = line.strip()
        line_len = len(line)
        if not swap_strings.get(line_len):
            swap_strings[line_len] = [line]
        else:
            if line not in swap_strings[line_len]:
                swap_strings[line_len].append(line)

    #for length in swap_strings:
    #    print "{1} strings of length {0}".format(length, len(swap_strings[length]))

    return soup


if config["transparent_mode"]:
    config = ProxyConfig(
        confdir = "~/.mitmproxy",
        mode = "transparent"
    )
else:
    config = ProxyConfig(confdir = "~/.mitmproxy")

server = ProxyServer(config, 8080)
m = FreeMaster(server)
print "Proxy server loaded."
m.run()
