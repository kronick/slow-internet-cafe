from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

import os

TRANSPARENT = True

class TemplateMaster(controller.Master):
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
				
				# Just decode (probably un-gzip) and then re-encode the response contents
				contents = msg.get_decoded_content()
				msg.content = contents
				
				# Re-compress if requested
				# msg.encode(msg.headers["content-encoding"][0])

				# Force uncompressed response
				msg.headers["content-encoding"] = [""]

		except Exception as e:
			print e

		msg.reply()

if TRANSPARENT:
	config = ProxyConfig(
		confdir = "~/.mitmproxy",
    	http_form_in = "relative",
		http_form_out = "relative",
    	get_upstream_server = TransparentUpstreamServerResolver(platform.resolver(), TRANSPARENT_SSL_PORTS)
	)
else:
	config = ProxyConfig(confdir = "~/.mitmproxy")

#config = None
server = ProxyServer(config, 8080)
m = TemplateMaster(server)
print "Proxy server loaded."
m.run()
