from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer

from random import random, randrange, randint, shuffle
import os

# TODO: Set these based on the surf report from San Diego or somewhere
weather_params = {
	"REVERBERATE": 0.8,
	"WAIT": 0.1,
	"SLOP": 0.1,
	"CHOP": 1.0
}

waveQueue = {}
buildingWave = ""

class SurfMaster(controller.Master):
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
			# Only worry about HTML for now
			content_type = " ".join(msg.headers["content-type"])
			if content_type is not None and "text/html" in content_type:
				#print msg.headers["content-encoding"]
				#print dir(msg)
				#print msg.get_decoded_content()

				new = not waveQueue.has_key(msg.flow.request.get_url())
				waveQueue[msg.flow.request.get_url()] = msg.get_decoded_content()

				if new or random() < weather_params["WAIT"]:
					# Tranquilo...
					msg.content = "<html><head><META HTTP-EQUIV='CACHE-CONTROL' CONTENT='NO-CACHE'></head><body style='margin: 0px;'><a href='javascript:window.location.reload()'><img src='http://media0.giphy.com/media/u538oVJPQ0Rzi/200.gif' style='border: 0; width: 100%; height: 100%'></a></body></html>"
					msg.encode(msg.headers["content-encoding"][0])

				else:
					output = ""
					survivors = {}
					for url in waveQueue:
						# Always output the current page, maybe some extra junk
						if msg.flow.request.get_url() == url or random() < weather_params["SLOP"]:
							thispage = waveQueue[url]
							insertion_point = randint(0, len(output))

							cut_start = randint(0, len(thispage))
							cut_stop  = randint(cut_start, len(thispage))
							if msg.flow.request.get_url() == url:
								cut_start = 0
								cut_stop = len(thispage)
							

							print "Inserting [{}:{}] from {} at {}".format(cut_start, cut_stop, url, insertion_point)
							output = output[:insertion_point] + thispage[cut_start:cut_stop] + output[insertion_point:]

							# Give this page a chance to surface again
							if new or random() < weather_params["REVERBERATE"]:
								survivors[url] = waveQueue[url]	
						else:
							survivors[url] = waveQueue[url]

					msg.content = output
					msg.encode(msg.headers["content-encoding"][0])
					
					# Don't cache
					msg.headers["Pragma"] = ["no-cache"]
					msg.headers["Cache-Control"] = ["no-cache, no-store"]

					# Update the list
					waveQueue.clear()
					for url in survivors:
						waveQueue[url] = survivors[url]
					

				# elif len(waveQueue) > 1 and random() < 0.5:
				# 	# UNLEASH THE WAVE
				# 	print "UNLEASHING THE WAVE:"
				# 	print waveQueue.keys()

				# 	msg.content = "\n".join(waveQueue.values())
				# 	msg.encode(msg.headers["content-encoding"][0])

				# 	waveQueue.clear()

		except Exception as e:
			print e

		msg.reply()

config = ProxyConfig(
	#cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
)
server = ProxyServer(config, 8080)
m = SurfMaster(server)
print "Proxy server loaded."
m.run()

