// CodeSide 新宿 1987 像素街机回放：仅更新渲染与界面，沿用原始回放数据、播放控制和录制接口。
"use strict";
(() => {
const M = R.meta, F = R.frames, TPS = M.tps || 60;
// 宣传片录制用的网址参数（不带参数时一切照旧）：
//   clean=1 隐藏所有界面，只留游戏画面和场内特效；labels=0 只隐藏头顶名字和血条；w=..&h=.. 固定画布像素尺寸
const QS = new URLSearchParams(location.search);
const CLEAN = QS.get("clean") === "1", LABELS = !CLEAN && QS.get("labels") !== "0";
const FIXW = Math.max(0, Math.floor(+QS.get("w") || 0)), FIXH = Math.max(0, Math.floor(+QS.get("h") || 0));
const FIXED = FIXW > 0 && FIXH > 0;
if (CLEAN) document.documentElement.classList.add("clean");
const W = M.tiles.length, H = M.tiles[0].length;
const T = (x, y) => (x >= 0 && x < W && y >= 0 && y < H) ? M.tiles[x][y] : null;
const WEAPONS = ["手枪", "突击步枪", "火箭筒"], WKEY = ["pistol", "assault_rifle", "rocket_launcher"];
const BULLET_SPEED = [50, 50, 20], DAMAGE = [20, 5, 30];
const STAGES = { round1: "第一轮", round2: "第二轮", finals: "决赛" };
const NAME_COLORS = ["#ffad82", "#93b8ff"];
const TEAM_SOLID = ["#f47c59", "#6898ff"];
const owner = {}; M.units.forEach(([id, pid]) => owner[id] = pid);
const pIndex = pid => M.players.indexOf(pid);
const US = M.unit_size; // [0.9, 1.8]

// ---------- 素材 ----------
const IMG = {};
// 先把 base64 解码成字节再 createImageBitmap：不经过 <img src="data:...">，
// 这样在禁止 data: 图片的嵌入环境（比如带 CSP 的网页预览）里也能画出来
function b64bytes(uri) {
  const bin = atob(uri.slice(uri.indexOf(",") + 1)), arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}
function loadImg(uri) {
  const viaTag = () => new Promise(ok => { const im = new Image(); im.onload = () => ok(im); im.onerror = () => ok(null); im.src = uri; });
  if (!window.createImageBitmap) return viaTag();
  return createImageBitmap(new Blob([b64bytes(uri)], { type: "image/png" })).catch(viaTag);
}
function loadImages() {
  return Promise.all(Object.keys(ASSETS).filter(k => k.endsWith(".png")).map(k =>
    loadImg(ASSETS[k]).then(im => { if (im && im.width) IMG[k.slice(0, -4)] = im; })));
}

// New art is embedded by the existing Python exporter. Atlas extraction is visual only.
const ACTORS = [[], []];
function atlasPart(source, box, maxPixels) {
  const [x,y,w,h]=box, scratch=document.createElement("canvas");scratch.width=w;scratch.height=h;
  const g=scratch.getContext("2d",{willReadFrequently:true});g.drawImage(source,x,y,w,h,0,0,w,h);
  const rgba=g.getImageData(0,0,w,h).data;
  let left=w,top=h,right=-1,bottom=-1;
  for(let yy=0;yy<h;yy++)for(let xx=0;xx<w;xx++)if(rgba[(yy*w+xx)*4+3]>96){left=Math.min(left,xx);right=Math.max(right,xx);top=Math.min(top,yy);bottom=Math.max(bottom,yy);}
  if(right<left)return scratch;
  const sw=right-left+1,sh=bottom-top+1,k=Math.min(1,maxPixels/Math.max(sw,sh));
  const out=document.createElement("canvas");out.width=Math.max(1,Math.round(sw*k));out.height=Math.max(1,Math.round(sh*k));
  const og=out.getContext("2d");og.imageSmoothingEnabled=false;og.drawImage(scratch,left,top,sw,sh,0,0,out.width,out.height);
  return out;
}
function prepareShinjukuArt() {
  const actors=IMG["shinjuku/actors"],items=IMG["shinjuku/items"];
  if(actors) {
    const stops=[0,310,645,976,1256,1536];
    for(let team=0;team<2;team++)for(let pose=0;pose<5;pose++)ACTORS[team][pose]=atlasPart(actors,[stops[pose],team*512,stops[pose+1]-stops[pose],512],84);
  }
  if(items) {
    const boxes=[[0,0,384,512],[384,0,384,512],[768,0,351,512],[1119,0,417,512],
      [0,512,485,512],[485,512,317,512],[802,512,335,512],[1137,512,399,512]];
    const names=["health_pack","mine","pistol","assault_rifle","rocket_launcher","placed_mine","cartridges","magazine"];
    names.forEach((name,i)=>IMG["loot/"+name]=atlasPart(items,boxes[i],name==="cartridges"?40:72));
    WKEY.forEach(name=>IMG["guns/"+name+"/gun"]=IMG["loot/"+name]);
  }
}

// ---------- 预处理：每帧的战利品、事件索引 ----------
let loot = [];
const lootAt = [];
const deaths = [];   // {i, id, x, y}
const lastSeen = {}; // id -> 最后一帧的单位数组
for (let i = 0; i < F.length; i++) {
  const f = F[i];
  if (f.l) loot = f.l;
  lootAt[i] = loot;
  for (const e of f.e || []) if (e[0] === "d") deaths.push({ i, id: e[1], x: e[2], y: e[3], prev: (F[i - 1] && F[i - 1].u.find(u => u[0] === e[1])) || null });
}
const finalFrame = F[F.length - 1];
// 每帧累计：开火次数、对方阵亡数（= 本方击杀得分次数）
const shotsAt = [], killsAt = [];
{
  let sh = [0, 0], kl = [0, 0];
  for (let i = 0; i < F.length; i++) {
    for (const e of F[i].e || []) {
      if (e[0] === "s") sh[pIndex(owner[e[1]])]++;
      else if (e[0] === "d") kl[1 - pIndex(owner[e[1]])]++;
    }
    shotsAt[i] = sh.slice(); killsAt[i] = kl.slice();
  }
}

// ---------- 画布 ----------
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const stage = document.getElementById("stage");
let S = 20, S0 = 20, CW = 0, CH = 0, DPR = 1;
const FOV = H + 5;
let CX = W / 2, CY = H / 2, zoom = 1; // 镜头中心（世界坐标）和缩放，arenaCapture.view() 可改
stage.style.setProperty("--ar", ((W + 2) / FOV).toFixed(4));
function resize() {
  DPR = window.devicePixelRatio || 1;
  if (FIXED) {
    // 固定像素尺寸：整张地图按比例放进画布，背景铺满
    cv.width = FIXW; cv.height = FIXH; CW = FIXW / DPR; CH = FIXH / DPR;
    cv.style.width = CW + "px"; cv.style.height = CH + "px";
    S0 = Math.min(FIXH / FOV, FIXW / (W + 2)); S = S0 * zoom;
    levelCache = null;
    return;
  }
  const r = stage.getBoundingClientRect();
  // 官方相机：竖直方向看 (高度 + 5) 个单位，水平方向按屏幕比例；这里把画布限制在地图范围附近
  const aspect = (W + 2) / FOV;
  let w = r.width, h = r.height;
  // Fill the stage with skyline; fit the world without cropping or stretching.
  w = Math.max(1,w-2); h = Math.max(1,h-2);
  if (!(h > 0)) h = w / aspect;
  CW = Math.floor(w); CH = Math.floor(h);
  cv.style.width = CW + "px"; cv.style.height = CH + "px";
  cv.width = Math.floor(CW * DPR); cv.height = Math.floor(CH * DPR);
  S0 = Math.min(cv.height / FOV,cv.width/(W+2)); S = S0 * zoom;
  levelCache = null;
}
const sx = x => cv.width / 2 + (x - CX) * S;
const sy = y => cv.height / 2 - (y - CY) * S;

// 官方 SpriteRenderer.draw：origin 是贴图内的锚点（y 向上），scale 是每个像素对应的世界单位
function sprite(img, ox, oy, scale, x, y, rot, flip, alpha) {
  if (!img || !img.width) return;
  const w = img.width, h = img.height;
  ctx.save();
  ctx.translate(sx(x), sy(y));
  if (rot) ctx.rotate(-rot);
  if (flip) ctx.scale(-1, 1);
  const k = scale * S;
  ctx.scale(k, k);
  if (alpha !== undefined) ctx.globalAlpha = alpha;
  ctx.drawImage(img, -ox * w, -(1 - oy) * h);
  ctx.restore();
}

// ---------- 工业场景（根据原始关卡格子绘制并缓存，不改变物理形状） ----------
let levelCache = null;
// Presentation-only geometry. Tile coordinates and collision shapes are unchanged.
const LP = 40;
function buildLevel() {
  const c=document.createElement("canvas");c.width=W*LP;c.height=H*LP;
  const g=c.getContext("2d");g.imageSmoothingEnabled=false;
  const solid=(x,y)=>T(x,y)==="#",ceil=new Array(W).fill(false);
  // Corrugated rooftop service shafts are background cladding, as in the original renderer.
  for(let y=H-2;y>=1;y--) {
    for(let x=1;x<W-1;x++)if(solid(x,y))ceil[x]=true;
    for(let x=1;x<W-1;x++)if(ceil[x]) {
      const px=x*LP,py=(H-1-y)*LP;
      g.fillStyle=x%3===0?"#293342":"#313c4b";g.fillRect(px,py,LP,LP);
      for(let n=1;n<LP;n+=6){g.fillStyle="#101c2b";g.fillRect(px+n,py,2,LP);g.fillStyle="#657081";g.fillRect(px+n+2,py,1,LP);g.fillStyle="#354456";g.fillRect(px+n+3,py,2,LP);}
      g.fillStyle="#0b162b";g.fillRect(px,py+LP-2,LP,2);
      for(let n=0;n<6;n++){const a=Math.floor(hash(x,y,n)*LP),b=Math.floor(hash(y,x,n+2)*LP);g.fillStyle=n%2?"#14213366":"#a4774a66";g.fillRect(px+a,py+b,1+Math.floor(hash(n,x,y)*2),2+Math.floor(hash(n,y,x)*9));}
      if(x%4===1){g.fillStyle="#121a27";g.fillRect(px+4,py,5,LP);g.fillStyle="#89909a";g.fillRect(px+5,py,1,LP);g.fillStyle="#a47646";g.fillRect(px+7,py,1,LP);if(y%2===0){g.fillStyle="#111b26";g.fillRect(px+2,py+18,9,5);g.fillStyle="#aab0ad";g.fillRect(px+3,py+18,7,1);}}
      if(x%4===2&&y%5===2){
        g.fillStyle="#101b2b";g.fillRect(px+6,py+5,24,28);g.strokeStyle="#76808a";g.strokeRect(px+6.5,py+5.5,24,28);
        for(let n=9;n<30;n+=4){g.fillStyle="#586475";g.fillRect(px+9,py+n,18,1);g.fillStyle="#08111d";g.fillRect(px+9,py+n+1,18,2);}
      }
      if(x%5===3&&y%7===3){
        g.fillStyle="#647184";g.fillRect(px+5,py+4,29,23);g.fillStyle="#111a27";g.fillRect(px+7,py+6,25,19);
        g.fillStyle="#344252";g.fillRect(px+9,py+8,21,15);g.fillStyle="#080f19";g.beginPath();g.arc(px+18,py+15,7,0,Math.PI*2);g.fill();
        g.strokeStyle="#788497";g.lineWidth=1;g.beginPath();g.moveTo(px+13,py+10);g.lineTo(px+23,py+20);g.moveTo(px+13,py+20);g.lineTo(px+23,py+10);g.stroke();
      }
    }
  }
  for(let x=0;x<W;x++)for(let y=0;y<H;y++) {
    const t=T(x,y),px=x*LP,py=(H-1-y)*LP;
    // The original fancy renderer leaves the outer containment walls invisible.
    if((x===0||x===W-1||y===H-1)&&y!==0)continue;
    if(t==="#") {
      g.fillStyle="#172232";g.fillRect(px,py,LP,LP);
      g.fillStyle="#485567";g.fillRect(px+2,py+2,LP-4,LP-4);
      g.fillStyle="#303d50";g.fillRect(px+3,py+5,LP-6,LP-8);
      g.fillStyle="#101a2b";g.fillRect(px+3,py+12,LP-6,3);g.fillRect(px+3,py+27,LP-6,3);
      for(let n=0;n<3;n++){g.fillStyle="#687588";g.fillRect(px+6+n*11,py+7,7,2);g.fillRect(px+6+n*11,py+22,7,2);g.fillStyle="#0c1524";g.fillRect(px+6+n*11,py+10,7,2);}
      g.fillStyle="#a9abb0";for(const dx of [4,LP-6])for(const dy of [4,LP-6])g.fillRect(px+dx,py+dy,2,2);
      if(!solid(x,y+1)){
        g.fillStyle="#d4c3a6";g.fillRect(px,py,LP,3);g.fillStyle="#717984";g.fillRect(px,py+3,LP,3);
        g.fillStyle="#151b22";g.fillRect(px,py+7,LP,6);
        g.save();g.beginPath();g.rect(px,py+7,LP,6);g.clip();g.fillStyle="#c6a35d";
        for(let n=-1;n<5;n++){g.beginPath();g.moveTo(px+n*11,py+7);g.lineTo(px+n*11+5,py+7);g.lineTo(px+n*11+10,py+13);g.lineTo(px+n*11+5,py+13);g.fill();}g.restore();
      }
      if(!solid(x-1,y)){g.fillStyle="#93a2b2";g.fillRect(px,py,2,LP);}
      if(!solid(x+1,y)){g.fillStyle="#080f19";g.fillRect(px+LP-2,py,2,LP);}
    } else if(t==="^") {
      g.fillStyle="#0e1725";g.fillRect(px,py+2,LP,8);g.fillStyle="#9fa7b0";g.fillRect(px,py,LP,2);g.fillStyle="#586378";g.fillRect(px,py+3,LP,3);
      g.fillStyle="#dbd3b4";g.fillRect(px+2,py+3,2,2);g.fillRect(px+LP-4,py+3,2,2);
      g.fillStyle="#27364a";g.beginPath();g.moveTo(px+6,py+9);g.lineTo(px+14,py+17);g.lineTo(px+14,py+9);g.fill();
    } else if(t==="H") {
      g.fillStyle="#0c1422";g.fillRect(px+11,py,18,LP);g.fillStyle="#d2a255";g.fillRect(px+11,py,2,LP);g.fillRect(px+27,py,2,LP);
      g.fillStyle="#f1c779";g.fillRect(px+11,py,1,LP);g.fillRect(px+27,py,1,LP);
      for(let n=4;n<LP;n+=9){g.fillStyle="#e5b86b";g.fillRect(px+13,py+n,14,2);g.fillStyle="#786246";g.fillRect(px+13,py+n+2,14,1);}
    }
  }
  // Rails and practical lamps follow actual exposed platform runs, on the background layer.
  for(let y=1;y<H-2;y++)for(let x=1;x<W-1;x++)if(solid(x,y)&&!solid(x,y+1)) {
    const px=x*LP,py=(H-1-y)*LP;
    if(solid(x-1,y)||solid(x+1,y)){
      g.fillStyle="#172131";g.fillRect(px,py-17,LP,2);g.fillRect(px,py-9,LP,2);g.fillRect(px+2,py-17,2,17);g.fillStyle="#726c67";g.fillRect(px,py-18,LP,1);
    }
    if(x%5===2){
      const light=g.createRadialGradient(px+20,py+LP+1,1,px+20,py+LP+1,LP*1.6);light.addColorStop(0,"#ffce8050");light.addColorStop(.4,"#ffc26c1a");light.addColorStop(1,"#dba76600");
      g.fillStyle=light;g.fillRect(px-LP,py+LP,LP*3,LP*1.7);g.fillStyle="#0b1421";g.fillRect(px+12,py+LP-1,16,4);g.fillStyle="#ffe1a3";g.fillRect(px+15,py+LP,10,2);
    }
  }
  return c;
}
const pads = []; for (let x = 0; x < W; x++) for (let y = 0; y < H; y++) if (T(x, y) === "T") pads.push([x, y]);

function drawBackground(tick) {
  const w=cv.width,h=cv.height,city=IMG["shinjuku/city"];
  ctx.fillStyle="#081329";ctx.fillRect(0,0,w,h);
  if(city){
    const k=Math.max(w/city.width,h/city.height),bw=city.width*k,bh=city.height*k;
    ctx.drawImage(city,(w-bw)/2,(h-bh)/2,bw,bh);
    // Background contrast is deliberately lower than the collision edges and combat sprites.
    ctx.fillStyle="#05112c35";ctx.fillRect(0,0,w,h);
  }
  const v=ctx.createRadialGradient(w*.5,h*.45,h*.2,w*.5,h*.5,Math.max(w,h)*.72);
  v.addColorStop(0,"#02061200");v.addColorStop(1,"#020612b0");ctx.fillStyle=v;ctx.fillRect(0,0,w,h);
}
function drawWeather(tick) {
  const w=cv.width,h=cv.height;ctx.save();ctx.strokeStyle="#a4bcdd24";ctx.lineWidth=Math.max(1,S*.025);
  ctx.beginPath();for(let n=0;n<38;n++){const yy=((hash(n,7,3)+tick/TPS*.29)%1)*h,xx=(hash(n,2,9)*w-yy*.18+w)%w;ctx.moveTo(Math.round(xx),Math.round(yy));ctx.lineTo(Math.round(xx-S*.12),Math.round(yy+S*.35));}ctx.stroke();ctx.restore();
}

function drawLevel(i, tick) {
  if (!levelCache) levelCache = buildLevel();
  ctx.save(); ctx.imageSmoothingEnabled = false;
  ctx.drawImage(levelCache, sx(0), sy(H), W * S, H * S); ctx.restore();
  // 跳板：被踩后 0.2 秒内播放压缩动画（官方 JUMP_PAD_ANIMATION_TIME）
  const used = {};
  for (let j = Math.max(0, i - 14); j <= i; j++) for (const e of F[j].e || []) if (e[0] === "p") used[e[1] + "," + e[2]] = F[j].t;
  for (const [x, y] of pads) {
    let name = "jumper_1";
    const u = used[x + "," + y];
    if (u !== undefined) {
      let t = Math.min(1, (tick - 1 - u) / TPS / 0.2); if (t < 0) t = 1;
      if (t < 0.33) name = "jumper_3"; else if (t < 0.66) name = "jumper_2";
    }
    const compress = name === "jumper_3" ? .10 : name === "jumper_2" ? .18 : .25;
    ctx.save();
    ctx.fillStyle="#2a3123"; ctx.fillRect(sx(x+.06),sy(y+.28),S*.88,S*.28);
    ctx.fillStyle="#817c55";ctx.fillRect(sx(x+.12),sy(y+compress),S*.76,S*.09);
    ctx.shadowColor="#c5ae6a";ctx.shadowBlur=S*.35;ctx.fillStyle="#dcc58c";
    ctx.fillRect(sx(x+.12),sy(y+compress+.045),S*.76,S*.045);
    ctx.strokeStyle="#d9c18b66";ctx.lineWidth=Math.max(1,S*.04);
    ctx.shadowBlur=0;ctx.fillStyle="#24291d";for(let n=0;n<3;n++)ctx.fillRect(sx(x+.2+n*.22),sy(y+compress+.045),S*.09,S*.09);
    ctx.restore();
  }
}

function drawLoot(i,time) {
  const names=["health_pack","mine","pistol","assault_rifle","rocket_launcher"];
  const sizes=[[.90,.70],[.94,.66],[.88,.52],[1.34,.54],[1.42,.56]];
  for(const [x,y,k] of lootAt[i]){
    const im=IMG["loot/"+names[k]];if(!im)continue;
    const scale=Math.min(sizes[k][0]/im.width,sizes[k][1]/im.height),bob=Math.max(0,Math.sin(time*3+x*1.7)*.04);
    ctx.save();ctx.fillStyle="#050c18aa";ctx.beginPath();ctx.ellipse(sx(x),sy(y+.035),S*sizes[k][0]*.45,S*.055,0,0,Math.PI*2);ctx.fill();
    ctx.shadowColor=k===0?"#ffd7ae":k===1?"#c9ba7b":"#f5cf8b";ctx.shadowBlur=S*.10;
    sprite(im,.5,0,scale,x,y+.035+bob,0,false);ctx.restore();
  }
}

function drawBullets(f, frac) {
  for (const [x, y, a, w] of f.b || []) {
    const d = BULLET_SPEED[w] * frac / TPS;
    const bx = x + Math.cos(a) * d, by = y + Math.sin(a) * d;
    // 拖尾
    ctx.save();
    ctx.strokeStyle = w === 2 ? "rgba(255,170,60,.85)" : "rgba(255,240,180,.7)";
    ctx.lineWidth = Math.max(1, S * (w === 2 ? 0.16 : 0.06));
    ctx.lineCap = "round"; ctx.shadowColor = w === 2 ? "#eeb569" : "#ffe4a1"; ctx.shadowBlur = S * .4;
    const tl = w === 2 ? 0.9 : 0.7;
    ctx.beginPath(); ctx.moveTo(sx(bx - Math.cos(a) * tl), sy(by - Math.sin(a) * tl)); ctx.lineTo(sx(bx), sy(by)); ctx.stroke();
    ctx.restore();
    ctx.save();ctx.translate(sx(bx),sy(by));ctx.rotate(-a);
    if(w===2){ctx.fillStyle="#263b30";ctx.fillRect(-S*.21,-S*.085,S*.4,S*.17);ctx.fillStyle="#d0af75";ctx.beginPath();ctx.moveTo(S*.31,0);ctx.lineTo(S*.12,-S*.085);ctx.lineTo(S*.12,S*.085);ctx.fill();}
    else {ctx.fillStyle="#fff1ca";ctx.fillRect(-S*.10,-Math.max(1,S*.025),S*.2,Math.max(2,S*.05));}
    ctx.restore();
    if (w === 2) { // 火箭尾焰
      const g = ctx.createRadialGradient(sx(bx), sy(by), 0, sx(bx), sy(by), S * 0.5);
      g.addColorStop(0, "rgba(255,200,90,.55)"); g.addColorStop(1, "rgba(255,120,0,0)");
      ctx.fillStyle = g; ctx.fillRect(sx(bx) - S * 0.5, sy(by) - S * 0.5, S, S);
    }
  }
}

function lerpUnit(a, b, frac) {
  if (!b) return a;
  const u = a.slice(); u[1] = a[1] + (b[1] - a[1]) * frac; u[2] = a[2] + (b[2] - a[2]) * frac; return u;
}

// New full-body arcade sprites. Pose selection reads the same recorded flags and position.
function drawUnit(u,tick,alpha) {
  const [id,x,y,hp,flags,mines,w,mag,lastAngle,lastFire]=u,team=pIndex(owner[id]);
  const onGround=flags&1,onLadder=flags&2,stand=flags&4,walkedRight=flags&8;
  const aim=w>=0&&lastAngle!==null?lastAngle:(walkedRight?0:Math.PI);
  const flip=Math.cos(aim)<0;
  const pose=onLadder?4:onGround?(stand?0:1+(Math.floor(x*2.2)%2+2)%2):3;
  const im=ACTORS[team][pose];if(!im)return;
  const bodyH=pose===3?US[1]*.78:US[1],bodyW=bodyH*im.width/im.height;
  const lift=onGround?0:pose===3?.17:0;
  ctx.save();ctx.globalAlpha=alpha??1;
  ctx.fillStyle=TEAM_SOLID[team]+"8c";ctx.beginPath();ctx.ellipse(sx(x),sy(y)-1,S*.43,S*.075,0,0,Math.PI*2);ctx.fill();
  ctx.shadowColor="#050a13";ctx.shadowBlur=S*.08;
  sprite(im,.5,0,bodyH/im.height,x,y+lift,0,flip);
  ctx.shadowBlur=0;
  if(w>=0){
    const gun=IMG["loot/"+WKEY[w]],gunW=[.63,1.03,1.17][w],gunH=gunW*gun.height/gun.width;
    const hy=y+US[1]*(pose===3?.60:.59),hx=x+(flip?-.03:.03);
    ctx.save();ctx.translate(sx(hx),sy(hy));ctx.rotate(-aim);if(flip)ctx.scale(1,-1);
    ctx.drawImage(gun,-S*.10,-S*gunH*.48,S*gunW,S*gunH);
    // The near hand joins the original recorded aim to the new gun artwork.
    ctx.fillStyle="#eab084";ctx.fillRect(S*.12,S*.035,S*.12,S*.10);ctx.fillStyle="#7a493a";ctx.fillRect(S*.12,S*.12,S*.12,S*.035);
    const flash=lastFire!=null?Math.floor((tick-lastFire)/2):-1;
    if(flash>=0&&flash<2){
      const mx=S*(gunW-.1),sz=S*(w===2?.43:.31);ctx.shadowColor="#ffa850";ctx.shadowBlur=S*.8;
      ctx.fillStyle="#ffb34c";ctx.beginPath();ctx.moveTo(mx,0);ctx.lineTo(mx+sz*.42,-sz*.34);ctx.lineTo(mx+sz*.30,-sz*.08);ctx.lineTo(mx+sz,0);ctx.lineTo(mx+sz*.30,sz*.08);ctx.lineTo(mx+sz*.42,sz*.34);ctx.closePath();ctx.fill();
      ctx.fillStyle="#fff2c7";ctx.fillRect(mx,-S*.04,sz*.5,S*.08);
    }
    ctx.restore();
  }
  if(hp<M.max_health*.3){ctx.strokeStyle="#ef735966";ctx.lineWidth=Math.max(1,S*.035);ctx.strokeRect(sx(x-bodyW/2),sy(y+bodyH+lift),bodyW*S,bodyH*S);}
  ctx.restore();
}

function drawLabels(units) {
  ctx.save();
  ctx.textAlign = "center"; ctx.textBaseline = "bottom";
  const fs = Math.max(10, Math.round(S * 0.62)), lh = fs + 3;
  ctx.font = `700 ${fs}px "PingFang SC","Microsoft YaHei",system-ui,sans-serif`;
  // 从下往上摆名字，和已经摆好的名字重叠就往上挪一行，避免挤在一起的队友名字叠成一团
  const placed = [];
  const list = units.map(u => ({ u, px: sx(u[1]), py: sy(u[2] + US[1]) - S * 0.55 })).sort((a, b) => b.py - a.py);
  for (const it of list) {
    const [id, , , hp] = it.u, team = pIndex(owner[id]);
    const name = R.bots[team] + " / " + id, tw = ctx.measureText(name).width + 10;
    let ly = it.py;
    for (let tries = 0; tries < 6; tries++) {
      const hit = placed.find(p => Math.abs(p.x - it.px) < (p.w + tw) / 2 && Math.abs(p.y - ly) < lh);
      if (!hit) break;
      ly = hit.y - lh;
    }
    placed.push({ x: it.px, y: ly, w: tw });
    // 头顶血条（跟着单位，不跟名字挪）
    const bw = S * 1.3, bh = Math.max(3, S * 0.16), py = it.py;
    ctx.fillStyle = "rgba(0,0,0,.6)"; ctx.fillRect(it.px - bw / 2 - 1, py + S * 0.12 - 1, bw + 2, bh + 2);
    ctx.fillStyle = hp > 60 ? TEAM_SOLID[team] : hp > 30 ? "#d9bb79" : "#db6e60";
    ctx.fillRect(it.px - bw / 2, py + S * 0.12, bw * Math.max(0, hp) / M.max_health, bh);
    ctx.fillStyle="#20261bd9"; ctx.fillRect(it.px-tw/2,ly-fs-2,tw,fs+4);
    ctx.lineWidth = Math.max(2, fs / 5); ctx.strokeStyle = "rgba(0,0,0,.75)";
    ctx.strokeText(name, it.px, ly); ctx.fillStyle = NAME_COLORS[team]; ctx.fillText(name, it.px, ly);
  }
  ctx.restore();
}

const MINE_IMG = ["mine/preparing", "mine/idle", "mine/triggered", "mine/triggered"];
function drawMines(f, time) {
  for (const [x, y, st, pid] of f.m || []) {
    const im=IMG["loot/placed_mine"];
    if(im)sprite(im,.5,0,.66/im.width,x,y+.02,0,false);
    if(st===0){ctx.fillStyle="#e9ba6a";ctx.fillRect(sx(x)-S*.025,sy(y+.23),S*.05,S*.05);}
    if (st === 2 && Math.floor(time * 12) % 2 === 0) { // 触发后闪烁
      const g = ctx.createRadialGradient(sx(x), sy(y + 0.25), 0, sx(x), sy(y + 0.25), S * 1.2);
      g.addColorStop(0, "rgba(255,60,40,.6)"); g.addColorStop(1, "rgba(255,0,0,0)");
      ctx.fillStyle = g; ctx.fillRect(sx(x) - S * 1.2, sy(y + 0.25) - S * 1.2, S * 2.4, S * 2.4);
    }
  }
}

// 简单的确定性随机，保证拖动进度条时特效一致
function hash(a, b, c) { let h = (a * 374761393 + b * 668265263 + c * 2147483647) | 0; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }

function drawEffects(i, tick, frac) {
  const now = tick + frac;
  let shake = 0;
  for (let j = Math.max(0, i - 40); j <= i; j++) {
    const f = F[j], age = now - f.t;
    (f.e || []).forEach((e, k) => {
      if (e[0] === "x") {
        // 官方 FancyExplosionRenderer：0.2 秒内由小变大并淡出
        const t = age / TPS / 0.2;
        if (t <= 1) {
          const im = IMG["explosion"], r = e[3];
          if (im && im.width) sprite(im, 0.5, 0.5, 2 * r / im.height * Math.max(0.05, t), e[1], e[2], 0, false, 1 - t);
          const g = ctx.createRadialGradient(sx(e[1]), sy(e[2]), 0, sx(e[1]), sy(e[2]), S * r * 1.6);
          g.addColorStop(0, `rgba(255,220,140,${0.45 * (1 - t)})`); g.addColorStop(1, "rgba(255,120,0,0)");
          ctx.fillStyle = g; ctx.fillRect(sx(e[1]) - S * r * 1.6, sy(e[2]) - S * r * 1.6, S * r * 3.2, S * r * 3.2);
        }
        if (age >= 0 && age < 24) {
          const life=age/24; ctx.save();ctx.globalAlpha=(1-life)*.65;
          ctx.strokeStyle="#ffd59a";ctx.lineWidth=Math.max(1,S*.055*(1-life));
          ctx.beginPath();ctx.arc(sx(e[1]),sy(e[2]),S*e[3]*(.3+life*1.25),0,Math.PI*2);ctx.stroke();ctx.restore();
        }
        if (age < 40) { // 烟和碎片
          for (let n = 0; n < 14; n++) {
            const a = hash(j, k, n) * Math.PI * 2, v = 2 + hash(n, j, k) * 6, tt = age / TPS;
            const px = e[1] + Math.cos(a) * v * tt, py = e[2] + Math.sin(a) * v * tt - 6 * tt * tt;
            const al = Math.max(0, 1 - age / 40);
            ctx.fillStyle = n % 3 ? `rgba(89,112,133,${al * 0.7})` : `rgba(255,190,90,${al})`;
            const s = S * (n % 3 ? 0.22 + tt * 0.6 : 0.12);
            ctx.fillRect(sx(px) - s / 2, sy(py) - s / 2, s, s);
          }
          if (age < 12) shake = Math.max(shake, (1 - age / 12) * 0.18 * e[3] / 3);
        }
      } else if (e[0] === "w" && age < 10) {
        for (let n = 0; n < 4; n++) {
          const a = hash(j, k, n) * Math.PI * 2, v = 3 + hash(k, n, j) * 4, tt = age / TPS;
          ctx.fillStyle = `rgba(255,230,150,${1 - age / 10})`;
          const s = Math.max(1, S * 0.09);
          ctx.fillRect(sx(e[1] + Math.cos(a) * v * tt) - s / 2, sy(e[2] + Math.sin(a) * v * tt) - s / 2, s, s);
        }
      } else if ((e[0] === "h" || e[0] === "B") && age < 45) {
        // 伤害数字
        const u = (F[j].u.find(q => q[0] === e[1])) || (F[j - 1] && F[j - 1].u.find(q => q[0] === e[1]));
        if (!u) return;
        const dmg = e[0] === "h" ? DAMAGE[e[2]] : 50;
        const tt = age / 45, px = u[1] + (hash(j, k, 7) - 0.5) * 0.8, py = u[2] + US[1] + 0.6 + tt * 1.6;
        ctx.save();
        ctx.globalAlpha = 1 - tt * tt;
        ctx.font = `800 ${Math.round(S * (e[0] === "B" ? 0.8 : 0.6))}px ui-monospace,Menlo,monospace`;
        ctx.textAlign = "center"; ctx.lineWidth = Math.max(2, S * 0.12); ctx.strokeStyle = "#000";
        ctx.strokeText("-" + dmg, sx(px), sy(py)); ctx.fillStyle = e[0] === "B" ? "#ffb347" : "#fff";
        ctx.fillText("-" + dmg, sx(px), sy(py));
        ctx.restore();
        if (age < 8) { // 命中血花
          for (let n = 0; n < 5; n++) {
            const a = hash(j, n, k) * Math.PI * 2, v = 2 + hash(n, k, j) * 3, t2 = age / TPS;
            ctx.fillStyle = `rgba(220,30,40,${1 - age / 8})`;
            const s = Math.max(1, S * 0.1);
            ctx.fillRect(sx(u[1] + Math.cos(a) * v * t2) - s / 2, sy(u[2] + 1 + Math.sin(a) * v * t2) - s / 2, s, s);
          }
        }
      }
    });
  }
  return shake;
}

function drawDeaths(i, tick, frac) {
  for (const d of deaths) {
    const age = tick + frac - F[d.i].t;
    if (age < 0 || age > 60 || !d.prev) continue;
    const u = d.prev.slice(); u[3] = 0;
    ctx.save();
    // 倒下、淡出，同时往上飘一个小灵魂
    drawUnit(u, tick, Math.max(0, 1 - age / 60));
    ctx.restore();
    const tt = age / 60;
    ctx.save();
    ctx.globalAlpha = 1 - tt;
    ctx.font = `${Math.round(S * 1.1)}px system-ui`;
    ctx.textAlign = "center";
    const px=sx(d.x),py=sy(d.y+US[1]+.8+tt*2.5),r=S*(.22+tt*.25);
    ctx.strokeStyle=TEAM_SOLID[pIndex(owner[d.id])];ctx.lineWidth=Math.max(1,S*.07);
    ctx.beginPath();ctx.moveTo(px-r,py-r);ctx.lineTo(px+r,py+r);ctx.moveTo(px+r,py-r);ctx.lineTo(px-r,py+r);ctx.stroke();
    ctx.restore();
  }
}

// ---------- 示意图模式（官方 Schematic，按 M 切换） ----------
function drawSchematic(f, i) {
  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, cv.width, cv.height);
  const col = { "#": "#777", "^": "#555", "H": "#6b4f2a", "T": "#2f7d32" };
  for (let x = 0; x < W; x++) for (let y = 0; y < H; y++) {
    const t = T(x, y); if (!col[t]) continue;
    ctx.fillStyle = col[t];
    if (t === "^") ctx.fillRect(sx(x), sy(y + 1), S, S * 0.25); else ctx.fillRect(sx(x), sy(y + 1), S, S);
  }
  for (const [x, y, k] of lootAt[i]) { ctx.fillStyle = k === 0 ? "#3f3" : k === 1 ? "#f80" : "#ff3"; ctx.fillRect(sx(x - 0.25), sy(y + 0.5), S * 0.5, S * 0.5); }
  for (const [x, y, , w] of f.b || []) { const s = w === 2 ? 0.4 : 0.2; ctx.fillStyle = "#fff"; ctx.fillRect(sx(x - s / 2), sy(y + s / 2), S * s, S * s); }
  for (const u of f.u) { ctx.fillStyle = TEAM_SOLID[pIndex(owner[u[0]])]; ctx.fillRect(sx(u[1] - US[0] / 2), sy(u[2] + US[1]), US[0] * S, US[1] * S); }
  for (const [x, y, st] of f.m || []) { ctx.fillStyle = st === 2 ? "#f00" : "#a50"; ctx.fillRect(sx(x - 0.25), sy(y + 0.5), S * 0.5, S * 0.5); }
  for (let j = Math.max(0, i - 10); j <= i; j++) for (const e of F[j].e || []) if (e[0] === "x") {
    ctx.fillStyle = "rgba(255,0,0,.5)"; ctx.fillRect(sx(e[1] - e[3]), sy(e[2] + e[3]), 2 * e[3] * S, 2 * e[3] * S);
  }
}

// ---------- 声音 ----------
// 枪声、爆炸、上膛等用真实录音加工（出处见 assets/SOURCE.md），血包沿用官方音效。
// 播放链路：音源 → 声像（按地图横坐标左右分布）→ 干声 + 城市空间混响 → 压缩器 → 输出
let audio = null, soundOn = true, master = null, verb = null;
const buffers = {};
const lastPlayed = {};
const SFX = { pistol: "sfx/pistol.mp3", assault_rifle: "sfx/assault_rifle.mp3", rocket_launcher: "sfx/rocket_launcher.mp3",
  explosion: "sfx/explosion.mp3", hit: "sfx/hit.mp3", reload: "sfx/reload.mp3", pickup: "sfx/pickup.mp3", click: "sfx/click.mp3",
  pad: "sfx/pad.mp3", ricochet1: "sfx/ricochet1.mp3", ricochet2: "sfx/ricochet2.mp3", ricochet3: "sfx/ricochet3.mp3",
  mine_beep: "sfx/mine_beep.mp3", heal: "heal.mp3" };
function impulse(sec) {
  // 室外楼群的空间感：几次离散的楼面反射 + 指数衰减的扩散尾音（左右声道不相关）
  const n = Math.floor(audio.sampleRate * sec), ir = audio.createBuffer(2, n, audio.sampleRate);
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647 * 2 - 1;
  for (let c = 0; c < 2; c++) {
    const d = ir.getChannelData(c);
    for (let i = 0; i < n; i++) { const t = i / audio.sampleRate; d[i] = rnd() * Math.exp(-t / 0.35) * Math.min(1, t / 0.02) * 0.5; }
    for (const [t, g] of [[0.045 + c * 0.012, 0.7], [0.09 + c * 0.017, 0.45], [0.16 - c * 0.01, 0.3]]) d[Math.floor(t * audio.sampleRate)] += g;
  }
  return ir;
}
// 浏览器只允许在用户点按/按键时启动声音：第一次点页面任何地方（包括播放键）就解锁，
// 并在同一个手势里播放一段静音（iOS 需要），按钮显示真实状态
function unlockAudio() {
  if (!soundOn) return;
  initAudio();
  if (!audio) return;
  if (audio.state !== "running") audio.resume().catch(() => {});
  try { const b = audio.createBuffer(1, 1, 22050), s = audio.createBufferSource(); s.buffer = b; s.connect(audio.destination); s.start(0); } catch (e) {}
  updateSndBtn();
}
function updateSndBtn() {
  const btn = document.getElementById("snd");
  if (!btn) return;
  const live = audio && audio.state === "running";
  btn.textContent = !soundOn ? "🔇 静音" : live ? "🔊 音效" : "🔈 点按开声音";
  btn.classList.toggle("on", soundOn && !!live);
}
for (const ev of ["touchend", "click", "keydown"]) // 移动端只把 click/touchend 算作用户手势，pointerdown 不算
  window.addEventListener(ev, unlockAudio, { capture: true, passive: true });
async function initAudio() {
  if (audio) return;
  try { audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return; }
  audio.onstatechange = updateSndBtn;
  const comp = audio.createDynamicsCompressor();
  comp.threshold.value = -14; comp.knee.value = 8; comp.ratio.value = 4; comp.attack.value = 0.002; comp.release.value = 0.15;
  comp.connect(audio.destination);
  master = audio.createGain(); master.gain.value = 0.9; master.connect(comp);
  try { verb = audio.createConvolver(); verb.buffer = impulse(1.4); const wet = audio.createGain(); wet.gain.value = 0.32; verb.connect(wet); wet.connect(master); }
  catch (e) { verb = null; }
  for (const [k, p] of Object.entries(SFX)) {
    if (!ASSETS[p]) continue;
    try { buffers[k] = await audio.decodeAudioData(b64bytes(ASSETS[p]).buffer); } catch (e) { /* 忽略解码失败 */ }
  }
}
function play(name, vol, x, opt) {
  if (!audio || !soundOn || !buffers[name]) return;
  if (audio.state === "suspended") { audio.resume().catch(() => {}); return; }
  const now = audio.currentTime, gap = (opt && opt.gap) || 0.045;
  if (lastPlayed[name] && now - lastPlayed[name] < gap) return;
  lastPlayed[name] = now;
  const src = audio.createBufferSource(), g = audio.createGain();
  src.buffer = buffers[name];
  src.playbackRate.value = 1 + (Math.random() * 2 - 1) * ((opt && opt.vary) ?? 0.04); // 每发略有不同，避免机械重复
  g.gain.value = vol ?? 1;
  src.connect(g);
  let out = g;
  if (x != null && audio.createStereoPanner) {
    const pan = audio.createStereoPanner(); pan.pan.value = Math.max(-1, Math.min(1, (x - W / 2) / (W / 2))) * 0.7;
    g.connect(pan); out = pan;
  }
  out.connect(master);
  if (verb) { const send = audio.createGain(); send.gain.value = (opt && opt.wet) ?? 0.5; out.connect(send); send.connect(verb); }
  src.start();
}
window.codesideAudio = { init: () => initAudio(), buffers, sounds: (j) => soundsFor(F[j], F[j - 1]), frames: F.length };
function soundsFor(f, prev) {
  const pos = {}; for (const u of f.u) pos[u[0]] = u;
  const ux = id => (pos[id] ? pos[id][1] : null);
  for (const e of f.e || []) {
    const k = e[0];
    if (k === "s") play(WKEY[e[2]], e[2] === 2 ? 0.9 : 0.75, ux(e[1]), { wet: 0.6 });
    else if (k === "x") play("explosion", 1, e[1], { wet: 0.8, vary: 0.06 });
    else if (k === "h") play("hit", 0.7, ux(e[1]), { wet: 0.15, vary: 0.1 });
    else if (k === "w" && e[3] !== 2 && Math.random() < 0.35) play("ricochet" + (1 + Math.floor(Math.random() * 3)), 0.35, e[1], { wet: 0.4, gap: 0.12, vary: 0.08 });
    else if (k === "H") play("heal", 0.55, ux(e[1]), { wet: 0.1, vary: 0 });
    else if (k === "P") play("pickup", 0.8, ux(e[1]), { wet: 0.2 });
    else if (k === "M") play("click", 0.8, ux(e[1]), { wet: 0.2 });
    else if (k === "p") play("pad", 0.5, ux(e[1]), { wet: 0.2, gap: 0.2 });
  }
  if (!prev) return;
  // 换弹：同一把枪的弹匣数变多
  const before = {}; for (const u of prev.u) before[u[0]] = u;
  for (const u of f.u) {
    const b = before[u[0]];
    if (b && b[6] === u[6] && u[6] >= 0 && u[7] > b[7]) play("reload", 0.7, u[1], { wet: 0.2, gap: 0.1 });
  }
  // 地雷被触发：蜂鸣报警
  const trig = ms => (ms || []).filter(m => m[2] === 2).length;
  if (trig(f.m) > trig(prev.m)) { const m = (f.m || []).find(m => m[2] === 2); play("mine_beep", 0.6, m ? m[0] : null, { wet: 0.2, gap: 0.3, vary: 0 }); }
}

// ---------- 侧边栏单位卡片 ----------
const sides = [document.getElementById("side1"), document.getElementById("side2")];
const cards = {};
M.units.forEach(([id, pid]) => {
  const t = pIndex(pid), el = document.createElement("div");
  el.className = "card p" + (t + 1);
  el.innerHTML = `<div class="hd"><canvas class="face" width="30" height="26"></canvas><div><div class="who"></div><div class="uid">单位 #${id}</div></div></div>
    <div class="hp"><em></em><i></i></div>
    <div class="row"><span>生命</span><b class="hpv"></b></div>
    <div class="row"><span class="wpn"></span><span class="ammo"></span></div>
    <div class="row"><span>地雷</span><b class="mn"></b></div>`;
  el.querySelector(".who").textContent = R.bots[t];
  el.querySelector(".who").style.color = NAME_COLORS[t];
  sides[t].appendChild(el);
  cards[id] = { el, hpI: el.querySelector(".hp i"), hpE: el.querySelector(".hp em"), hpv: el.querySelector(".hpv"),
    wpn: el.querySelector(".wpn"), ammo: el.querySelector(".ammo"), mn: el.querySelector(".mn"), face: el.querySelector(".face"), key: "" };
});
const statEls = sides.map((side, t) => {
  const el = document.createElement("div");
  el.className = "card stats p" + (t + 1);
  el.innerHTML = `<div class="row"><span>击杀</span><b class="k"></b></div><div class="row"><span>伤害得分</span><b class="d"></b></div>
    <div class="row"><span>开火次数</span><b class="f"></b></div>`;
  side.appendChild(el);
  return { k: el.querySelector(".k"), d: el.querySelector(".d"), f: el.querySelector(".f") };
});
function updateStats(i) {
  for (let t = 0; t < 2; t++) {
    const k = killsAt[i][t];
    statEls[t].k.textContent = k; statEls[t].d.textContent = F[i].s[t] - k * 1000; statEls[t].f.textContent = shotsAt[i][t];
  }
}
function iconTo(cv2, im) {
  if (!im) return;
  cv2.width = im.width; cv2.height = im.height;
  const g = cv2.getContext("2d"); g.imageSmoothingEnabled = false; g.drawImage(im, 0, 0);
}
function drawFaces() {
  for(const id in cards){
    const c=cards[id].face,g=c.getContext("2d"),im=ACTORS[pIndex(owner[id])][0];
    c.width=40;c.height=40;g.imageSmoothingEnabled=false;
    if(im)g.drawImage(im,im.width*.20,0,im.width*.75,im.height*.45,1,1,38,38);
  }
}

function updateCards(f, tick) {
  const alive = {}; for (const u of f.u) alive[u[0]] = u;
  for (const id in cards) {
    const c = cards[id], u = alive[id];
    if (!u) {
      const key = "dead";
      if (c.key !== key) { c.key = key; c.el.classList.add("dead"); c.hpI.style.width = "0%"; c.hpE.style.width = "0%"; c.hpv.textContent = "阵亡"; c.wpn.textContent = ""; c.wkey = null; c.ammo.innerHTML = ""; c.mn.textContent = "-"; }
      continue;
    }
    const [, , , hp, , mines, w, mag, , , timer] = u;
    const key = [hp, mines, w, mag, timer > 0 ? 1 : 0].join();
    if (c.key === key) continue;
    c.key = key; c.el.classList.remove("dead");
    const pct = Math.max(0, hp) / M.max_health * 100;
    c.hpI.style.width = pct + "%"; c.hpE.style.width = pct + "%";
    c.hpI.className = pct > 60 ? "" : pct > 30 ? "mid" : "low";
    c.hpv.textContent = hp + " / " + M.max_health;
    if (w < 0) { c.wkey = -1; c.wpn.innerHTML = "<span>空手</span>"; c.ammo.innerHTML = ""; }
    else {
      if (c.wkey !== w) { c.wkey = w; c.wpn.innerHTML = `<canvas></canvas><b>${WEAPONS[w]}</b>`; iconTo(c.wpn.firstChild, IMG["loot/" + WKEY[w]]); }
      const max = M.magazine[w];
      c.ammo.innerHTML = Array.from({ length: max }, (_, k) => `<i class="${k < mag ? "" : "e"}"></i>`).join("");
      if (timer > 0.45) c.ammo.innerHTML = `<span class="tag">装弹中</span>`;
    }
    c.mn.textContent = mines ? "× " + mines : "0";
  }
}

// ---------- 播放控制 ----------
let pos = 0, playing = false, speed = 1, fancy = true, lastTs = null;
const tl = document.getElementById("tl"), fill = tl.querySelector(".fill"), knob = tl.querySelector(".knob");
const playBtn = document.getElementById("play"), tickEl = document.getElementById("tick");
const N = F.length - 1;
for (const d of deaths) {
  const m = document.createElement("div"); m.className = "mk";
  m.style.left = (d.i / Math.max(1, N) * 100) + "%"; m.style.background = TEAM_SOLID[pIndex(owner[d.id])];
  m.title = `第 ${F[d.i].t} tick：${R.bots[pIndex(owner[d.id])]} 的单位 #${d.id} 阵亡`;
  tl.appendChild(m);
}
function seekFromEvent(ev) {
  const r = tl.getBoundingClientRect();
  if (!(r.width > 0)) return;
  pos = Math.max(0, Math.min(N, (ev.clientX - r.left) / r.width * N));
}
let dragging = false;
tl.addEventListener("pointerdown", ev => { dragging = true; tl.setPointerCapture(ev.pointerId); seekFromEvent(ev); });
tl.addEventListener("pointermove", ev => { if (dragging) seekFromEvent(ev); });
tl.addEventListener("pointerup", () => dragging = false);
function setPlaying(p) {
  playing = p; playBtn.textContent = p ? "❚❚" : "▶";
  if (p) { unlockAudio(); if (pos >= N) pos = 0; }
}
playBtn.onclick = () => setPlaying(!playing);
document.getElementById("speed").onchange = e => speed = +e.target.value;
const modeBtn = document.getElementById("mode");
modeBtn.onclick = () => { fancy = !fancy; modeBtn.textContent = fancy ? "街机画面" : "示意图"; };
const sndBtn = document.getElementById("snd");
sndBtn.onclick = () => {
  // 声音开着但还没被浏览器放行时，这一下只负责解锁，不把它关掉
  if (soundOn && !(audio && audio.state === "running")) { unlockAudio(); return; }
  soundOn = !soundOn;
  if (soundOn) unlockAudio();
  updateSndBtn();
};
updateSndBtn();
window.addEventListener("keydown", e => {
  if (e.target.tagName === "SELECT") return;
  if (e.code === "Space") { e.preventDefault(); setPlaying(!playing); }
  else if (e.code === "ArrowRight") { pos = Math.min(N, Math.floor(pos) + (e.shiftKey ? 60 : 1)); }
  else if (e.code === "ArrowLeft") { pos = Math.max(0, Math.ceil(pos) - (e.shiftKey ? 60 : 1)); }
  else if (e.code === "KeyM") modeBtn.click();
});

// ---------- 顶部、击杀提示、结束横幅 ----------
document.getElementById("n1").textContent = R.bots[0];
document.getElementById("n2").textContent = R.bots[1];
document.getElementById("stagename").textContent = (STAGES[M.stage] || M.stage) + " · " + ({ simple: "简单关卡", complex: "复杂关卡", "level.txt": "官方固定关卡", empty: "空箱子" }[M.level] || M.level);
(R.stats || []).forEach((s, k) => { if (s && s.crashed) document.getElementById("c" + (k + 1)).style.display = "inline"; });
const s1 = document.getElementById("s1"), s2 = document.getElementById("s2"), feed = document.getElementById("feed");
const banner = document.getElementById("banner");
let feedKey = "";
function updateHud(i) {
  const f = F[i];
  s1.textContent = f.s[0]; s2.textContent = f.s[1];
  tickEl.textContent = `tick ${f.t} / ${M.ticks}`;
  const recent = deaths.filter(d => d.i <= i && F[i].t - F[d.i].t < 240).slice(-4);
  const key = recent.map(d => d.i + ":" + d.id).join();
  if (key !== feedKey) {
    feedKey = key;
    feed.innerHTML = "";
    for (const d of recent) {
      const t = pIndex(owner[d.id]), killer = 1 - t, div = document.createElement("div");
      div.innerHTML = `× <b style="color:${NAME_COLORS[t]}"></b> <span style="color:#8f8b9c">#${d.id}</span> 阵亡 · <b style="color:${NAME_COLORS[killer]}"></b> +1000`;
      div.querySelectorAll("b")[0].textContent = R.bots[t]; div.querySelectorAll("b")[1].textContent = R.bots[killer];
      feed.appendChild(div);
    }
  }
  if (i >= N) {
    const [a, b] = R.scores;
    const bt = document.getElementById("bt"), bs = document.getElementById("bs");
    if (a === b) { bt.textContent = "平局"; bt.style.color = ""; }
    else { const w = a > b ? 0 : 1; bt.textContent = R.bots[w] + " 获胜"; bt.style.color = NAME_COLORS[w]; }
    const teams = new Set(finalFrame.u.map(u => owner[u[0]]));
    bs.textContent = `${a} : ${b} · ` + (teams.size <= 1 && finalFrame.t < M.ticks ? "一方全灭" : "时间到");
    banner.style.display = "flex";
  } else banner.style.display = "none";
}

// ---------- 主循环 ----------
let lastI = -1, capturing = false, capPos = 0;
// 画一帧游戏画面。time 是动画时钟（秒）：平时用真实时间，录制时用比赛时间，保证逐帧确定
function render(i, frac, time) {
  const f = F[i], g = F[Math.min(N, i + 1)];
  const tick = f.t;
  ctx.imageSmoothingEnabled = false;
  if (!fancy) { drawSchematic(f, i); return; }
  drawBackground(tick + frac);
  ctx.save();
  let shake = 0;
  // 先算震动（只依赖事件），再整体平移
  for (let j = Math.max(0, i - 12); j <= i; j++) for (const e of F[j].e || []) if (e[0] === "x") {
    const age = tick + frac - F[j].t; if (age < 12) shake = Math.max(shake, (1 - age / 12) * 0.18 * e[3] / 3);
  }
  if (shake) ctx.translate((Math.sin(time * 90) * shake) * S, (Math.cos(time * 77) * shake) * S);
  drawLevel(i, tick);
  drawLoot(i, time);
  drawBullets(f, frac);
  const nextU = {}; for (const u of g.u) nextU[u[0]] = u;
  const units = f.u.map(u => lerpUnit(u, nextU[u[0]], frac));
  drawDeaths(i, tick, frac);
  for (const u of units) drawUnit(u, tick);
  drawMines(f, time);
  drawEffects(i, tick, frac);
  drawWeather(tick+frac);
  if (LABELS) drawLabels(units);
  ctx.restore();
}
function frame(ts) {
  if (capturing) return; // 录制接口接管后停止实时循环
  if (lastTs === null) lastTs = ts;
  const dt = Math.min(0.1, (ts - lastTs) / 1000); lastTs = ts;
  if (playing && !dragging) {
    pos += dt * TPS * speed;
    if (pos >= N) { pos = N; setPlaying(false); }
  }
  const i = Math.min(N, Math.floor(pos)), frac = i < N ? pos - i : 0;
  const f = F[i];
  if (playing && i !== lastI && speed <= 4) for (let j = Math.max(lastI + 1, i - 3); j <= i; j++) soundsFor(F[j], F[j - 1]);
  lastI = i;
  render(i, frac, ts / 1000);
  if (!CLEAN) {
    fill.style.width = (pos / Math.max(1, N) * 100) + "%";
    knob.style.left = (pos / Math.max(1, N) * 100) + "%";
    updateHud(i);
    updateCards(f, f.t);
    updateStats(i);
  }
  requestAnimationFrame(frame);
}

// ---------- 录制接口（给无头浏览器逐帧截图用） ----------
// seek(tick, frac) 跳到某个 tick（frac 是 0~1 的帧间插值），render() 画出这一帧，png() 取画布图片。
// 第一次调用 seek 后实时播放停止、声音关闭，画面只在 render() 时更新。
let readyResolve;
const ready = new Promise(r => { readyResolve = r; });
window.arenaCapture = {
  ready,
  ticks: N,
  fps: TPS,
  get width() { return cv.width; },
  get height() { return cv.height; },
  seek(tick, frac) {
    if (!capturing) { capturing = true; playing = false; soundOn = false; if (audio) audio.suspend().catch(() => {}); }
    capPos = Math.max(0, Math.min(N, (+tick || 0) + (+frac || 0)));
    return capPos;
  },
  render() {
    const i = Math.min(N, Math.floor(capPos)), frac = i < N ? capPos - i : 0;
    render(i, frac, (F[i].t + frac) / TPS);
    return true;
  },
  // 镜头特写：以世界坐标 (cx, cy) 为中心放大 zoom 倍；不带参数恢复全图
  view(cx, cy, z) {
    if (cx == null) { CX = W / 2; CY = H / 2; zoom = 1; }
    else { CX = +cx; CY = +cy; zoom = Math.max(0.1, +z || 1); }
    S = S0 * zoom;
    return { cx: CX, cy: CY, zoom };
  },
  png() { return cv.toDataURL("image/png"); },
  // 方便挑镜头：击杀和爆炸发生的 tick 与位置
  highlights() {
    const out = [];
    for (const d of deaths) out.push({ tick: F[d.i].t, type: "kill", id: d.id, x: d.x, y: d.y });
    for (const f of F) for (const e of f.e || []) if (e[0] === "x") out.push({ tick: f.t, type: "explosion", x: e[1], y: e[2] });
    return out.sort((a, b) => a.tick - b.tick);
  },
  map: { width: W, height: H },
};

window.addEventListener("resize", resize);
loadImages().then(() => {
  // 素材一张都没加载出来时自动切到示意图，至少保证有画面
  if (!Object.keys(IMG).length) { fancy = false; modeBtn.textContent = "示意图"; }
  prepareShinjukuArt(); resize(); drawFaces(); requestAnimationFrame(frame); setPlaying(false); readyResolve(true); });
})();
