import json, sys, glob
import os
sys.path.insert(0, os.environ.get('ARENA_ROOT', '/mnt/project-files/arena') + '')
from arena.games.octopath import data as D
for fn in sorted(glob.glob('m/m*.json')):
    if 'v10' in fn: continue
    R = json.load(open(fn)); M = R['meta']; P = M['picks']
    for i, f in enumerate(R['frames']):
        ev = f.get('ev', []); cur = None; sk = None; bp = 0; dmg = 0; brk = 0; ko = 0; lat = 0; nh = 0
        for e in ev:
            k = e.get('e')
            if k == 'turn': cur = e['u']
            elif k == 'skill': sk = e['s']
            elif k == 'boost': bp = e['n']
            elif k == 'latent': lat = 1
            elif k == 'hit' and cur and e.get('u') == cur: dmg += e['d']; nh += 1
            elif k == 'break': brk += 1
            elif k == 'ko': ko += 1
        if not sk or not cur: continue
        trav = P[cur[0]][cur[1]]; T = D.TRAVELERS[trav]
        S = D.SKILLS.get(sk) or D.LATENT_SKILLS.get(sk) or {}
        native = S.get('job') == T['job_en'] or sk in D.LATENT_SKILLS
        if dmg > 1200 or brk or ko:
            print(f"{fn[2:]:9s} step {i:2d} {R['bots'][cur[0]][:6]:6s} {T['name']:5s} {S.get('zh', sk):8s} {'本职' if native else '副职'} BP{bp} {'潜' if lat else ' '} hits {nh} dmg {dmg:5d} brk {brk} ko {ko}")
