from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer

import os
import cStringIO
import cv2
from random import randint, uniform

from PIL import Image

face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')

def processedFace(file):

  img = cv2.imread(file)
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

  faces = face_cascade.detectMultiScale(gray, 1.3, 5)

  if(len(faces) == 0):
  	print "No faces."
  else:
  	print "{} faces.".format(len(faces))

  # Don't do any more processing if no faces are found
  if len(faces) == 0:
  	return None

  # Use PIL to censor the image
  image = Image.open(file)
  dot = Image.open("face-dot-white.png")

  for(x,y,w,h) in faces:
  	scale = uniform(3,5)
  	w_o = w
  	w =  int(w * scale)
  	x -= int(w_o * (scale - 1) / 2)
  	y -= int(w_o * (scale - 1) / 2)
  	scaleddot = dot.copy().resize((w,w), Image.ANTIALIAS)
  	#scaleddot = scaleddot.rotate(randint(0,360))
  	image.paste(scaleddot, (x, y), scaleddot)
  image.save("tmp.jpg")
  f = open("tmp.jpg", 'r')
  o = f.read()
  f.close()

  return o

  # for(x,y,w,h) in faces:
  #   cv2.circle(img, (x+w/2, y+h/2), w, (100,100,240), -1, cv2.CV_AA)

  # cv2.imwrite("tmp.jpg", img)
  # f = open("tmp.jpg", 'r')
  # o = f.read()
  # f.close()

  # return o

class FacesMaster(controller.Master):
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
				f = open("tmp_o.jpg", "w+")
				f.write(msg.content)
				f.close()

				msg.content = processedFace("tmp_o.jpg") or msg.content
				
				# Don't cache
				msg.headers["Pragma"] = ["no-cache"]
				msg.headers["Cache-Control"] = ["no-cache, no-store"]

				#img = cv2.imread("tmp_o.jpg")
				#gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

				
				#cv2.imwrite("tmp.jpg", gray)
				#f = open("tmp.jpg", 'r')
				#msg.content = f.read()
				#f.close()

			except Exception as e:
				print "Error processing image: {}".format(e)

		msg.reply()

config = ProxyConfig(
	#cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
)
server = ProxyServer(config, 8080)
m = FacesMaster(server)
m.run()

