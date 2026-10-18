# Builds the 1987 rocket-trooper servant cards for the rift scene from the CodeSide kit v1.2 "Shinjuku 1987" atlases
import os
# (red-team operative, standing pose, plus the kit's rocket launcher on the shoulder). Outputs a still card and a firing
# card (muzzle flash + backblast) with the same canvas and feet pivot, facing right like the old cs_unit1.png.
import sys
from PIL import Image, ImageDraw
SRC = os.environ.get('ARENA_ROOT', '/mnt/project-files/arena') + '/arena/games/codeside/assets/shinjuku/'
OUT = sys.argv[1]
act = Image.open(SRC + 'actors.png').convert('RGBA')
itm = Image.open(SRC + 'items.png').convert('RGBA')

def crop(im, box):
    c = im.crop(box)
    a = c.split()[3].point(lambda v: 255 if v > 96 else 0)
    return c.crop(a.getbbox())

body = crop(act, (0, 0, 310, 512))
tube = crop(itm, (0, 512, 485, 512 + 512))
BH = body.height
S = 0.80 * BH / tube.width            # launcher length ≈ 0.8 body height (shoulder-carried)
tube = tube.resize((round(tube.width * S), round(tube.height * S)), Image.LANCZOS)
print('body', body.size, 'tube', tube.size)

PAD_L, PAD_R, PAD_T = 170, 230, 40
W = PAD_L + body.width + PAD_R
H = PAD_T + BH + 8
bx, by = PAD_L, PAD_T
# launcher: tube top sits at the operative's shoulder line, grip near the front fist, muzzle well forward
shoulder_y = by + round(0.41 * BH)
tx = bx + round(body.width * 0.62) - round(tube.width * 0.62)
ty = shoulder_y - round(tube.height * 0.28)

def card(fire):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if fire:   # backblast plume behind the tube
        d = ImageDraw.Draw(im)
        cy = ty + round(tube.height * 0.24)
        for k, (r, col) in enumerate([(46, (120, 110, 104, 150)), (34, (255, 150, 60, 220)), (20, (255, 230, 150, 255))]):
            x0 = tx - 10 - k * 6
            d.polygon([(x0 + 10, cy - r * 0.5), (x0 - r * 2.6, cy - r * 1.1), (x0 - r * 3.4, cy), (x0 - r * 2.6, cy + r * 1.1), (x0 + 10, cy + r * 0.5)], fill=col)
    im.alpha_composite(body, (bx, by))
    im.alpha_composite(tube, (tx, ty))
    # the near fist drawn over the grip so the hand holds the launcher
    fist = body.crop((round(body.width * 0.70), round(BH * 0.27), round(body.width * 0.98), round(BH * 0.38)))
    im.alpha_composite(fist, (tx + round(tube.width * 0.60) - fist.width // 2, ty + round(tube.height * 0.42)))
    if fire:   # muzzle flash: a hard-edged arcade star like the viewer's
        d = ImageDraw.Draw(im)
        mx, my = tx + tube.width - 4, ty + round(tube.height * 0.24)
        sz = 200
        star = [(mx, my), (mx + sz * .42, my - sz * .34), (mx + sz * .30, my - sz * .08), (mx + sz, my), (mx + sz * .30, my + sz * .08), (mx + sz * .42, my + sz * .34)]
        d.polygon(star, fill=(255, 179, 76, 255))
        s2 = [(x - (x - mx) * 0.45, my + (y - my) * 0.5) for x, y in star]
        d.polygon(s2, fill=(255, 242, 199, 255))
    # pixel grid: the atlas is drawn at ~5 px per art pixel; resample onto that grid and harden alpha
    q = 5
    small = im.resize((W // q, H // q), Image.BOX)
    a = small.split()[3].point(lambda v: 255 if v > 110 else 0)
    small.putalpha(a)
    return small

for fire, name in [(False, 'cs_trooper.png'), (True, 'cs_trooper_fire.png')]:
    c = card(fire)
    c.save(OUT + '/' + name)
print('card', W // 5, H // 5, 'feet y from bottom px', 8 // 5, 'body x0', bx // 5, 'body w', body.width // 5, 'body h', BH // 5)
