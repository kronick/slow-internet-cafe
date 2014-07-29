# coding=utf-8

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer

import os
import requests
import json
import threading
import socket

local_country_codes = ["es"]
local_region_codes = ["*"]


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

	def handle_response(self, msg):
		# Process replies from Internet servers to clients
		# ------------------------------------------------
		content_type = " ".join(msg.headers["content-type"])
		if content_type is None or "text/html" not in content_type:
			msg.reply()
			return
		try:
			# Make this threaded:
			reply = msg.reply
			m = msg
			msg.reply = controller.DummyReply()
			if hasattr(reply, "q"):
				msg.reply.q = reply.q

			def run():
				# Only worry about HTML for now (and ignore 301/302 redirects)
				content_type = " ".join(msg.headers["content-type"])
				if msg.code != 301 and msg.code != 302 and content_type is not None and "text/html" in content_type and msg.flow.request.host not in ["192.168.1.128", "127.0.0.1", "localhost"]:
					# Try to do a local DNS lookup and search by IP for more accurate results
					try:
						#query = socket.gethostbyaddr(msg.request.host)[2][0]
						query = socket.getaddrinfo(msg.flow.request.host, 80)[0][4][0]	# I think this is more reliable
					except:
						query = msg.flow.request.host

					print msg.flow.request.host
					r = requests.get("http://freegeoip.net/json/" + query)
					print r.content
					try:
						j = json.loads(r.content)
						country_code = j["country_code"].lower()
						region_code = j["region_code"].lower()
						
						if country_code not in local_country_codes:
							# Just show a flag
							extras = ""
							if j["region_name"] != "":
								if j["city"] != "":
									extras = u"It is hosted in {}, {}, {}.".format(j["city"], j["region_name"], j["country_name"])
								else:
									extras = u"It is hosted in {}, {}.".format(j["region_name"], j["country_name"])
							else:
								extras = u"It is hosted in {}.".format(j["country_name"])

							extras = u"<span style='font-size: 50%'>" + extras + u"</span>"

							flag = country_code
							if country_code == "us" and region_code != "":
								flag = u"{}-{}".format(country_code, region_code)

							#msg.content = u"<html><body style='background: #b9b9a9 '><div style='margin-top: 1em; margin-bottom: 1em; text-align: center; font-size: 24pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em;'>{}<br><img src='http://localhost:8000/flags/{}.png' style='height: 400px'><br>IS NOT LOCAL<br>{}</div></body></html>".format(msg.request.host.upper(), flag, extras)
							#msg.content = "<html><body style='background: #ff8989; background: -moz-linear-gradient(-45deg, #ff8989 0%, #53cbf1 97%); background: -webkit-gradient(linear, left top, right bottom, color-stop(0%,#ff8989), color-stop(97%,#53cbf1)); background: -webkit-linear-gradient(-45deg, #ff8989 0%,#53cbf1 97%); background: -o-linear-gradient(-45deg, #ff8989 0%,#53cbf1 97%); background: -ms-linear-gradient(-45deg, #ff8989 0%,#53cbf1 97%); background: linear-gradient(135deg, #ff8989 0%,#53cbf1 97%); filter: progid:DXImageTransform.Microsoft.gradient( startColorstr=\'#ff8989\', endColorstr=\'#53cbf1\',GradientType=1 ); '><div style='margin-top: 1em; margin-bottom: 1em; text-align: center; font-size: 24pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em;'>{}<br><img src='http://localhost:8000/flags/{}.png' style='height: 400px'><br>IS NOT LOCAL<br>{}</div></body></html>".format(msg.request.host.upper(), country_code, extras)
							msg.content = u"<html><body style='background: url(http://127.0.0.1:8000/flags/{}.png); background-size: 100%;'><div style='width: 900px; height: 200px; margin: auto; position: absolute; left:0; right:0; top:0; bottom:0; text-align: center; font-size: 36pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em; text-shadow: black 0 0 40px;'><div style='background: rgba(0,0,0,.5); width: auto;'>{}<br>IS NOT LOCAL<br>{}</div></div></body></html>".format(flag, msg.flow.request.host.upper(), extras)
						
							# Force unicode
							msg.content = msg.content.encode("utf-8")
							msg.headers["content-type"] = ["{}; charset=utf-8".format(msg.headers["content-type"][0])]
						
							#if len(msg.headers["content-encoding"]) > 0:
							#	msg.encode(msg.headers["content-encoding"][0])
							# Force uncompressed response
							msg.headers["content-encoding"] = [""]
							
							# Don't cache
							msg.headers["Pragma"] = ["no-cache"]
							msg.headers["Cache-Control"] = ["no-cache, no-store"]
					except ValueError as e:
						msg.content = "<html><body style='background: url(http://127.0.0.1:8000/flags/missing.png); background-size: 100%;'><div style='width: 900px; height: 200px; margin: auto; position: absolute; left:0; right:0; top:0; bottom:0; text-align: center; font-size: 36pt; font-family: sans-serif; font-weight: bold; color: white; line-height: 1.5em; text-shadow: black 0 0 40px;'><div style='background: rgba(0,0,0,.5); width: auto;'>I DON'T KNOW WHERE I AM<br><span style='font-size: 50%; line-height: 1.75em;'>Check back later to find out if<br>{}<br>is local.</span></div></div></body></html>".format(msg.request.host.upper())
						msg.headers["content-encoding"] = [""]
						# Don't cache
						msg.headers["Pragma"] = ["no-cache"]
						msg.headers["Cache-Control"] = ["no-cache, no-store"]
						
						print "Could not decode JSON: " + str(e)
					
					reply()
					
				else:

					reply()
			threading.Thread(target=run).start()

		except Exception as e:
			print e

		#msg.reply()

config = ProxyConfig(
	#certs = [os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")]
	confdir = "~/.mitmproxy"
)
#config = None
server = ProxyServer(config, 8080)
m = LocalMaster(server)
m.run()

