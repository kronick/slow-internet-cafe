import cv2
import sys
from os import listdir
from os.path import isfile, join

def processFace(file):
  #face_cascade = cv2.CascadeClassifier('haarcascade_profileface.xml')
  face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
  eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')

  img = cv2.imread(file)
  gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

  #faces = face_cascade.detectMultiScale(gray, 1.2, 1)
  faces = face_cascade.detectMultiScale(gray, 1.3, 3)

  if(len(faces) == 0):
    print "No faces."
  else:
    print "{} faces.".format(len(faces))

  for(x,y,w,h) in faces:
    cv2.circle(img, (x+w/2, y+h/2), w, (100,100,240), -1, cv2.CV_AA)


  cv2.imwrite("tmp.jpg", img)
  f = open("tmp.jpg", 'r')
  o = f.read()
  f.close()

  cv2.imshow('img',img)
  cv2.waitKey(0)
  cv2.destroyAllWindows()

if __name__ == "__main__":
  if len(sys.argv) > 1:
    if isfile(sys.argv[1]):
      processFace(sys.argv[1])
    else:
      files = [ f for f in listdir(sys.argv[1]) if isfile(join(sys.argv[1],f))]
      for f in files:
        processFace(join(sys.argv[1],f))

  else:
    print "Must specify input filename."
