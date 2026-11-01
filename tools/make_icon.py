"""Draw the original app icon at high resolution and export Windows/web sizes."""
from pathlib import Path
from PIL import Image,ImageDraw
import math

root=Path(__file__).resolve().parents[1]/'web'
scale=4
image=Image.new('RGBA',(256*scale,256*scale))
draw=ImageDraw.Draw(image)
def box(coords):return tuple(round(v*scale) for v in coords)
def line(points,color,width):draw.line([(round(x*scale),round(y*scale)) for x,y in points],fill=color,width=width*scale)
draw.rounded_rectangle(box((4,4,252,252)),radius=54*scale,fill='#14191f',outline='#39414b',width=3*scale)
draw.ellipse(box((42,42,214,214)),outline='#f1f4f7',width=17*scale)
draw.arc(box((25,25,231,231)),200,325,fill='#ffb05a',width=7*scale)
for angle in (207,232,257,282,307):
    theta=math.radians(angle)
    line([(128+110*math.cos(theta),128+110*math.sin(theta)),(128+118*math.cos(theta),128+118*math.sin(theta))],'#ffb05a',4)
line([(52,116),(104,130),(128,201)],'#f1f4f7',15)
line([(204,116),(152,130),(128,201)],'#f1f4f7',15)
draw.ellipse(box((100,100,156,156)),fill='#ffb05a')
draw.ellipse(box((115,115,141,141)),fill='#14191f')
draw.ellipse(box((180,174,246,240)),fill='#ffb05a',outline='#14191f',width=6*scale)
line([(200,207),(226,207)],'#14191f',6);line([(213,194),(213,220)],'#14191f',6)
image=image.resize((256,256),Image.Resampling.LANCZOS)
image.save(root/'icon.png')
image.save(root/'icon.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
