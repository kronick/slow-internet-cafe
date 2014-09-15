#coding=utf-8

#TODO: WEBP isn't working... OpenCV doesn't like loading the images?
# Good sites:
# http://mashable.com/2014/08/27/survivor-season-29-cast/
# https://upload.wikimedia.org/wikipedia/commons/1/1d/Woman_Montage_%281%29.jpg
# https://upload.wikimedia.org/wikipedia/commons/d/d9/Men_montage_2.jpg


from libmproxy import controller, proxy
from libmproxy.proxy.config import ProxyConfig
from libmproxy.proxy.server import ProxyServer
from libmproxy import platform
from libmproxy.proxy.primitives import TransparentUpstreamServerResolver
TRANSPARENT_SSL_PORTS = [443, 8433]

from utils import concurrent, generate_trust, get_logger

import os,sys
import math
import threading
import cStringIO
import cv2, numpy
from random import randint, uniform, normalvariate

from PIL import Image, ImageDraw

import time
from config import global_config

log = get_logger("ERASURE")

#eye_cascade = cv2.CascadeClassifier('data/haarcascade_eye.xml')

dot = Image.open("../static/img/face-dot-white.png")

def processedFace(data, ext):
    # Because we're running asynchronously, we need to load the classifier for each image
    face_cascade = cv2.CascadeClassifier('data/haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier('data/haarcascade_eye.xml')
    male_model = cv2.createFisherFaceRecognizer()
    male_model.load("data/male_model.yml")

    # OpenCV wants a file-like object so create one from the data string
    input_image = cStringIO.StringIO(data)
    input_image.seek(0)
    input_array = numpy.asarray(bytearray(input_image.read()), dtype=numpy.uint8)
    gray = cv2.imdecode(input_array, cv2.CV_LOAD_IMAGE_GRAYSCALE)
    input_image.seek(0)


    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    # if(len(faces) == 0):
    #     log.debug("No faces.")
    # else:
    #     log.debug("{} faces.".format(len(faces)))

    # Identify the male faces
    male_faces = []
    female_faces = []
    for(x,y,w,h) in faces:
        # Classify face as male or female
        crop = w * .2
        im = gray[y+crop:y+h, x+crop:x+w-crop]
        im = cv2.resize(im, (120,120))

        [p_label, p_confidence] = male_model.predict(numpy.asarray(im))

        if p_label == 1:
            male_faces.append((x,y,w,h))
        else:
            female_faces.append((x,y,w,h))

    # if(len(male_faces) == 0):
    #     log.debug("No faces are male.")
    # else:
    #     log.info("Censoring {} male faces.".format(len(male_faces)))

    # Don't do any more processing if no male faces are found
    if len(faces) == 0:
        return None

    # Use PIL to censor the image
    image = Image.open(input_image)

    draw = ImageDraw.Draw(image)

    original_image = image.copy()
    for(x,y,w,h) in male_faces:
        # scale = uniform(3,5)
        # w_o = w
        # w =  int(w * scale)
        # x -= int(w_o * (scale - 1) / 2)
        # y -= int(w_o * (scale - 1) / 2)
        # scaleddot = dot.copy().resize((w,w), Image.ANTIALIAS)
        # #scaleddot = scaleddot.rotate(randint(0,360))
        # image.paste(scaleddot, (x, y), scaleddot)

        # Mix-n-match some random patches
        s = w / 12
        for i in range(0,400):
            #left, upper, right, lower
            left = randint(x,x+w-s)
            right = left + s
            #right = randint(left+1, min(left+4, x+w))
            upper = randint(y,y+h-s)
            lower = upper + s
            #lower = randint(upper+1, min(upper+4, y+h))

            patch = original_image.crop((left,upper,right,lower))
            #patch.load()
            patch_width = right-left
            patch_height = lower-upper
            patch_x = randint(x, x+w-patch_width)
            patch_y = randint(y, y+h-patch_height)

            paste_angle = uniform(0,2*math.pi)
            paste_r = randint(0,w/2)
            #paste_r = normalvariate(0, w/3)
            #patch_x = int(paste_r * math.cos(paste_angle) + x + w/2)
            #patch_y = int(paste_r * math.sin(paste_angle) + y + h/2)

            patch_x = int(((patch_x - w) / s + 0.5) * s + w)
            patch_y = int(((patch_y - h) / s + 0.5) * s + h)

            #print("{} x {}".format(patch_width, patch_height))

            image.paste(patch, (patch_x, patch_y))
            #draw.rectangle([patch_x,patch_y, patch_x+patch_width, patch_y+patch_height], outline=(0,0,255))

    original_image = image.copy()
            
    for(x,y,w,h) in faces:
        draw.rectangle([x+2,y+2, x+w-2, y+h-2], outline=(100,255,100))
        #pass
    del(draw)

    image = Image.blend(image, original_image, 0.5)



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
        accept =  "".join(msg.headers["accept"])
        if "image/jpeg" in accept or "image/webp" in accept or "image/png" in accept:
            del(msg.headers["if-modified-since"])
            del(msg.headers["if-none-match"])

        msg.reply()

    @concurrent    
    def handle_response(self, msg):
        # First see if we need to show the HTTPS user agreement/certificate download
        client_ip = msg.flow.client_conn.address.address[0]
        router_ip = global_config["router_IPs"]["erasure"]
        if generate_trust(msg, client_ip, router_ip):
            return
        # Only worry about images
        content_type = " ".join(msg.headers["content-type"])
        if msg.code != 200 or content_type is None or not ("image/jpeg" in content_type or "image/webp" in content_type or "image/png" in content_type):
            return

        try:
            req = msg.flow.request
            url = u"{}://{}{}".format(req.get_scheme(), u"".join(req.headers["host"]), req.path)

            ext = "JPEG" if "image/jpeg" in content_type else "PNG" if "image/png" in content_type else "WEBP"
            content = msg.get_decoded_content()
            if len(content) < 100:
                return
                
            censored = processedFace(content, ext)
            msg.content = censored or msg.content
            
            # Force uncompressed response
            if censored:
                log.info(u"Faces found in image: {}".format(url))

                msg.headers["content-encoding"] = [""]
            # Don't cache
            msg.headers["Pragma"] = ["no-cache"]
            msg.headers["Cache-Control"] = ["no-cache, no-store"]

        except Exception as e:
            log.exception(u"<{}> processing {} ".format(type(e).__name__, url))

        #log.debug("Replying with image...")
        

if global_config["transparent_mode"]:
    config = ProxyConfig(
        confdir = "~/.mitmproxy",
        mode = "transparent"
    )
else:
    config = ProxyConfig(confdir = "~/.mitmproxy")


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
server = ProxyServer(config, port)
m = FacesMaster(server)
log.info("---- ERASURE proxy running on port {} ----".format(port))
m.run()