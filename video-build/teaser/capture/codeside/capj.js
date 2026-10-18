// node cap9.js page.html W H outdir shots.json   (shot: {name,t0,t1,n,c0:[x,y],c1,z0,z1,ease?} ; n=1 for a still)
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
const [page,W,H,out,shotsF]=process.argv.slice(2);
const shots=JSON.parse(fs.readFileSync(shotsF));
const ease2=t=>t*t*(3-2*t);
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:+W,height:+H},deviceScaleFactor:1});
await p.goto('file://'+require('path').resolve(page)+`?clean=1&w=${W}&h=${H}`);
await p.evaluate(()=>arenaCapture.ready);
for(const s of shots){const dir=`${out}/${s.name}`;fs.mkdirSync(dir,{recursive:true});
 for(let k=0;k<s.n;k++){const u=s.n>1?k/(s.n-1):0,e=s.ease===false?u:ease2(u);
  // time runs linearly unless a warp [[u,t],...] is given
  let t=s.t0+(s.t1-s.t0)*u;
  if(s.warp){const w=s.warp;for(let j=1;j<w.length;j++)if(u<=w[j][0]){const a=w[j-1],c=w[j];t=a[1]+(c[1]-a[1])*(u-a[0])/(c[0]-a[0]);break;}}
  await p.evaluate(([t,cx,cy,z])=>{arenaCapture.seek(Math.floor(t),t%1);arenaCapture.view(cx,cy,z);arenaCapture.render()},[t,s.c0[0]+(s.c1[0]-s.c0[0])*e,s.c0[1]+(s.c1[1]-s.c0[1])*e,s.z0+(s.z1-s.z0)*e]);
  await p.screenshot({path:`${dir}/${String(k).padStart(5,'0')}.jpg`,type:'jpeg',quality:90});}
 console.log('done',s.name,s.n);}
await b.close();})();
