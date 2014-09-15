# coding=utf-8

# TODO:
# [ ] Limit number of requests/threads per user
# [ ] Better error handling/investigate crashes
import os, sys
import threading
import requests
import base64
import httplib
import json
import random

import time

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

from utils import concurrent, generate_trust, get_logger

from bs4 import BeautifulSoup

from PIL import Image

from config import global_config

log = get_logger("SIMILAR")

options = {
    "frequency": 1, # Only replace every nth image
    "smallest_image": 5000, # Only consider images larger than this many bytes
    "request_timeout": 15,
}

images_processed = 0
images_pending = 0;

class SimilarMaster(controller.Master):

    def __init__(self, server):
        controller.Master.__init__(self, server)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    def handle_request(self, msg):
        # Process requests from users to Internet servers

        # Don't allow cached images requests, but go ahead and cache CSS, JS, HTML, etc
        if "image/jpeg" in "".join(msg.headers["accept"]) or "image/webp" in "".join(msg.headers["accept"]) or "image/png" in "".join(msg.headers["accept"]) or "image/gif" in "".join(msg.headers["accept"]):
            del(msg.headers["if-modified-since"])
            del(msg.headers["if-none-match"])
            del(msg.headers["Cache-Control"])

        msg.reply()

    def handle_response(self, msg):
        # First see if we need to show the HTTPS user agreement/certificate download
        client_ip = msg.flow.client_conn.address.address[0]
        router_ip = global_config["router_IPs"]["similar"]
        if generate_trust(msg, client_ip, router_ip):
            return

        is_image = (msg.headers["content-type"] == ["image/jpeg"] or msg.headers["content-type"] == ["image/png"] or msg.headers["content-type"] == ["image/webp"] or msg.headers["content-type"] == ["image/gif"]) and msg.code == 200 and not msg.flow.request.headers["X-Do-Not-Replace"] and len(msg.content) > options["smallest_image"]

        global images_processed
        global images_pending
        if is_image: images_processed += 1
        should_process = images_processed % options["frequency"] == 0
        
        if is_image and should_process:
            images_pending += 1
            req = msg.flow.request
            url = u"{}://{}{}".format(req.get_scheme(), u"".join(req.headers["host"]), req.path)
            
            if images_pending > 10:
              log.info("--- {} images in the queue!".format(images_pending))
            
            try:
                self.process_image(msg)

            except Exception as e:
                log.exception(u"<{}> processing {} ".format(type(e).__name__, url))

        else:
            msg.reply()

    @concurrent        
    def process_image(self, msg):
        global images_pending
        client_ip = msg.flow.client_conn.address.address[0]
        req = msg.flow.request
        url = u"{}://{}{}".format(req.get_scheme(), u"".join(req.headers["host"]), req.path)
        #log.info(u"{} requests {}".format(client_ip, url))   
        # [ ] Better error handling/investigate crashes
        # Make a POST request with multipart/form and following fields:
        # filename: whatever.jpg
        # image_content: base_64 encoded data with "-_" instead of "+/"
        # encoded_image: None
        # image_url: None
        # And original headers

        search_url = "http://images.google.com/searchbyimage/upload"
        filename = "similar.jpg"
        image_content = base64.b64encode(msg.get_decoded_content(), "-_")
        
        request_headers = {
             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
             "Proxy-Connection": "keep-alive",
             "Cache-Control": "max-age=0",
             "Origin": "http://images.google.com",
             "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
             #"X-Client-Data": "CMO1yQEIhLbJAQiitskBCKm2yQEIwbbJAQi4iMoBCOyIygEI9pPKAQ==",
             "Referer": "http://images.google.com/",
             "Accept-Encoding": "gzip,deflate,sdch",
             "Accept-Language": "en-US,en;q=0.8"
        }

        
        try:
            t1 = time.time()
            r = requests.post(search_url,
                files={"image_url": "", "encoded_image": "", "image_content": image_content, "filename": filename},
                headers = request_headers,
                timeout = options["request_timeout"])
            t2 = time.time()


            log.debug("Google request made in {:0.3f} s".format(t2-t1))
            

            try:
                soup = BeautifulSoup(r.text)
                
                similar_section = soup.find(id="iur")
                if(similar_section is not None):
                    similar_elements = similar_section.find_all("li")

                    n_similar = len(similar_elements)
                    chosen_similar = similar_elements[random.randint(0,n_similar-1)]

                    similar_url = json.loads(chosen_similar.find(class_="rg_meta").text)["ou"]

                    #print "Replacing with <{}>".format(similar_url)
                    t1 = time.time()
                    img = requests.get(similar_url, headers={"X-Do-Not-Replace": "True"})
                    t2 = time.time()
                    log.debug("{}\n--> downloaded in in {:0.3f} s".format(similar_url[-8:], t2-t1))
                    msg.content = img.content
            
                    # Force uncompressed response
                    msg.headers["content-encoding"] = [""]
                    # And don't cache
                    msg.headers["Pragma"] = ["no-cache"]
                    msg.headers["Cache-Control"] = ["no-cache, no-store"]
                    log.info(u"{} is replaced by --> {}".format(url, similar_url))
                else:
                    log.info(u"Could not find any similar images for {}".format(url))

            except Exception as e:
                log.exception(u"<{}> processing {} ".format(type(e).__name__, url))

        except requests.exceptions.Timeout:
            log.warning(u"Timeout finding similar images on {}".format(url))

        images_pending -= 1


if global_config["transparent_mode"]:
    config = ProxyConfig(
        confdir = "~/.mitmproxy",
        mode = "transparent"
    )
else:
    config = ProxyConfig(confdir = "~/.mitmproxy")

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
server = ProxyServer(config, port)
m = SimilarMaster(server)
log.info("---- SIMILAR proxy loaded on port {} ----".format(port))
m.run()

