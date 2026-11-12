import sys,glob,os
from PIL import Image, ImageDraw
T=sys.argv[1]; fs=sorted(glob.glob(T+"/n/photos/*.jpg"))
W=380; H=300; cols=5
for part,chunk in enumerate([fs[:20],fs[20:]]):
    rows=(len(chunk)+cols-1)//cols
    sheet=Image.new("RGB",(cols*W,rows*H),"black"); d=ImageDraw.Draw(sheet)
    for i,f in enumerate(chunk):
        im=Image.open(f); im.thumbnail((W-8,H-28))
        x=(i%cols)*W; y=(i//cols)*H
        sheet.paste(im,(x+(W-im.width)//2,y+24))
        d.text((x+6,y+4),os.path.basename(f),fill="yellow")
    sheet.save("%s/sheet%d.jpg"%(T,part+1),quality=80)
print("ok")
