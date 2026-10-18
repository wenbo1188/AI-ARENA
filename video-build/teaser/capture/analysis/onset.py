import numpy as np, wave, sys
w=wave.open(sys.argv[1]); sr=w.getframerate(); n=w.getnframes(); ch=w.getnchannels()
x=np.frombuffer(w.readframes(n),dtype=np.int16).reshape(-1,ch).mean(1)/32768
hop=256; win=1024
frames=(len(x)-win)//hop
idx=np.arange(win)[None,:]+hop*np.arange(frames)[:,None]
S=np.abs(np.fft.rfft(x[idx]*np.hanning(win),axis=1))
S=np.log1p(100*S)
flux=np.maximum(0,np.diff(S,axis=0)).sum(1); flux=np.r_[0,flux]
t=(np.arange(frames)*hop+win/2)/sr
# low band flux (kick) 
f=np.fft.rfftfreq(win,1/sr); lo=f<150
fl=np.maximum(0,np.diff(S[:,lo],axis=0)).sum(1); fl=np.r_[0,fl]
np.savez('sync/onset.npz',t=t,flux=flux,fl=fl)
BEAT=60/128
# phase fit
for name,env in (('all',flux),('kick',fl)):
    best=None
    for ph in np.arange(0,BEAT,0.002):
        g=np.arange(ph,t[-1],BEAT)
        v=np.interp(g,t,env).sum()
        if best is None or v>best[0]: best=(v,ph)
    print(name,'best beat phase (s) =',round(best[1],3))
