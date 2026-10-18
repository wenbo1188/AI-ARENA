import numpy as np, subprocess, sys
f=sys.argv[1]; W,H=160,90
raw=subprocess.run(['ffmpeg','-loglevel','error','-i',f,'-vf',f'scale={W}:{H},format=gray','-f','rawvideo','-'],capture_output=True).stdout
v=np.frombuffer(raw,np.uint8).reshape(-1,H,W).astype(np.float32)
fps=24
d=np.abs(np.diff(v,axis=0)).mean((1,2)); d=np.r_[0,d]
lum=v.mean((1,2))
np.savez('sync/vis.npz',d=d,lum=lum)
o=np.load('sync/onset.npz'); ot=o['t']; ofx=o['flux']
BEAT=60/128
# visual events: frames where diff is a local peak and > 12
ev=[i for i in range(1,len(d)-1) if d[i]>12 and d[i]>=d[i-1] and d[i]>=d[i+1]]
print('n events',len(ev))
for i in ev:
    t=i/fps  # change between frame i-1 and i, i.e. at time i/fps
    b=t/BEAT
    # nearest strong onset within 0.25 s
    m=(ot>t-0.25)&(ot<t+0.25)
    j=np.argmax(np.where(m,ofx,0)); 
    print(f't={t:6.3f} diff={d[i]:5.1f} beat={b:6.2f} (off {((b+0.5)%1-0.5)*BEAT*1000:+4.0f}ms vs beat, {((b*2+0.5)%1-0.5)*BEAT/2*1000:+4.0f}ms vs 8th) strongest onset nearby at {ot[j]-t:+.3f}s flux={ofx[j]:.0f}')
