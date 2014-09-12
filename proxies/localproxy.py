# coding=utf-8

# Suprisingly local:
# -----------------------------------
# http://www.qq.com/
# http://www.sina.com.cn/
# http://www.ifeng.com/
# http://weather.com/
# https://www.tuenti.com/
# http://blogs.wsj.com/
# http://www.macba.cat/
# http://www.npr.org
# http://www.usatoday.com/

# Not local:
# -----------------------------------
# http://laboralcentrodearte.org
# http://www.cccb.org/
# http://mob-barcelona.com
# https://www.google.es/


import os,sys
import requests
import json
import threading
import socket

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

from utils import concurrent, avoid_captive_portal, generate_trust, get_logger

from jinja2 import Environment, FileSystemLoader
template_env = Environment(loader=FileSystemLoader("templates"))

from config import global_config

local_country_codes = ["es"]
local_region_codes = ["*"]

options = {
        "static-server-host": "static-01.slow",
        "static-server-port": "8000",
        }

log = get_logger("LOCAL")

class LocalMaster(controller.Master):
    def __init__(self, server):
        controller.Master.__init__(self, server)

    def run(self):
        try:
            return controller.Master.run(self)
        except KeyboardInterrupt:
            self.shutdown()

    def handle_request(self, msg):
        # Process requests from clients to Internet servers
        # -------------------------------------------------

        # Don't allow cached HTML requests, but go ahead and cache CSS, JS, images, etc
        if "text/html" in "".join(msg.headers["accept"]):
            del(msg.headers["if-modified-since"])
            del(msg.headers["if-none-match"])
            #print "NO-CACHE"

        msg.reply()

    @concurrent
    def handle_response(self, msg):
        # Process replies from Internet servers to clients
        # ------------------------------------------------
        # First see if we need to show the HTTPS user agreement/certificate download
        client_ip = msg.flow.client_conn.address.address[0]
        router_ip = global_config["router_IPs"]["local"]
        if generate_trust(msg, client_ip, router_ip):
            return

        content_type = " ".join(msg.headers["content-type"])
        if content_type is None or "text/html" not in content_type:
            return

        if avoid_captive_portal(msg):
            return

        try:
            
            content_type = " ".join(msg.headers["content-type"])
            
            msg.flow.request.host = "".join(msg.flow.request.headers["host"])

            if msg.code != 301 and msg.code != 302 and content_type is not None and "text/html" in content_type and msg.flow.request.host not in ["192.168.1.128", "127.0.0.1", "localhost"]:
                # Try to do a local DNS lookup and search by IP for more accurate results
                try:
                    #query = socket.gethostbyaddr(msg.request.host)[2][0]
                    query = socket.getaddrinfo(msg.flow.request.host, 80)[0][4][0]  # I think this is more reliable
                except:
                    query = msg.flow.request.host

            
                r = requests.get("http://freegeoip.net/json/" + query)
                log.debug(u"{} - {}".format(msg.flow.request.host, r.content))

                try:
                    j = json.loads(r.content)
                    country_code = j["country_code"].lower()
                    region_code = j["region_code"].lower()
                
                    # Append "the" before certain countries to sound more natural
                    if j["country_name"] in ["United States", "United Kingdom", "Netherlands"] and j["region_name"] == "" and j["city"] == "":
                        j["country_name"] = "the {}".format(j["country_name"])

                    if country_code not in local_country_codes:
                        # Just show a flag
                        notes = ""
                        if j["region_name"] != "":
                            if j["city"] != "":
                                notes = u"It is hosted in {}, {}, {}.".format(j["city"], j["region_name"], j["country_name"])
                            else:
                                notes = u"It is hosted in {}, {}.".format(j["region_name"], j["country_name"])
                        else:
                            notes = u"It is hosted in {}.".format(j["country_name"])

                        #notes = u"<span style='font-size: 50%'>" + notes + u"</span>"

                        flag = country_code
                        if country_code == "us" and region_code != "":
                            flag = u"{}-{}".format(country_code, region_code)

                        template = template_env.get_template('local/notlocal.html')
                        msg.content = template.render(flag=flag, host=msg.flow.request.host, notes=notes)

                        #msg.content = u"<html><body style='background: url(http://{}:{}/flags/{}.png); background-size: 100%;'><div style='width: 900px; height: 200px; margin: auto; position: absolute; left:0; right:0; top:0; bottom:0; text-align: center; font-size: 36pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em; text-shadow: black 0 0 40px;'><div style='background: rgba(0,0,0,.5); width: auto;'>{}<br>IS NOT LOCAL<br>{}</div></div></body></html>".format(options["static-server-host"], options["static-server-port"], flag, msg.flow.request.host.upper(), extras)
                    
                        # Force unicode
                        msg.content = msg.content.encode("utf-8")
                        msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]
                    
                        #if len(msg.headers["content-encoding"]) > 0:
                        #   msg.encode(msg.headers["content-encoding"][0])
                        # Force uncompressed response
                        msg.headers["content-encoding"] = [""]
                        
                        # Don't cache
                        msg.headers["Pragma"] = ["no-cache"]
                        msg.headers["Cache-Control"] = ["no-cache, no-store"]

                        log.info(u"NOT local: <{}>".format(msg.flow.request.host))
                    else:
                        log.info(u"LOCAL: <{}>".format(msg.flow.request.host))
                except ValueError as e:
                    #template = template_env.get_template('local/error.html')
                    template = template_env.get_template('local/notlocal.html')
                    msg.content = template.render(host=msg.flow.request.host, flag="missing")

                    #msg.content = "<html><body style='background: url(http://{}:{}/flags/missing.png); background-size: 100%;'><div style='width: 900px; height: 200px; margin: auto; position: absolute; left:0; right:0; top:0; bottom:0; text-align: center; font-size: 36pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em; text-shadow: black 0 0 40px;'><div style='background: rgba(0,0,0,.5); width: auto;'>I DON'T KNOW WHERE I AM<br><span style='font-size: 50%; line-height: 1.75em;'>Check back later to find out if<br>{}<br>is local.</span></div></div></body></html>".format(options["static-server-host"], options["static-server-port"], msg.flow.request.host.upper())
                    msg.headers["content-encoding"] = [""]
                    # Don't cache
                    msg.headers["Pragma"] = ["no-cache"]
                    msg.headers["Cache-Control"] = ["no-cache, no-store"]
                    
                    
                    log.exception(u"<{}> parsing JSON for {} ".format(type(e).__name__, msg.flow.request.host))
                    

        except Exception as e:
            log.exception(u"<{}> checking {} ".format(type(e).__name__, msg.flow.request.host))


if global_config["transparent_mode"]:
    config = ProxyConfig(
        confdir = "~/.mitmproxy",
        mode = "transparent"
    )
else:
    config = ProxyConfig(confdir = "~/.mitmproxy")


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
server = ProxyServer(config, port)
m = LocalMaster(server)


log.info("---- LOCAL proxy loaded on port {} ---".format(port))
m.run()

