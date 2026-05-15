from PIL import Image
from time import sleep
img = Image.open(r'C:\Users\skfre\lpthw\1semestprojekt\interessant.jpg')

pixels = img.load()
width, height = img.size

pixelx = 0
pixely = 0
pixelx2 = 0
pixely2 = 0
pixel_values = 0
vaerdi = 0
# hele billedet
for i in range(118):
    pixelx = 0
    pixely += 1
    for i in range(119):
        pixel_values += sum(pixels[pixelx,pixely])
        pixelx += 1
        
        
print(pixel_values)    


#første halvdel af billede
for i in range(118):
    pixelx2 = 0
    pixely2 += 1
    for i in range(59):
        vaerdi += sum(pixels[pixelx2,pixely2])
        pixelx2 += 1

print(vaerdi)
#anden halvdel af billede
pixelx3 = 0
pixely3 = 0
vaerdi2 = 0

for i in range(118):
    pixelx3 = 60
    pixely3 += 1
    for i in range(59):
        vaerdi2 += sum(pixels[pixelx3,pixely3])
        pixelx3 +=1
print(vaerdi2)