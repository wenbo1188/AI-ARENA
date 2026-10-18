import os, sys, numpy as np
from PIL import Image
root='film/public/footage'
for c in sys.argv[1:]:
    fs=sorted(os.listdir(f'{root}/{c}'))
    prev=None; d=[]
    for f in fs:
        im=Image.open(f'{root}/{c}/{f}'); im.draft('L',(240,135)); a=np.asarray(im.convert('L').resize((160,90)),np.float32)
        d.append(0 if prev is None else np.abs(a-prev).mean()); prev=a
    d=np.array(d); lum=None
    top=np.argsort(-d)[:5]
    print(f'{c:16s} n={len(fs):3d} spikes', ' '.join(f'{i}:{d[i]:.1f}' for i in sorted(top)))
