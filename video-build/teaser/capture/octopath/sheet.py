import sys, os
from PIL import Image, ImageDraw
d = sys.argv[1]; step = int(sys.argv[2]); fs = sorted(os.listdir(d))
sel = fs[::step]; cols = 6; rows = (len(sel) + cols - 1) // cols
S = Image.new('RGB', (cols * 320, rows * 180))
for i, f in enumerate(sel):
    im = Image.open(os.path.join(d, f)).convert('RGB').resize((320, 180))
    ImageDraw.Draw(im).text((4, 4), f[:-4], fill=(255, 255, 0))
    S.paste(im, ((i % cols) * 320, (i // cols) * 180))
S.save(sys.argv[3], quality=80)
