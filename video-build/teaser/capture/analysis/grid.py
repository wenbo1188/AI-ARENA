import numpy as np,sys
d=np.load('sync/onset.npz'); t=d['t']; fx=d['flux']
BEAT=60/128; S16=BEAT/4
a0,a1=int(sys.argv[1]),int(sys.argv[2])
med=np.median(fx)
for k in range(a0,a1):
    row=[]
    for s in range(16):
        c=k*4*BEAT+s*S16
        m=(t>c-0.035)&(t<c+0.06)
        v=fx[m].max()/med
        row.append(v)
    print(f'bar {k:2d} {k*4*BEAT:6.2f}s ', ' '.join(('#' if v>2.2 else '+' if v>1.7 else '.' ) for v in row), '  ', ' '.join(f'{v:3.1f}' for v in row))
