from PIL import Image
from time import sleep
import random
img = Image.open(r'C:\Users\skfre\lpthw\1semestprojekt\test.png')

pixels = img.load()
width, height = img.size

pixelx = 0
pixely = 0

# hele billedet
for i in range(647):
    pixelx = 0
    pixely += 1
    for i in range(300):
        pixels[pixelx,pixely] = (random.randrange(0,255),random.randrange(0,255),random.randrange(0,255))
        pixelx += 1
img.show()
        
