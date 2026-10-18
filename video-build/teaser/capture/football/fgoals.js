const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const D=(process.env.ARENA_ROOT||'/mnt/project-files/arena')+'/results/demo_v1_0.1m/';
const fs=require('fs');
(async()=>{const b=await chromium.launch();
for(const f of fs.readdirSync(D).filter(x=>/^\d{3}_.*\.html$/.test(x))){
 const p=await b.newPage({viewport:{width:320,height:180}});
 await p.goto('file://'+D+encodeURIComponent(f)+'?clean=1&w=320&h=180');
 await p.waitForFunction(()=>window.arenaCapture&&arenaCapture.ticks);
 const r=await p.evaluate(()=>{const F=R.frames;const keys=Object.keys(F[0]);const out=[];let last=JSON.stringify(F[0].s);
   for(let i=1;i<F.length;i++){const s=JSON.stringify(F[i].s);if(s!==last){out.push([i,s]);last=s}} return {n:F.length,keys,goals:out,bots:R.bots}});
 console.log(f,JSON.stringify(r));await p.close();}
await b.close();})();
