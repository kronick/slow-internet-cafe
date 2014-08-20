from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

from utils import concurrent, get_hostname, get_user_info

import os
import re
import time

import json
import sqlite3

from bs4 import BeautifulSoup

from random import choice, random

from config import global_config

TRANSPARENT = False

collapse_whitespace_rex = re.compile(r'\s+')

options = {
    "replace_chance_short":  0.2,    # Chance of replacing a short string (~word length)
    "replace_chance_medium": 0.4,    # Chance of replacing a medium string (~sentence length)
    "replace_chance_long":   0.9,    # Chance of replacing a long string (paragraph+ length)
    "string_limit_short":    50,     # Max length of a "short" string
    "string_limit_medium":   500,    # Max length of a "medium" string
}

string_length_classes = range(1,20)

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
            
            req = msg.flow.request
            url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)

            if content_type is not None and "text/html" in content_type:
                # Decode contents (if gzip'ed)
                contents = msg.get_decoded_content()

                client_ip = msg.flow.client_conn.address.address[0]
                hostname, mac = get_user_info(client_ip, global_config["router_IPs"]["swap"]) or client_ip
                user = {"mac": mac, "ip": client_ip, "hostname": hostname}
                
                t1 = time.time()
                replacements = load_replacements(mac)
                t2 = time.time()
                print "Loaded replacements in {}ms".format((t2-t1)*1000)

                msg.content = process_as_html(user, url, contents, charset, replacements)
                
                
                # Force uncompressed response
                msg.headers["content-encoding"] = [""]

                # Force unicode
                msg.content = msg.content.encode("utf-8")
                msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]

            # Handle JSON
            if "https://twitter.com" in url and content_type is not None and ("json" in content_type or "javascript" in content_type):
                try:
                    j = json.loads(msg.get_decoded_content(),  encoding = charset)
                except ValueError:
                    # Not really JSON
                    print "this is not json1!!"
                    return

                client_ip = msg.flow.client_conn.address.address[0]
                hostname, mac = get_user_info(client_ip, global_config["router_IPs"]["swap"]) or client_ip
                user = {"mac": mac, "ip": client_ip, "hostname": hostname}
                
                replacements = load_replacements(mac)
                process_html_in_json(user, url, j, charset, replacements)

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

def process_html_in_json(user, url, j, charset, replacements):
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
                    soup = process_as_html(user, url, soup, charset, replacements)
                    j[k] = unicode(u" ".join([unicode(t) for t in soup.body.contents]))

                    print "---> Found some HTML in this JSON!"

                
                    #print j[k]
                else:
                    print u"Just a single value: " + j[k]
                    

            except TypeError as e:
                #print "Trying next level..."

                process_html_in_json(user, url, j[k], charset, replacements)
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



def process_as_html(user, url, contents, charset, replacements):
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
    # Keep track of used lines to be deleted later
    swap_strings = replacements["strings"]
    used_strings = []
    for line in lines:
        line_len = len(line.strip())
        if swap_strings.get(line_len):
            replacement = choice(swap_strings[line_len])
            replacement_string = replacement["string"]
            replacement_id = replacement["string_id"]

            rand = random()
            should_replace = (line_len < options["string_limit_short"] and rand < options["replace_chance_short"]) or \
                             (line_len >= options["string_limit_short"] and line_len < options["string_limit_medium"] and \
                                    rand < options["replace_chance_medium"]) or \
                             (line_len >= options["string_limit_medium"] and rand < options["replace_chance_long"])

            if should_replace and line_len > 1 and unicode(line).strip() != unicode(replacement_string).strip():
                #print u"{} -- becomes --> {}".format(unicode(line).strip(), replacement_string.strip())

                # Preserve spaces before and after
                padded_replacement_string = replacement_string
                if line[0] == u" ":
                    padded_replacement_string = u" " + padded_replacement_string
                if line[-1] == u" ":
                    padded_replacement_string =  padded_replacement_string + u" "

                if line[0:2] == u". ":
                    padded_replacement_string =  u". " + padded_replacement_string
                if line[0:2] == u", ":
                    padded_replacement_string =  u", " + padded_replacement_string

                # TODO: Check if this is a good match because it
                #       a) starts/ends with the same punctuation, if any
                #       b) starts with same case (upper/lowercase)
                #       c) starts/ends with 

                #line.replace_with(u"{}  / {}".format(unicode(line), padded_replacement_line))
                line.replace_with(padded_replacement_string)
                
                # Remove from list
                used_strings.append(replacement_id)

    delete_replacements(used_strings, None, None)

    add_content_to_db(user, url, line_strings, None, None)

    #for length in swap_strings:
    #    print "{1} strings of length {0}".format(length, len(swap_strings[length]))

    return soup


def load_replacements(not_this_mac):
    with sqlite3.connect("db/swap.db") as db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        # Select a random host from the most recently updated
        t1 = time.time()
        cursor.execute('''
            SELECT * FROM users WHERE mac IS NOT ? ORDER BY last_seen DESC LIMIT 3
        ''', (not_this_mac,))
        users = cursor.fetchall()
        
        if not users:
            return

        swap_user = choice(results)

        t2 = time.time()
        print "Got user in {}ms".format((t2-t1)*1000)

        print swap_user

        t1 = time.time()
        cursor.execute("SELECT * FROM strings WHERE string_user IS ? ORDER BY time_added ASC LIMIT 5000", (swap_user["mac"],))
        results = cursor.fetchall() or []
        t2 = time.time()
        print "Got strings in {}ms".format((t2-t1)*1000)

        # Sort result into dict by length
        # Need to keep full record around so we can delete by ID when used
        t1 = time.time()
        swap_strings = {0:[]}
        for r in results:
            
            stripped = r["string"].strip()
            length = len(stripped)
            if not swap_strings.get(length):
                swap_strings[length] = [r]
            else:
                if r not in swap_strings[length]:
                    swap_strings[length].append(r) 

        t2 = time.time()
        print "Sorted {} strings in {}ms".format(len(results), (t2-t1)*1000)

        return {
            "strings": swap_strings,
            "images": None,
            "links": None
        }

def delete_replacements(used_strings, used_images, used_links):
    with sqlite3.connect("db/swap.db") as db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        for i in used_strings or []:
            cursor.execute("DELETE FROM strings WHERE string_id = ?", (i,))
        for i in used_images or []:
            cursor.execute("DELETE FROM images WHERE image_id = ?", (i,))
        for i in used_links or []:
            cursor.execute("DELETE FROM links WHERE link_id = ?", (i,))

        db.commit()
    

def update_users_database(hostname, client_ip, mac):
    if not client_ip and not mac:
        return

    with sqlite3.connect("db/swap.db") as db:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        # See if this MAC address already exists in the user table
        cursor.execute("INSERT OR REPLACE INTO users(mac, hostname, last_ip, last_seen) VALUES(?, ?, ?, ?)",
                        (mac or client_ip, hostname, client_ip, int(time.time())))
        db.commit()

def add_content_to_db(user, source_url, strings, images, links):
    with sqlite3.connect("db/swap.db") as db:
        cursor = db.cursor()

        # Expects a user dictionary with mac, ip and hostname
        client_ip = user["ip"]
        mac = user["mac"]
        hostname = user["hostname"]


        # Update the user database. Do this here to limit transactions per pageview
        cursor.execute("INSERT OR REPLACE INTO users(mac, hostname, last_ip, last_seen) VALUES(?, ?, ?, ?)",
                        (mac or client_ip, hostname, client_ip, int(time.time())))

        for s in strings:
            cursor.execute('''
                INSERT INTO strings(string_user, string, length, url, time_added)
                            VALUES(?, ?, ?, ?, ?)
            ''', (mac or client_ip, s, len(s), source_url, int(time.time())))

        db.commit()



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
