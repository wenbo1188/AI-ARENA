import sys, os
from PIL import Image
from concurrent.futures import ProcessPoolExecutor
src, dst = sys.argv[1:3]; os.makedirs(dst, exist_ok=True)
def one(f): Image.open(os.path.join(src, f)).convert('RGB').save(os.path.join(dst, f[:-4] + '.jpg'), quality=90)
with ProcessPoolExecutor(4) as ex: list(ex.map(one, sorted(os.listdir(src))))
print(dst, len(os.listdir(dst)))
