# coding=utf-8

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

import os,sys
import requests
import threading
import socket
import sqlite3

from utils import concurrent, get_hostname, avoid_captive_portal, generate_trust, get_logger

from datetime import datetime, timedelta
from time import time

from jinja2 import Environment, FileSystemLoader
template_env = Environment(loader=FileSystemLoader("templates"))

from config import global_config

ALLOWED_HOSTS = ["captive.apple.com"]
ALLOWED_AGENTS = ["CaptiveNetworkSupport"]

log = get_logger("BLACKOUT")

class BlackoutMaster(controller.Master):
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
        router_ip = global_config["router_IPs"]["blackout"]
        if generate_trust(msg, client_ip, router_ip):
            return

        content_type = " ".join(msg.headers["content-type"])
        if msg.code != 301 and msg.code != 302 and content_type is not None and "text/html" in content_type:

            try:
               self.process_html(msg)
            except Exception as e:
                log.exception(e)


    def process_html(self, msg):
        if avoid_captive_portal(msg):
            return


        # Check if the requested URL is already in the database
        req = msg.flow.request
        url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)
        
        db = sqlite3.connect("db/blackout.db")
        db.row_factory = sqlite3.Row
        cursor = db.cursor()
        cursor.execute('''SELECT * FROM resources WHERE url=?''', (url,))
        resource = cursor.fetchone()

        client_ip = msg.flow.client_conn.address.address[0]

        if resource is None:
            # If not, add the URL to the database with current timestamp
            # and pass the page on as usual

            hostname = get_hostname(client_ip, global_config["router_IPs"]["blackout"]) or client_ip
            cursor.execute('''INSERT INTO resources(url, last_accessed, life_remaining, accessed_by) VALUES(?, ?, 0, ?)''',
                                                    (url, int(time()), hostname))
            db.commit()

        else:
            # If yes in the database, was it accessed within the past 24 hours?
            now = int(time())
            then = resource["last_accessed"]
            accessed_by = resource["accessed_by"]

            blackout_time = 86400 #86400 # 24 hours in seconds
            if now - then > blackout_time:
                # If not accessed in 24 hours, update the database with the current timestamp
                # and pass the page on as usual
                hostname = get_hostname(client_ip, global_config["router_IPs"]["blackout"]) or client_ip
                cursor.execute('''UPDATE resources SET last_accessed = ?, accessed_by = ? WHERE url = ?''', (now, hostname, url))
                db.commit()
            else:
                # If it was accessed in past 24 hours, display the blackout page with info
                then_date = datetime.fromtimestamp(then)
                now_date = datetime.fromtimestamp(now)
                available_date = then_date + timedelta(0, blackout_time)
                time_diff = now_date - then_date
                available_diff = available_date - now_date

                # Figure natural description for last access day
                accessed_day = ""
                if time_diff.days == 0:
                    accessed_day = "today"
                elif time_diff.days == 1:
                    accessed_day = "yesterday"
                else:
                    accessed_day = "{} days ago".format(time_diff.days)

                # Figure natural description for day page will be accessible again
                available_day = ""
                if available_diff.days == 0:
                    available_day = "today"
                elif available_diff.days == 1:
                    available_day = "tomorrow"
                else:
                    available_day = "in {} days".format(available_diff.days)

                blackout_diff = available_date - now_date
                minutes,seconds = divmod(blackout_diff.total_seconds(), 60)
                hours, minutes = divmod(minutes, 60)

                then_string = "{} at {}".format(accessed_day, then_date.strftime("%H:%M"))
                
                template = template_env.get_template("blackout/notavailable.html")

                msg.content = template.render(url=url, access_time = then_string, hours=int(hours), minutes=int(minutes), seconds=int(seconds), accessed_by=accessed_by)

                
                # Force unicode
                msg.content = msg.content.encode("utf-8")
                msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]
            
                # Force uncompressed response
                msg.headers["content-encoding"] = [""]
                
                # Don't cache
                msg.headers["Pragma"] = ["no-cache"]
                msg.headers["Cache-Control"] = ["no-cache, no-store"]

                # Allow any script
                del(msg.headers["content-security-policy"]) 
        db.close()


if global_config["transparent_mode"]:
    config = ProxyConfig(
        confdir = "~/.mitmproxy",
        mode = "transparent"
    )
else:
    config = ProxyConfig(confdir = "~/.mitmproxy")

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
server = ProxyServer(config, port)
m = BlackoutMaster(server)
log.info("---- BLACKOUT proxy loaded on port {} ----".format(port))
m.run()
