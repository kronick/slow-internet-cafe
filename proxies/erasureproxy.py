#coding=utf-8

#TODO: WEBP isn't working... OpenCV doesn't like loading the images?

from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

from utils import concurrent

import os
import threading
import cStringIO
import cv2, numpy
from random import randint, uniform

from PIL import Image

import time

#eye_cascade = cv2.CascadeClassifier('data/haarcascade_eye.xml')

imgid = 0
TMP_DIR = "data/tmp/"


dot = Image.open("../static/img/face-dot-white.png")

def processedFace(data, ext):
    # Because we're running asynchronously, we need to load the classifier for each image
    face_cascade = cv2.CascadeClassifier('data/haarcascade_frontalface_default.xml')

    # OpenCV wants a file-like object so create one from the data string
    input_image = cStringIO.StringIO(data)
    input_image.seek(0)
    input_array = numpy.asarray(bytearray(input_image.read()), dtype=numpy.uint8)
    gray = cv2.imdecode(input_array, cv2.CV_LOAD_IMAGE_GRAYSCALE)
    input_image.seek(0)


    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if(len(faces) == 0):
        print "No faces."
    else:
        print "{} faces.".format(len(faces))

    # Don't do any more processing if no faces are found
    if len(faces) == 0:
        return None

    # Use PIL to censor the image
    image = Image.open(input_image)

    for(x,y,w,h) in faces:
        scale = uniform(3,5)
        w_o = w
        w =  int(w * scale)
        x -= int(w_o * (scale - 1) / 2)
        y -= int(w_o * (scale - 1) / 2)
        scaleddot = dot.copy().resize((w,w), Image.ANTIALIAS)
        #scaleddot = scaleddot.rotate(randint(0,360))
        image.paste(scaleddot, (x, y), scaleddot)
    
    image_buffer = cStringIO.StringIO()
    image.save(image_buffer, ext)
    return image_buffer.getvalue()


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

    @concurrent    
    def handle_response(self, msg):
        # Only worry about images
        content_type = " ".join(msg.headers["content-type"])
        if msg.code != 200 or content_type is None or not ("image/jpeg" in content_type or "image/webp" in content_type):
            return

        try:
            if "image/jpeg" in content_type:
                ext = "JPEG"
            else:
                ext = "WEBP"

            msg.content = processedFace(msg.get_decoded_content(), ext) or msg.content
            
            # Force uncompressed response
            msg.headers["content-encoding"] = [""]
            # Don't cache
            msg.headers["Pragma"] = ["no-cache"]
            msg.headers["Cache-Control"] = ["no-cache, no-store"]

        except Exception as e:
            print "Error processing image: {}".format(e)

        print "Replying with image..."
        

config = ProxyConfig(
    #certs = [os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")]
    confdir = "~/.mitmproxy",
    #mode = "transparent"
    #http_form_in = "relative",
    #http_form_out = "relative",
    #get_upstream_server = TransparentUpstreamServerResolver(platform.resolver(), TRANSPARENT_SSL_PORTS)
)
#config = None
server = ProxyServer(config, 8080)
m = FacesMaster(server)
print "Proxy server loaded."
m.run()

