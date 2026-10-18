import json,glob,os
for fn in sorted(glob.glob('m/*.json')):
    R=json.load(open(fn)); F=R['frames']
    nb=[len(f.get('b') or []) for f in F]
    ev=[(f['t'],e[0],e[1:4]) for f in F for e in (f.get('e') or []) if e[0] in ('x','d')]
    w=60
    best=sorted(((sum(nb[k:k+w]),F[k]['t']) for k in range(0,max(1,len(F)-w),10)),reverse=True)[:3]
    print(os.path.basename(fn), R['scores'], len(F), 'maxb',max(nb), 'win',best, 'ev',[(t,k) for t,k,_ in ev][:14])
