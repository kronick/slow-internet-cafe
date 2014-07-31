from libmproxy import controller, proxy
import os

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
		try:
			# Only worry about HTML for now
			if msg.get_content_type() is not None and "text/html" in msg.get_content_type():
				
				# Just decode (probably un-gzip) and then re-encode the response contents
				contents = msg.get_decoded_content()
				msg.content = contents
				msg.encode(msg.headers["content-encoding"][0])

		except Exception as e:
			print e

		msg.reply()

config = proxy.ProxyConfig(
	cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
)
server = proxy.ProxyServer(config, 8080)
m = LocalMaster(server)
m.run()

