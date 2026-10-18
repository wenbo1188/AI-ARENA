// node cap_octo.js W H outdir shots.json
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
const [PAGE,W,H,out,shotsF]=process.argv.slice(2);
const shots=JSON.parse(fs.readFileSync(shotsF));
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:+W,height:+H},deviceScaleFactor:1});
await p.goto('file://'+require('path').resolve(PAGE)+`?clean=1&w=${W}&h=${H}&fps=60`);
await p.evaluate(()=>arenaCapture.ready);
for(const s of shots){
  const dir=`${out}/${s.name}`;fs.mkdirSync(dir,{recursive:true});
  const dur=await p.evaluate(t=>arenaCapture.duration(t),s.step);
  const n=s.n||Math.round(dur*(s.f1-s.f0)/1000*60*(s.speed?1/s.speed:1));
  let c0=s.c0,c1=s.c1;
  if(s.focus){const u=await p.evaluate(([a,i,st])=>{arenaCapture.seek(st,0);return arenaCapture.unit(a,i)},[s.focus[0],s.focus[1],s.step]);c0=c1=[u.x+(s.dx||0),u.y+(s.dy||0)];}
  for(let i=0;i<n;i++){
    const k=n>1?i/(n-1):0, e=s.ease===false?k:ease(k);
    const frac=s.f0+(s.f1-s.f0)*k;
    const z=Math.exp(Math.log(s.z0)+(Math.log(s.z1)-Math.log(s.z0))*e);
    // keep the focal point stable while zooming: interpolate center weighted by zoom
    const w=(1/z-1/s.z0)/((1/s.z1-1/s.z0)||1);
    const cx=c0[0]+(c1[0]-c0[0])*(isFinite(w)?w:e), cy=c0[1]+(c1[1]-c0[1])*(isFinite(w)?w:e);
    await p.evaluate(([st,fr,z,cx,cy])=>{arenaCapture.seek(st,fr);if(Math.abs(z-1)<1e-4&&Math.abs(cx-720)<0.5&&Math.abs(cy-405)<0.5)arenaCapture.view();else arenaCapture.view(z,cx,cy);arenaCapture.render()},[s.step,frac,z,cx,cy]);
    await p.screenshot({path:`${dir}/${String(i).padStart(5,'0')}.jpg`,type:'jpeg',quality:90});
  }
  console.log('done',s.name,n);
}
await b.close();})();
