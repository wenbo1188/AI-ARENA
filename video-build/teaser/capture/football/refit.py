import json, numpy as np
d=json.load(open('foot_seg.json')); F=d['f']; t0=F[0]['t']; n=len(F)
TOL=0.065
def refit(P):
    def fit(i,j):
        t=np.arange(i,j+1)-i; A=np.stack([np.ones_like(t),t,t*t],1).astype(float)
        C=np.linalg.lstsq(A,P[i:j+1],rcond=None)[0]; return C,np.abs(A@C-P[i:j+1]).max()
    out=P.copy(); i=0
    while i<n:
        j=min(i+2,n-1)
        while j+1<n and fit(i,j+1)[1]<=TOL: j+=1
        if j-i>=2:
            C,_=fit(i,j); t=np.arange(0,j-i+1); out[i:j+1]=np.stack([np.ones_like(t),t,t*t],1)@C
        i=j+1
    return out
B=refit(np.array([f['b'] for f in F],float))
nr=len(F[0]['r'])
R=[refit(np.array([f['r'][k][:3] for f in F],float)) for k in range(nr)]
ov={}
for k in range(n):
    ov[str(t0+k)]={'b':[round(float(v),4) for v in B[k]],'r':[[round(float(v),4) for v in R[q][k]] for q in range(nr)]}
json.dump(ov,open('pos_fix.json','w')); print('ok',n)
