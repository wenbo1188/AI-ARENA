# The UNKNOWN servant: a tall hooded figure made of shadow. Near-black body, a cold silver rim light from behind,
# the cloak's lower half breaking up into smoke and motes, two faint eye glints inside the hood.
# Writes servant_unknown_a.png (512x768 RGBA, straight alpha) framed like the other servants
# (feet ~92% down, figure ~80% of the height).
import sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
out = sys.argv[1]
W, H = 1024, 1536
rng = np.random.default_rng(11)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

def bez(p0, p1, p2, p3, n=48):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(lambda p: np.array(p, float), (p0, p1, p2, p3))
    return ((1-t)**3*p0 + 3*(1-t)**2*t*p1 + 3*(1-t)*t**2*p2 + t**3*p3).tolist()
def poly(points, sc=2):
    m = Image.new('L', (W * sc, H * sc), 0)
    ImageDraw.Draw(m).polygon([(x * sc, y * sc) for x, y in points], fill=255)
    return np.asarray(m.resize((W, H), Image.LANCZOS), np.float32) / 255

def vnoise(sx, sy, seed):
    r = np.random.default_rng(seed)
    gw, gh = int(W / sx) + 3, int(H / sy) + 3
    g = r.random((gh, gw)).astype(np.float32)
    fx, fy = xx / sx, yy / sy
    x0, y0 = fx.astype(int), fy.astype(int)
    tx, ty = fx - x0, fy - y0
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a, b, c, d = g[y0, x0], g[y0, x0 + 1], g[y0 + 1, x0], g[y0 + 1, x0 + 1]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty
def fbm(sx, sy, seed, oct=5):
    s, amp, tot = 0, 1, 0
    for o in range(oct):
        s = s + amp * vnoise(sx / 2 ** o, sy / 2 ** o, seed + o); tot += amp; amp *= 0.5
    return s / tot

# a tall, slim figure: hood, narrow shoulders, cloak closed at the chest, opening and flaring toward the ground,
# the right side swept back a little as if by wind
cx = 512
pts = []
pts += bez((cx - 6, 196), (cx + 52, 196), (cx + 86, 262), (cx + 84, 338))            # hood crown, right
pts += bez((cx + 84, 338), (cx + 96, 372), (cx + 150, 392), (cx + 170, 430))         # shoulder right
pts += bez((cx + 170, 430), (cx + 196, 520), (cx + 196, 640), (cx + 186, 760))       # arm under the cloak
pts += bez((cx + 186, 760), (cx + 200, 960), (cx + 268, 1180), (cx + 330, 1400))     # cloak, swept back
pts += bez((cx + 330, 1400), (cx + 200, 1430), (cx + 60, 1424), (cx - 40, 1430))     # hem (will dissolve)
pts += bez((cx - 40, 1430), (cx - 140, 1432), (cx - 220, 1420), (cx - 262, 1404))
pts += bez((cx - 262, 1404), (cx - 230, 1200), (cx - 196, 980), (cx - 186, 770))     # cloak left
pts += bez((cx - 186, 770), (cx - 192, 640), (cx - 188, 520), (cx - 160, 432))
pts += bez((cx - 160, 432), (cx - 140, 392), (cx - 92, 372), (cx - 80, 338))         # shoulder left
pts += bez((cx - 80, 338), (cx - 84, 260), (cx - 56, 198), (cx - 6, 196))            # hood, left
body = poly(pts)
# a long blade held low at the right side, point to the ground: the one thing that says "servant"
hx, hy, tx, ty = cx + 176, 742, cx + 262, 1416
ux, uy = (tx - hx), (ty - hy); L = math.hypot(ux, uy); ux, uy = ux / L, uy / L; nx, ny = -uy, ux
def at(d, w): return (hx + ux * d + nx * w, hy + uy * d + ny * w)
blade = poly([at(30, -13), at(30, 13), at(L - 80, 11), at(L, 0), at(L - 80, -11)])
guard = poly([at(10, -40), at(10, 40), at(26, 40), at(26, -40)])
grip = poly([at(-56, -7), at(-56, 7), at(14, 7), at(14, -7)]) + poly([at(-72, -11), at(-72, 11), at(-56, 11), at(-56, -11)])
sword = np.maximum(np.maximum(blade, guard), grip)
fuller = poly([at(44, -1.6), at(44, 1.6), at(L - 90, 1.2), at(L - 90, -1.2)])
face = poly(bez((cx - 2, 248), (cx + 40, 252), (cx + 54, 300), (cx + 46, 346)) + bez((cx + 46, 346), (cx + 30, 372), (cx - 30, 372), (cx - 44, 346))
            + bez((cx - 44, 346), (cx - 52, 300), (cx - 40, 252), (cx - 2, 248)))
face = np.asarray(Image.fromarray((face * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255

# smoke: the silhouette's edge wanders with noise (more toward the hem), and the lower cloak fades out in streaks
# that rise like smoke; a few wisps trail above the hem
n1 = fbm(70, 50, 3)
n2 = fbm(22, 140, 9)            # vertical streaks
low = np.clip((yy - 1000) / 430, 0, 1)
dx = (n1 - 0.5) * (8 + 70 * low)
dy = (fbm(80, 60, 5) - 0.5) * (4 + 40 * low)
src_x = np.clip(xx + dx, 0, W - 1).astype(int); src_y = np.clip(yy + dy, 0, H - 1).astype(int)
bodyd = body[src_y, src_x]
fadeY = yy + (n2 - 0.5) * 260 + (n1 - 0.5) * 80
fade = 1 - np.clip((fadeY - 1190) / 240, 0, 1) ** 1.3
alpha = np.clip(bodyd * fade, 0, 1)
soft = np.asarray(Image.fromarray((body * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(16)), np.float32) / 255
wisp = soft * np.clip((yy - 1150) / 300, 0, 1) * np.clip((1480 - yy) / 120, 0, 1) * np.clip((n2 - 0.55) * 4, 0, 1)
alpha = np.maximum(alpha, wisp * 0.45)
# the rim: the edge band of the alpha, lit from behind and up-left
A = Image.fromarray((alpha * 255).astype(np.uint8))
e1 = np.asarray(A.filter(ImageFilter.MinFilter(5)), np.float32) / 255
e2 = np.asarray(A.filter(ImageFilter.MinFilter(15)), np.float32) / 255
rim = np.clip(alpha - e1, 0, 1) + 0.22 * np.clip(alpha - e2, 0, 1)
light = np.clip(0.45 + 0.6 * (-(xx - cx) / 300) + 0.35 * (-(yy - 600) / 700), 0.2, 1.3)
rim = rim * light * (1 - 0.7 * low)
# cloth: barely-there folds inside
folds = 0.5 + 0.5 * np.sin((xx - cx) / 26 + 3 * fbm(200, 300, 21) + (yy / 900) ** 2 * 2)
cloth = folds ** 6 * np.clip((yy - 420) / 200, 0, 1) * (1 - low) * 0.5
# the mantle's hem across the chest and the cloak's parting below it catch a little light
mant_y = 560 + 0.0011 * (xx - cx) ** 2
mant = (np.exp(-((yy - mant_y) / 2.0) ** 2) * 0.5 + np.exp(-((yy - mant_y - 14) / 16) ** 2) * 0.25) * np.clip((172 - np.abs(xx - cx)) / 40, 0, 1) * light * 0.6
part_x = cx + 6 + (yy - 600) * 0.03 + (yy > 600) * 0
part = np.exp(-((xx - part_x) / 2.0) ** 2) * np.clip((yy - 600) / 80, 0, 1) * np.clip((1100 - yy) / 400, 0, 1) * 0.35
cloth = cloth + 0.0

rimc = np.array([0.80, 0.85, 1.0])
col = np.array([0.006, 0.007, 0.013])[None, None] * (1 + 2.5 * cloth[..., None])
col = col + rimc * (rim * 1.25 + (mant * 0.5 + part * 0.35) * alpha)[..., None]
col = col + np.array([0.10, 0.12, 0.2]) * (wisp * 0.6)[..., None]
col = col * (1 - face[..., None] * 0.85)

for ex in (cx - 17, cx + 17):                          # two cold glints in the hood
    g = np.exp(-(((xx - ex) / 6.5) ** 2 + ((yy - 312) / 2.6) ** 2))
    col += np.array([0.85, 0.92, 1.0]) * (g * 1.4)[..., None]
    alpha = np.maximum(alpha, g)
col = col * alpha[..., None]                           # premultiplied from here

# a faint cold halo outside the edge, so the shape reads on black
halo = np.asarray(A.filter(ImageFilter.GaussianBlur(22)), np.float32) / 255
halo = np.clip(halo - alpha, 0, 1) * light * (1 - 0.5 * low) * 0.35
col += rimc * (halo * 0.55)[..., None]
alpha = np.clip(alpha + halo * 0.4, 0, 1)

# motes drifting up off the smoke
for _ in range(150):
    x = cx + rng.normal(0, 150); y = 1430 - rng.random() ** 1.8 * 700
    if soft[int(min(H - 1, y)), int(np.clip(x, 0, W - 1))] < 0.05 or y < 1150: continue
    r = 1.0 + rng.random() * 1.8
    x0, y0 = int(x) - 7, int(y) - 7
    if x0 < 0 or y0 < 0 or x0 + 14 >= W or y0 + 14 >= H: continue
    sl = (slice(y0, y0 + 14), slice(x0, x0 + 14))
    g = np.exp(-(((xx[sl] - x) / r) ** 2 + ((yy[sl] - y) / r) ** 2)) * (0.3 + 0.7 * rng.random()) * np.clip((y - 700) / 300, 0, 1)
    col[sl] += rimc * g[..., None] * 0.9
    alpha[sl] = np.clip(alpha[sl] + g * 0.9, 0, 1)

a = np.clip(alpha, 1e-4, 1)[..., None]
rgb = np.clip(col / a, 0, 1) ** (1 / 2.2)
im = Image.fromarray((np.dstack([rgb, alpha]) * 255 + 0.5).astype(np.uint8), 'RGBA').resize((512, 768), Image.LANCZOS)
im.save(out)
for name, bgc in (('prev_blue', (40, 40, 60)), ('prev_black', (0, 0, 0)), ('prev_warm', (90, 60, 30))):
    bg = Image.new('RGBA', im.size, bgc + (255,)); bg.alpha_composite(im); bg.convert('RGB').save(out.replace('.png', f'_{name}.png'))
