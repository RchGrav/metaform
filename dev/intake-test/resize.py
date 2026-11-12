import sys,os,glob
from PIL import Image, ImageOps
T=sys.argv[1]; out=T+"/small/sigma-fp2-review-samples"
n=0
for f in sorted(glob.glob(T+"/photos/*.jpg")):
    im=ImageOps.exif_transpose(Image.open(f)); im.thumbnail((1280,1280), Image.LANCZOS)
    im.convert("RGB").save(os.path.join(out,os.path.basename(f)),"JPEG",quality=85); n+=1
print(n,"files; last size",im.size)
