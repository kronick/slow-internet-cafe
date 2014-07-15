from libmproxy import controller, proxy
import os
import threading
import requests
import base64
import httplib


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

		# Don't allow cached HTML requests, but go ahead and cache CSS, JS, images, etc
		if "image/jpeg" in "".join(msg.headers["accept"]) or "image/webp" in "".join(msg.headers["accept"]):
			del(msg.headers["if-modified-since"])
			del(msg.headers["if-none-match"])

		msg.reply()

	def handle_response(self, msg):
		# Process replies from Internet servers to users
		if msg.headers["content-type"] == ["image/jpeg"] and msg.code == 200:
			try:
				# Make this threaded:
				reply = msg.reply
				m = msg
				msg.reply = controller.DummyReply()
				if hasattr(reply, "q"):
					msg.reply.q = reply.q

				def run():

					#f = open("tmp_o.jpg", "w+")
					#f.write(msg.content)
					#f.close()



					# Make a POST request with multipart/form and following fields:
					# filename: whatever.jpg
					# image_content: base_64 encoded data with "-_" instead of "+/"
					# encoded_image: None
					# image_url: None
					# And original headers

					filename = "similar.jpg"
					image_content = base64.b64encode(msg.content, "-_")

					t = upload_to_google(image_content)

					url = "http://httpbin.org/post"
					#url = "http://images.google.com/searchbyimage/upload"
					# r = requests.post(url,
					# 				  #files={"filename": filename, "image_content": image_content, "image_url": "", "encoded_image": ""},

					# 				  files = "123",

					# 				  # headers = {"host": "images.google.com",
					# 				  # 			 "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
					# 				  # 			 "proxy-connect": "keep-alive",
					# 				  # 			 "cache-control": "max-age=0",
					# 				  # 			 "origin": "http://images.google.com",
					# 				  # 			 #"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
					# 				  # 			 #"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
					# 				  # 			 "x-client-data": "CMO1yQEIhLbJAQiitskBCKm2yQEIwbbJAQi4iMoBCOyIygEI9pPKAQ==",
					# 				  # 			 #"content-type": "multipart/form-data; boundary=----WebKitFormBoundaryE4lHG8YtkYgZeGXW",
					# 				  # 			 "referer": "http://images.google.com/",
					# 				  # 			 "accept-encoding": "gzip,deflate,sdch",
					# 				  # 			 "accept-language": "en-US,en;q=0.8",
					# 				  # 			 #"cookie": "PREF=ID=4a50a001b91fd6c2:FF=0:TM=1405427880:LM=1405427880:S=hgq1NqlFuP8OAY5h; NID=67=Bk33psfCcyeOkaBVQMSDK5KcprebrMv7ycHiMMKH7WQctb4QMEaggbPjwEsAb5c_bSFikbOsPe2PzBT0G8MJZZTVTAMop93ATqp0Tbul_IU55mEp2pxijVUTnnGdym1H"
					# 				  # 			 "cookie": "OGPC=4061135-1:4061130-22:; OGP=-4061130:; PREF=ID=7f5416533b04f0e7:U=0b7757f53644dbcf:FF=0:LD=en:CR=2:TM=1395716670:LM=1405374050:DV=kmdYOgebfREditOmwYZI6u3jk1bgigI:GM=1:S=8m2OYPAR8yWMobGc; NID=67=WLxGTLzthckcySqP4YJ6b1rh5WrV4Na1eZev3N2BpXxCLpZi0kQPHJzaQF6ozGJQj9Ws1DKaRDbQ5r7-F_PLi3sThrfSDLGBmQf2DzsC36WS9tcSUOGXCE_116R3U_-Z9VjERff-3V07DM9DWY0qCSZG9Yo4lxHjMMhSWAh1y9kGUOLfThM"
					# 				  # 			 }

					# 				  headers = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
					# 				  			 "proxy-connect": "keep-alive",
					# 				  			 "cache-control": "max-age=0",
					# 				  			 #"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
					# 				  			 #"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
					# 				  			 "x-client-data": "CMO1yQEIhLbJAQiitskBCKm2yQEIwbbJAQi4iMoBCOyIygEI9pPKAQ==",
					# 				  			 #"content-type": "multipart/form-data; boundary=----WebKitFormBoundaryE4lHG8YtkYgZeGXW",
					# 				  			 "accept-encoding": "gzip,deflate,sdch",
					# 				  			 "accept-language": "en-US,en;q=0.8",
					# 				  			 #"cookie": "PREF=ID=4a50a001b91fd6c2:FF=0:TM=1405427880:LM=1405427880:S=hgq1NqlFuP8OAY5h; NID=67=Bk33psfCcyeOkaBVQMSDK5KcprebrMv7ycHiMMKH7WQctb4QMEaggbPjwEsAb5c_bSFikbOsPe2PzBT0G8MJZZTVTAMop93ATqp0Tbul_IU55mEp2pxijVUTnnGdym1H"
					# 				  			 "cookie": "OGPC=4061135-1:4061130-22:; OGP=-4061130:; PREF=ID=7f5416533b04f0e7:U=0b7757f53644dbcf:FF=0:LD=en:CR=2:TM=1395716670:LM=1405374050:DV=kmdYOgebfREditOmwYZI6u3jk1bgigI:GM=1:S=8m2OYPAR8yWMobGc; NID=67=WLxGTLzthckcySqP4YJ6b1rh5WrV4Na1eZev3N2BpXxCLpZi0kQPHJzaQF6ozGJQj9Ws1DKaRDbQ5r7-F_PLi3sThrfSDLGBmQf2DzsC36WS9tcSUOGXCE_116R3U_-Z9VjERff-3V07DM9DWY0qCSZG9Yo4lxHjMMhSWAh1y9kGUOLfThM"
					# 				  			 }
					# 				 )

					# #print r.request.headers

					# print r.text

					#print msg.request.headers
					#print "{}: {}".format(r.status_code, r.text.encode("utf-8"))
					soup = BeautifulSoup(t)
					print soup.prettify()
					#print soup.title
					#print soup.find_all(id="resultStats")
					#for link in soup.find_all("a"):
					#	print link.get("href")
					#print soup.text


				threading.Thread(target=run).start()


			except Exception as e:
				print "Error processing image: {}".format(e)

		msg.reply()

def upload_to_google(image_content):
	host = "images.google.com"
	selector = "/searchbyimage/upload"

	heads = {"host": "images.google.com",
		 "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
		 "proxy-connect": "keep-alive",
		 "cache-control": "max-age=0",
		 "origin": "http://images.google.com",
		 #"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
		 "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2)",
		 "x-client-data": "CMO1yQEIhLbJAQiitskBCKm2yQEIwbbJAQi4iMoBCOyIygEI9pPKAQ==",
		 #"content-type": "multipart/form-data; boundary=----WebKitFormBoundaryE4lHG8YtkYgZeGXW",
		 "referer": "http://images.google.com/",
		 "accept-encoding": "gzip,deflate,sdch",
		 "accept-language": "en-US,en;q=0.8",
		 
		 #"cookie": "OGPC=4061135-1:4061130-22:; OGP=-4061130:; PREF=ID=7f5416533b04f0e7:U=0b7757f53644dbcf:FF=0:LD=en:CR=2:TM=1395716670:LM=1405374050:DV=kmdYOgebfREditOmwYZI6u3jk1bgigI:GM=1:S=8m2OYPAR8yWMobGc; NID=67=WLxGTLzthckcySqP4YJ6b1rh5WrV4Na1eZev3N2BpXxCLpZi0kQPHJzaQF6ozGJQj9Ws1DKaRDbQ5r7-F_PLi3sThrfSDLGBmQf2DzsC36WS9tcSUOGXCE_116R3U_-Z9VjERff-3V07DM9DWY0qCSZG9Yo4lxHjMMhSWAh1y9kGUOLfThM"
		 "cookie": "PREF=ID=d15bb57ccd5b6658:FF=0:TM=1405432071:LM=1405432071:S=EU8w9yOCNeiEdy5P; NID=67=aZIWgJZU6Qsy9NPyrJm9J9O605s3xkqRE_Ncz_Z3C9TszihJmjBr_atcTrJyi67U8D5YeOuCisDeJ4O3_nhOw7SzpMpPcUWqdM-GTkAVYLPxXN8EXX4mhjtZIQxUfXmh"
		 }

	BOUNDARY = "----WebKitFormBoundaryE4lHG8YtkYgZeGXW"
	CRLF = "\r\n"
	L = []
	L.append(BOUNDARY)
	L.append('Content-Disposition: form-data; name="image_url"')
	L.append('')
	L.append('')
	L.append(BOUNDARY)
	L.append('Content-Disposition: form-data; name="encoded_image"; filename=""')
	L.append('Content-Type: application/octet-stream')
	L.append('')
	L.append('')
	L.append(BOUNDARY)
	L.append('Content-Disposition: form-data; name="image_content"')
	L.append('')
	L.append(image_content)
	L.append(BOUNDARY)
	L.append('Content-Disposition: form-data; name="filename"')
	L.append('')
	L.append("file.jpg")
	L.append(BOUNDARY)

	body = CRLF.join(L)

	content_type = 'multipart/form-data; boundary={}'.format(BOUNDARY)
	
	h = httplib.HTTP(host)
	h.putrequest('POST', selector)
	h.putheader('content-type', content_type)
	h.putheader('content-length', str(len(body)))
	for k in heads:
		h.putheader(k, heads[k])

	h.endheaders()
	h.send(body)

	#print h.getreply()
	errcode, errmsg, headers = h.getreply()

	if(errcode == 302):
		print  h.file.read()
		r = requests.get(headers["location"], headers=heads)
		return r.text

	#print headers["location"]
	else:
		return h.file.read()

config = proxy.ProxyConfig(
	cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
)
server = proxy.ProxyServer(config, 8080)
m = SimilarMaster(server)
m.run()

