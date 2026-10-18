import os, sys
from PIL import Image, ImageDraw
root='film/public/footage'; out=sys.argv[1]; step=int(sys.argv[2]); clips=sys.argv[3:]
W,H=240,135; cols=12
rows=[]
for c in clips:
    fs=sorted(os.listdir(f'{root}/{c}'))[::step][:cols*2]
    for k in range(0,len(fs),cols): rows.append((c,fs[k:k+cols]))
S=Image.new('RGB',(W*cols,H*len(rows)))
for r,(c,fs) in enumerate(rows):
    for i,f in enumerate(fs):
        im=Image.open(f'{root}/{c}/{f}'); im.draft('RGB',(480,270)); im=im.convert('RGB').resize((W,H))
        ImageDraw.Draw(im).text((3,3),f'{c[4:]} {int(f[:5])}',fill=(255,255,0)); S.paste(im,(i*W,r*H))
S.save(out,quality=80)
