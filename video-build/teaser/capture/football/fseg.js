const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
const G=JSON.parse(process.argv[2]);
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:320,height:180}});
 await p.goto('file://'+require('path').resolve('foot8/004.html')+'?clean=1&w=320&h=180');
 await p.waitForFunction(()=>window.arenaCapture&&arenaCapture.ticks);
 const out=await p.evaluate(G=>G.map(([a,c])=>R.frames.slice(a,c+1)),G);
 fs.writeFileSync('fsegs.json',JSON.stringify(out));await b.close();})();
