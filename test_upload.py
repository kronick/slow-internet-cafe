import os
import threading
import requests
import base64
import httplib
import json

from bs4 import BeautifulSoup

f = open("img.jpg", "r")
image_content = base64.b64encode(f.read(), "-_")
f.close()

filename = "img.jpg"

url = "http://images.google.com/searchbyimage/upload"

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

r = requests.post(url,
				  files={"image_url": "", "encoded_image": "", "image_content": image_content, "filename": filename},
				  headers = request_headers)



# Manually follow redirects
#while r.status_code == 302:
#	print "Redirect!"
#	r = requests.get(r.headers["location"], headers = request_headers, allow_redirects = False)


soup = BeautifulSoup(r.text)
print soup.title.text

for similar in soup.find(id="iur").find_all("li"):
	metadata = json.loads(similar.find(class_="rg_meta").text)
	print metadata["ou"]
