import numpy as np
d=np.load('sync/onset.npz'); t=d['t']; fx=d['flux']; fl=d['fl']
BEAT=60/128; BAR=4*BEAT
def phase(env,a,b):
    m=(t>=a)&(t<b); best=None
    for ph in np.arange(-0.2,0.2,0.004):
        g=np.arange(a+ph,b,BEAT/2)  # eighth grid
        v=np.interp(g,t,env).sum()
        if best is None or v>best[0]: best=(v,ph)
    return best[1]
for k in range(0,39,1):
    a=k*BAR; b=a+BAR
    m=(t>=a)&(t<b)
    if not m.any(): continue
    env=fx[m]; tt=t[m]
    # peaks
    pk=[i for i in range(1,len(env)-1) if env[i]>=env[i-1] and env[i]>env[i+1]]
    pk=sorted(pk,key=lambda i:-env[i])[:4]
    s=' '.join(f'{(tt[i]-a)/BEAT:5.2f}' for i in sorted(pk))
    print(f'bar {k:2d} t={a:6.2f} ph8={phase(fx,a,b)*1000:+5.0f}ms kickph={phase(fl,a,b)*1000:+5.0f}ms energy={env.mean():6.1f} peaks(beats)={s}')
