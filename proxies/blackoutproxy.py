# coding=utf-8

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

import os
import requests
import threading
import socket
import sqlite3

from datetime import datetime, timedelta
from time import time

from jinja2 import Environment, FileSystemLoader
template_env = Environment(loader=FileSystemLoader("templates"))

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

    def handle_response(self, msg):
        # Process replies from Internet servers to clients
        # ------------------------------------------------
        try:
            # Make this threaded:
            reply = msg.reply
            m = msg
            msg.reply = controller.DummyReply()
            if hasattr(reply, "q"):
                msg.reply.q = reply.q

            # -- Begin Thread
            def run():
                # Check if the requested URL is already in the database
                req = msg.flow.request
                url = "{}://{}{}".format(req.get_scheme(), "".join(req.headers["host"]), req.path)
                
                db = sqlite3.connect("db/blackout.db")
                cursor = db.cursor()
                cursor.execute('''SELECT url, last_accessed, life_remaining FROM resources WHERE url=?''', (url,))
                resource = cursor.fetchone()
                
                if resource is None:
                    # If not, add the URL to the database with current timestamp
                    # and pass the page on as usual

                    cursor.execute('''INSERT INTO resources(url, last_accessed, life_remaining) VALUES(?, ?, 0)''',
                                                            (url, int(time())))
                    db.commit()

                else:
                    # If yes in the database, was it accessed within the past 24 hours?
                    now = int(time())
                    then = resource[1]
                    blackout_time = 86400 #86400 # 24 hours in seconds
                    if now - then > blackout_time:
                        # If not accessed in 24 hours, update the database with the current timestamp
                        # and pass the page on as usual
                        cursor.execute('''UPDATE resources SET last_accessed = ? WHERE url = ?''', (now, url))
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
                        # available_string = "until {} at {}".format(available_day, available_date.strftime("%H:%M"))
                        available_string = "for <span id='h'>{}</span> hours, <span id='m'>{}</span> minutes, <span id='s'>{}</span> seconds".format(int(hours), int(minutes), int(seconds))
                        #script = "<script type='text/javascript' src='http://127.0.0.1:8000/static/jquery-1.11.1.min.js'></script>"
                        #script += "<script type='text/javascript'>$(document).ready(function() { setInterval(function() { h = $('#h').text(); m = $('#m').text(); s = $('#s').text(); if(s > 0) $('#s').text(s - 1); else if(m > 0) { $('#s').text('59'); $('#m').text(m-1); } else { $('#s').text('59'); $('#m').text('59'); $('#h').text(h-1); } }, 1000) });</script>"
                        script = "<script type='text/javascript'>setInterval(function() { h = document.getElementById('h').innerHTML; m = document.getElementById('m').innerHTML; s = document.getElementById('s').innerHTML; if(s > 0) document.getElementById('s').innerHTML = (s - 1); else if(m > 0) { document.getElementById('s').innerHTML = '59'; document.getElementById('m').innerHTML = (m-1); } else { document.getElementById('s').innerHTML = '59'; document.getElementById('m').innerHTML = '59'; document.getElementById('h').innerHTML = (h-1); } }, 1000);</script>"


                        extras = "<span style='font-size:50%; line-height: 1.5em'>The page was already accessed {}.<br>It will not be available again {}.<br><i>PLEASE SEEK OTHER PATHS</i>".format(then_string, available_string)
                        
                        template = template_env.get_template("blackout/notavailable.html")

                        msg.content = template.render(url=url, access_time = then_string, hours=int(hours), minutes=int(minutes), seconds=int(seconds))

                        #msg.content = u"<html><body style='background: url(http://127.0.0.1:8000/static/img/dusk.jpg); background-size: 100%; background-position: bottom'>{}<div style='width: 900px; height: 300px; margin: auto; position: absolute; left:0; right:0; top:0; bottom:0; text-align: center; font-size: 36pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em; text-shadow: black 0 0 40px;'><div style='background: rgba(0,0,0,.5); width: auto; padding: 30px;'>{}<br>IS NOT AVAILABLE<br>{}</div></div></body></html>".format(script, url, extras)
                        # "Dusk-A330" by mailer_diablo - Self-taken (Unmodified). Licensed under Creative Commons Attribution-Share Alike 3.0 via Wikimedia Commons - http://commons.wikimedia.org/wiki/File:Dusk-A330.JPG#mediaviewer/File:Dusk-A330.JPG.
                        
                        # Force unicode
                        msg.content = msg.content.encode("utf-8")
                        msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]
                    
                        # Force uncompressed response
                        msg.headers["content-encoding"] = [""]
                        
                db.close()
                reply()
                # ---- End Thread
            
            # Only worry about HTML for now and automatically follow redirects
            content_type = " ".join(msg.headers["content-type"])
            if msg.code != 301 and msg.code != 302 and content_type is not None and "text/html" in content_type:
                threading.Thread(target=run).start()
            else:
                reply()

        except Exception as e:
            print e
            msg.reply()

config = ProxyConfig(
    #certs = [os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")]
    confdir = "~/.mitmproxy",
    mode = "transparent"
)
#config = None
server = ProxyServer(config, 8080)
m = BlackoutMaster(server)
print "Proxy server loaded."
m.run()

