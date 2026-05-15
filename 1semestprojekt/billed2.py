from PIL import Image
from time import sleep
img = Image.open(r'C:\Users\skfre\lpthw\1semestprojekt\test.png')

pixels = img.load()
width, height = img.size

pixelx = 0
pixely = 0
pixelx2 = 0
pixely2 = 0
pixel_values = 0
vaerdi = 0
# hele billedet
for i in range(647):
    pixelx = 0
    pixely += 1
    for i in range(1151):
        pixel_values += sum(pixels[pixelx,pixely])
        pixelx += 1
        
        
print(round(pixel_values / 1000000))    


#første halvdel af billede
for i in range(647):
    pixelx2 = 0
    pixely2 += 1
    for i in range(576):
        vaerdi += sum(pixels[pixelx2,pixely2])
        pixelx2 += 1

print(round(vaerdi / 1000000))
#anden halvdel af billede
pixelx3 = 0
pixely3 = 0
vaerdi2 = 0

for i in range(647):
    pixelx3 = 576
    pixely3 += 1
    for i in range(576):
        vaerdi2 += sum(pixels[pixelx3,pixely3])
        pixelx3 +=1
print(round(vaerdi2 / 1000000))