# coding=utf-8
from random import random, randrange, randint, shuffle, choice, uniform
import os, threading,sys

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

import json, requests, datetime, time, sys, re, urllib2, traceback

from bs4 import BeautifulSoup
from urlparse import urljoin

from os import listdir
from os.path import isfile, join

from jinja2 import Environment, FileSystemLoader
template_env = Environment(loader=FileSystemLoader("templates"))

from config import global_config
from utils import concurrent

waveQueue = {}
buildingWave = ""

gif_dir = "../static/img/surf/"
api_pattern = re.compile(r"change_surf_spot=([^&]+)")

do_not_follow = ["http://www.tumblr.com/register", ]

ALLOWED_HOSTS = ["captive.apple.com"]
ALLOWED_AGENTS = ["CaptiveNetworkSupport"]

surf_spots = {
                u"Barceloneta":      {"id": 3535, "location": u"Barcelona, España"},
                u"Mundaka":          {"id": 169,  "location": u"País Vasco"},
                u"Blacks Beach":     {"id": 295,  "location": u"La Jolla, California"},
                #"Chicago":          {"id": 960,  "location": "Lake Michigan"},
                u"Playa San Lorenzo":{"id": 4387, "location": u"Gijón, España"},
                u"Rodiles":          {"id": 178,  "location": u"Gijón, España"},
                u"Taghazout":        {"id": 131,  "location": u"Morocco"},
                u"J-Bay":            {"id": 88,   "location": u"South Africa"},

                u"Mavericks":        {"id": 162,  "location": u"Half Moon Bay, California"},
                u"Nazaré":           {"id": 194,  "location": u"Portugal"},
                u"Teahupoo":         {"id": 619,  "location": u"Tahiti"},
                u"Pipeline":         {"id": 616,  "location": u"Oahu, Hawaii"},
                u"Trestles":         {"id": 291,  "location": u"San Diego County, California"},
                u"Rincon":           {"id": 272,  "location": u"Carpinteria, California"},
                u"Ocean Beach":      {"id": 255,  "location": u"San Francisco, California"},
}

def get_report(spot):
    api_base = "http://magicseaweed.com/api/" + global_config["msw_api_key"] + "/forecast/?units=eu&spot_id="
    r = requests.get(api_base + str(surf_spots[spot]["id"]))
    j = json.loads(r.content)
    print spot
    # Find current time
    now = int(time.time())
    diff = sys.maxsize
    nowcast = None
    for i in j:
        d = now - i["timestamp"]
        if d < diff and d > 0:
            nowcast = i
            diff = d

    rating = "["
    for n in range(nowcast["solidRating"]):
        rating += "*"
    for n in range(nowcast["fadedRating"]):
        rating += "-"
    rating += "]"
    print rating
    print "wind: " + str(nowcast["wind"]["speed"]) + nowcast["wind"]["unit"]
    print "waves: {}-{} {}".format(nowcast["swell"]["minBreakingHeight"], nowcast["swell"]["maxBreakingHeight"], nowcast["swell"]["unit"])

    report = {
        "REVERBERATE" : 0.5,
        "WAIT": (5-nowcast["solidRating"]) / 5.0 * .7 + .05,            # range is 0.05 - 0.8
        "SLOP": nowcast["fadedRating"] / 5.0 * 0.3 + 0.04,              # Chance of inserting gunk from other pages
        "SIZE": nowcast["swell"]["maxBreakingHeight"] or 0,             # Add n-1 extra pages based on wave size
        "FLAT": (nowcast["solidRating"] + nowcast["fadedRating"] == 0), # FLAT if nothing good or bad is happening
        "wind": str(nowcast["wind"]["speed"]) + nowcast["wind"]["unit"],
        "waves": "{}-{} {}".format(nowcast["swell"]["minBreakingHeight"], nowcast["swell"]["maxBreakingHeight"], nowcast["swell"]["unit"])
    }

    print report

    return report;

class SurfMaster(controller.Master):
    current_spot = choice(surf_spots.keys())
    weather_params = {}

    def __init__(self, server):
        controller.Master.__init__(self, server)
        self.weather_params = get_report(self.current_spot)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    @concurrent
    def handle_request(self, msg):
        # Process requests from clients to Internet servers
        # -------------------------------------------------
        if "change_surf_spot" in msg.path:
            matches = api_pattern.findall(msg.path)
            if(len(matches) > 0):
                s = urllib2.unquote(matches[0]).decode("utf-8")
                s = s.replace("+", " ")
                if s in surf_spots.keys() and s != self.current_spot:
                    print u"Moving to {}".format(s)
                    try:
                        self.weather_params = get_report(s)
                        self.current_spot = s
                    except TypeError:
                        print "Could not get surf report..."

                    msg.headers["x-surf-changed"] = ["True"]
                else:
                    if s == self.current_spot:
                        if msg.headers["x-surf-changed"]:
                            del(msg.headers["x-surf-changed"])
                        print "Already at " + s
                    else:
                        print u"{} not in spots list...".format(s)

        # Don't allow cached HTML requests, but go ahead and cache CSS, JS, images, etc
        if "text/html" in "".join(msg.headers["accept"]):
            del(msg.headers["if-modified-since"])
            del(msg.headers["if-none-match"])
            #print "NO-CACHE"

        msg.reply()

    @concurrent
    def handle_response(self, msg):
        # Process replies from Internet servers to clients
        if msg.flow.request.host in ALLOWED_HOSTS:
            msg.reply()
            return
        try:
            # Only worry about HTML for now
            content_type = " ".join(msg.headers["content-type"])
            content_headers = [x.strip() for x in content_type.split(";")]
            charset = None
            for head in content_headers:
                if head.startswith("charset="):
                    charset = head[8:].lower()

            if content_type is not None and "text/html" in content_type:
                req = msg.flow.request
                client_ip = msg.flow.client_conn.address.host
                url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)

                #print msg.headers["content-encoding"]
                #print dir(msg)
                #print msg.get_decoded_content()

                # Crawl a little bit if there aren't many pages in the queue yet
                if len(waveQueue) < 10:
                    links = get_links(url, msg.get_decoded_content(), charset = charset)
                    if len(links) > 0:
                        l = choice(links)
                        for i in range(5):
                            try:
                                print "Crawling " + l
                                r = requests.get(l)
                                waveQueue[l] = r.content.replace("</html>", "")
                                l = choice(get_links(l, r.content, None))
                            except requests.ConnectionError:
                                break


                if req.headers["x-surf-changed"] or self.weather_params["FLAT"] or random() < self.weather_params["WAIT"]:
                    gifs = [ f for f in listdir(gif_dir) if isfile(join(gif_dir,f))]
                    g = choice(gifs)

                    # Tranquilo...
                    message = ""
                    if self.weather_params["FLAT"]:
                        message = "Not much happening here..."
                    else:
                        if self.weather_params["SIZE"] > 2:
                            message = "Big waves "
                            end = "!"
                        elif self.weather_params["SIZE"] > 1:
                            message = "A nice swell "
                            end = "."
                        else:
                            message = "A gentle swell "
                            end = "."
                        if self.weather_params["SLOP"] >= .1:
                            message += "but it's all blown out!"
                        elif self.weather_params["SLOP"] > .5:
                            message += "with a bit of chop" + end
                        else:
                            message += end

                    template = template_env.get_template("surf/tranquilo.html")
                    msg.content = (template.render(spots=surf_spots, current_spot = self.current_spot, background=g,
                                   wind = self.weather_params["wind"], waves = self.weather_params["waves"], message = message,
                                   flat = self.weather_params["FLAT"], redirect = url)).encode("utf-8")

                
                    #msg.content = "<html><head><META HTTP-EQUIV='CACHE-CONTROL' CONTENT='NO-CACHE'></head><body style='margin: 0px;'><a href='javascript:window.location.reload()'><img src='http://media0.giphy.com/media/u538oVJPQ0Rzi/200.gif' style='border: 0; width: 100%; height: 100%'></a></body></html>"
                    msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]
                    msg.headers["content-encoding"] =  []

                    # Allow any script
                    del(msg.headers["content-security-policy"]) 

                else:
                    new = not waveQueue.has_key(url)
                    contents = msg.get_decoded_content().replace("</html>", "")
                    waveQueue[url] = contents
                    bigWave = {}
                    output = ""

                    links = get_links(url, contents, charset = charset)
                    if self.weather_params["SIZE"] > 1 and len(links) > 0:
                        # Get links, download one or two at random, append
                        for i in range(0, int((self.weather_params["SIZE"] - 1) * 3)):
                            if random() < 0.8:
                                l = choice(links)
                                print "Adding " + l
                                try:
                                    r = requests.get(l)
                                    waveQueue[l] = r.content.replace("</html>", "")
                                    bigWave[l] = waveQueue[l]
                                except requests.ConnectionError:
                                    print "Couldn't get link {}".format(l)

                    survivors = {}
                    keys = waveQueue.keys()
                    shuffle(keys)
                
                    i = 0
                    for u in keys:
                        i += 2
                        # Always output the current page, maybe some extra junk
                        if url == u or (random() < self.weather_params["SLOP"] and i < 50):
                            thispage = waveQueue[u]
                            insertion_point = randint(0, len(output))

                            cut_start = randint(0, len(thispage))
                            cut_stop  = randint(cut_start, len(thispage))
                            if url == u:
                                cut_start = 0
                                cut_stop = len(thispage)
                                #if self.weather_params["SIZE"] < 1:
                                #    cut_stop = len(thispage) * uniform(self.weather_params["SIZE"],1)
                            

                            print "Inserting [{}:{}] from {} at {}".format(cut_start, cut_stop, u, insertion_point)
                            output = output[:insertion_point] + thispage[cut_start:cut_stop] + output[insertion_point:]

                            if url == u and len(bigWave) > 0:
                                for l in bigWave:
                                    output += bigWave[l]

                            # Give this page a chance to surface again
                            if new or random() < self.weather_params["REVERBERATE"]:
                                survivors[u] = waveQueue[u] 
                        else:
                            survivors[u] = waveQueue[u]

                    msg.content = output
                    msg.headers["content-encoding"] =  []
                    
                    # Don't cache
                    msg.headers["Pragma"] = ["no-cache"]
                    msg.headers["Cache-Control"] = ["no-cache, no-store"]

                    # Update the list
                    waveQueue.clear()
                    for u in survivors:
                        waveQueue[u] = survivors[u]
                    

                # elif len(waveQueue) > 1 and random() < 0.5:
                #   # UNLEASH THE WAVE
                #   print "UNLEASHING THE WAVE:"
                #   print waveQueue.keys()

                #   msg.content = "\n".join(waveQueue.values())
                #   msg.encode(msg.headers["content-encoding"][0])

                #   waveQueue.clear()

                # Don't cache
                msg.headers["Pragma"] = ["no-cache"]
                msg.headers["Cache-Control"] = ["no-cache, no-store"]

        except Exception as e:
            print e
            print traceback.format_exc()

        msg.reply()
        

def get_links(url, html, charset):
    soup = BeautifulSoup(html, "html5lib", from_encoding = charset) 
    link_els = soup.find_all("a");
    hrefs = [l.get("href") for l in link_els]
    links = [urljoin(url, l) for l in hrefs if l and not l.startswith("#") and \
             not l.endswith(".jpg") and not l.endswith(".png") and not l.endswith(".jpeg") and \
             not l.endswith(".gif") and not l.endswith(".webp") and not l.endswith(".JPG") and \
             not l.endswith(".PNG") and not l.endswith(".GIF") and not l.endswith(".WEBP") and \
             l not in do_not_follow and "www.tumblr.com" not in l]

    return links



if global_config["transparent_mode"]:
    config = ProxyConfig(
        confdir = "~/.mitmproxy",
        mode = "transparent"
    )
else:
    config = ProxyConfig(confdir = "~/.mitmproxy")

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
server = ProxyServer(config, port)
m = SurfMaster(server)
print "SURF proxy loaded on port {}".format(port)
m.run()

