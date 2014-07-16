# TODO:
# [ ] Limit number of requests/threads per user
# [ ] Better error handling/investigate crashes

from libmproxy import controller, proxy
import os
import threading
import requests
import base64
import httplib
import json


from bs4 import BeautifulSoup

from PIL import Image

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

		msg.reply()

	def handle_response(self, msg):
		# Process replies from Internet servers to users
		#print msg.request.headers
		#if msg.request.headers["X-Do-Not-Replace"]:
		#	print "Ignoring this image to avoid infinite loop..."

		if (msg.headers["content-type"] == ["image/jpeg"] or msg.headers["content-type"] == ["image/png"] or msg.headers["content-type"] == ["image/webp"] or msg.headers["content-type"] == ["image/gif"]) and msg.code == 200 and not msg.request.headers["X-Do-Not-Replace"]:
			try:
				# Make this threaded:
				reply = msg.reply
				m = msg
				msg.reply = controller.DummyReply()
				if hasattr(reply, "q"):
					msg.reply.q = reply.q

				def run():
					# [ ] Better error handling/investigate crashes
					# Make a POST request with multipart/form and following fields:
					# filename: whatever.jpg
					# image_content: base_64 encoded data with "-_" instead of "+/"
					# encoded_image: None
					# image_url: None
					# And original headers

					search_url = "http://images.google.com/searchbyimage/upload"
					filename = "similar.jpg"
					image_content = base64.b64encode(msg.content, "-_")
					
					request_headers = {
						 "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
						 "Proxy-Connection": "keep-alive",
						 "Cache-Control": "max-age=0",
						 "Origin": "http://images.google.com",
						 "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
						 "X-Client-Data": "CMO1yQEIhLbJAQiitskBCKm2yQEIwbbJAQi4iMoBCOyIygEI9pPKAQ==",
						 "Referer": "http://images.google.com/",
						 "Accept-Encoding": "gzip,deflate,sdch",
						 "Accept-Language": "en-US,en;q=0.8"
					}

					r = requests.post(search_url,
						files={"image_url": "", "encoded_image": "", "image_content": image_content, "filename": filename},
						headers = request_headers)

					try:
						soup = BeautifulSoup(r.text)
						
						similar_section = soup.find(id="iur")
						if(similar_section is not None):
							similar_elements = similar_section.find_all("li")

							similar_url = json.loads(similar_elements[0].find(class_="rg_meta").text)["ou"]

							print "Replacing with <{}>".format(similar_url)
							img = requests.get(similar_url, headers={"X-Do-Not-Replace": "True"})
							msg.content = img.content
					
							# Force uncompressed response
							msg.headers["content-encoding"] = [""]
							# And don't cache
							msg.headers["Pragma"] = ["no-cache"]
							msg.headers["Cache-Control"] = ["no-cache, no-store"]
						else:
							print "Could not find any similar images."

					except Exception as e:
						print e

					#print similar_url
					
					#print soup.text

					reply()


				threading.Thread(target=run).start()


			except Exception as e:
				print "Error processing image: {}".format(e)

		else:
			msg.reply()

config = proxy.ProxyConfig(
	cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
)
server = proxy.ProxyServer(config, 8080)
m = SimilarMaster(server)
m.run()

