// node cap_foot.js W H outdir shots.js [only]
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
const [W,H,out,shotsF,only]=process.argv.slice(2);
const shots=require(require('path').resolve(shotsF)).filter(s=>!only||only.split(',').includes(s.name));
(async()=>{const b=await chromium.launch();
for(const s of shots){
  const p=await b.newPage({viewport:{width:+W,height:+H},deviceScaleFactor:1});
  await p.goto((process.env.BASE||'file://'+(process.env.ARENA_ROOT||'/mnt/project-files/arena')+'/results/demo_v1_0.1m/')+encodeURIComponent(s.file)+`?clean=1&w=${W}&h=${H}&fps=60`);
  await p.waitForFunction(()=>window.arenaCapture&&arenaCapture.ticks);
  if(process.env.OV){const ov=fs.readFileSync(process.env.OV,'utf8');await p.evaluate(o=>{const OV=JSON.parse(o);for(const k in OV){const f=R.frames[+k];f.b=OV[k].b;OV[k].r.forEach((p,q)=>{f.r[q][0]=p[0];f.r[q][1]=p[1];f.r[q][2]=p[2]})}},ov);}
  await p.evaluate(()=>{
    window.ballAt=t=>{const F=R.frames,i=Math.max(0,Math.min(F.length-2,Math.floor(t))),f=t-i,a=F[i].b,c=F[i+1].b;return [a[0]+(c[0]-a[0])*f,a[1]+(c[1]-a[1])*f,a[2]+(c[2]-a[2])*f]};
    window.ballSm=(t,w)=>{let s=[0,0,0],n=0;for(let d=-w;d<=w;d+=1){const g=Math.exp(-d*d/(2*(w/2)**2)),p=ballAt(t+d);s[0]+=p[0]*g;s[1]+=p[1]*g;s[2]+=p[2]*g;n+=g}return s.map(v=>v/n)};
    window._lerp=(a,b,k)=>a.map((v,i)=>v+(b[i]-v)*k);
    window._ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
    window._ease2=t=>t*t*(3-2*t);
    window._smin=(a,b,k)=>-k*Math.log(Math.exp(-a/k)+Math.exp(-b/k));
  });
  const dir=`${out}/${s.name}`;fs.mkdirSync(dir,{recursive:true});
  for(let k=0;k<s.n;k++){
    if(s.step&&k%s.step) continue;
    const png=await p.evaluate(([k,n,t0,t1,cam,warm])=>{
      const u=n>1?k/(n-1):0;const t=t0+(t1-t0)*u;
      if(k===0&&warm){arenaCapture.seek(Math.floor(t-warm),0);arenaCapture.render();for(let j=warm*2-1;j>=0;j--){const tt=t-j/2;arenaCapture.seek(Math.floor(tt),tt%1);arenaCapture.render();}}
      arenaCapture.seek(Math.floor(t),t%1);
      const c=(new Function('u','t','k','return '+cam))(u,t,k);
      arenaCapture.camera(c[0],c[1],c[2]);
      arenaCapture.render();return arenaCapture.dataURL('image/jpeg');
    },[k,s.n,s.t0,s.t1,s.cam,s.warm||0]);
    fs.writeFileSync(`${dir}/${String(k).padStart(5,'0')}.jpg`,Buffer.from(png.split(',')[1],'base64'));
  }
  console.log('done',s.name);await p.close();
}
await b.close();})();
