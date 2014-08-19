#coding=utf-8

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

from Adblock import Filter
from config import global_config


currency_pattern = re.compile(ur'''
    (
        (?P<before>^|\s|\(|>)                               # beginning of match condition
        (?P<value>(
            (\$|EUR(\s?)|EU(\s?)|£|€)                       # Currency type up front
            (?=\d)                                          # Make sure SOME number is coming...
            (
                (\d{1,3})?                                  # Variable length of digits one or more times
                ([,.]\d{3})*                                # optional thousands separators and 3 digit groups
            )                                               
            ([,.](\d{1,2}))?                                # optional cents
            (\sbillion|\strillion|\sbillón|\smillardo|\s)?  # optional text description
        )
        |                                                   # ---------- OR with currency AFTER the number
        (
            (?=\d)                                          # Make sure SOME number is coming...
            (
                (\d{1,3})?                                  # Variable length of digits one or more times
                ([,.]\d{3})*                                # optional thousands separators and 3 digit groups
            )                                               
            ([,.](\d{1,2}))?                                # optional cents
            (\sbillion|\strillion|\sbillón|\smillardo|\ )?  # optional text description
            ((\s?)EUR|(\s?)EU|(\s?)€|\sdollars|\seuros)     # Currency type at end
        ))        
        (?P<after>$|[.,!?)]|\s|\<|&(\w){1,6};)              # end of match condition
    )
''', (re.VERBOSE |re.UNICODE))

adblock_filter = Filter(file('data/easylist.txt'))


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
        if "text/html" in "".join(msg.headers["accept"]):
            del(msg.headers["if-modified-since"])
            del(msg.headers["if-none-match"])
            #print "NO-CACHE"

        url = "{}://{}{}".format(msg.get_scheme(), "".join(msg.headers["host"]), msg.path)
        #if adblock_filter.match(url):
        #    print url

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
            
            req = msg.flow.request
            url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)
            for head in content_headers:
                if head.startswith("charset="):
                    charset = head[8:].lower()

            if content_type is not None and "jpg" in content_type or "png" in content_type or "jpeg" in content_type:
                # Check to see if this is an ad
                if adblock_filter.match(url):
                    with open("../static/img/face-dot.png") as f:
                        msg.content = f.read()
                        # Force uncompressed response
                        msg.headers["content-encoding"] = [""]
                        msg.headers["content-type"] = ["image/png"]

                        print url

                        # Never cache  modified response
                        msg.headers["Pragma"] = ["no-cache"]
                        msg.headers["Cache-Control"] = ["no-cache, no-store"]         

            elif content_type is not None and "text/html" in content_type:
                if adblock_filter.match(url):
                    msg.content = "!!!"
                    return

                # Decode contents (if gzip'ed)
                contents = msg.get_decoded_content()
                #contents = "<p>€32</p>"
                #charset = "utf-8"

                soup = process_as_html(contents,  charset = charset)

                msg.content = soup

                
                # Force uncompressed response
                msg.headers["content-encoding"] = [""]

                # Force unicode
                msg.content = msg.content.encode("utf-8")
                msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]

                # Never cache  modified response
                msg.headers["Pragma"] = ["no-cache"]
                msg.headers["Cache-Control"] = ["no-cache, no-store"]         
 
            # Handle JSON
            elif content_type is not None and "json" in content_type or "javascript" in content_type:
                if adblock_filter.match(url):
                    msg.content = "!!!"
                    return
                return

                try:
                    j = json.loads(msg.get_decoded_content(),  encoding = charset)
                except ValueError:
                    # Not really JSON
                    #print "this is not jsgon1!!"
                    return
                return

                process_html_in_json(j, charset)

                msg.content = json.dumps(j, sort_keys=True, indent=4, separators=(',', ': '), encoding="utf-8")

                # Force uncompressed response
                msg.headers["content-encoding"] = [""]

                # Force unicode
                msg.content = msg.content.encode("utf-8")
                msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]       

                # Never cache  modified response
                msg.headers["Pragma"] = ["no-cache"]
                msg.headers["Cache-Control"] = ["no-cache, no-store"]         

        #except Exception as e:
        #    print repr(e)

def change_link_href(el, href):
    if not el.parent:
        return False
    elif el.parent.name is "a":
        el.parent["href"] = "about:blank"
        return True
    else:
        return change_link_href(el.parent, href)

def find_string_elements(el):
    out = []
    if not el:
        return []

    for string in el.strings:
        stripped_string = unicode(string)
        if stripped_string and stripped_string != " " and string.parent.name not in ["script", "style", "noscript"]:
            out.append(string)

    return out


def censor_currency_match(match):
    g = match.groupdict()
    
    censored = u""
    for i in range(1,len(g["value"])):
        censored += u"█"

    return (unicode(g["before"]) + censored + unicode(g["after"]))

# HTML and JSON handlers
# ----------------------------------------------------------
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
                    print j[k]
                    j[k] = u" ".join([unicode(t) for t in soup.body.contents])

                    print j[k]
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

def process_as_html(contents, charset):
    if type(contents) == BeautifulSoup:
        soup = contents
    else:
        soup = BeautifulSoup(contents, "html5lib", from_encoding = charset) 
        
    # Get references to all strings
    if not soup.body: return soup

    strings = find_string_elements(soup.body)
    images = soup.body("img")
    iframes = soup.body("iframe")
    #flash = soup.body("param")
    
    for string_el in strings:
        # Run regex on each string
        s = unicode(string_el)
        censored = currency_pattern.sub(censor_currency_match, s)
        if s is not censored:
            
            already_link = change_link_href(string_el, "http://www.slowerinternet.com")
            if not already_link:
                #print "Must create a link!"
                link = soup.new_tag("a", href="http://www.slowerinternet.com")
                link.string = censored
                string_el.replace_with(link)
            else:
                string_el.replace_with(censored)

    for img in images:
        if img.get("src") and adblock_filter.match(img["src"]):
            img["src"] = "https://docs.python.org/favicon.ico"

    for iframe in iframes:
        if iframe.get("src") and adblock_filter.match(iframe["src"]):
            iframe["src"] = "http://example.com"

    return soup
       

if global_config["transparent_mode"]:
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
