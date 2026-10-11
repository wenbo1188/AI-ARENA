"""把 3D 足球回放渲染成一个独立的 HTML 文件。

使用 three.js（MIT 协议，已内嵌在 arena/vendor/three.min.js）做 WebGL 渲染，
生成的文件不依赖网络，双击即可打开。
"""
import base64
import html
import json
import os

VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "vendor")
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

TEMPLATE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { --a:#22c55e; --b:#ef4444; --panel:rgba(10,14,22,0.72); --line:rgba(255,255,255,0.14); --fg:#eef2f7; --muted:#9aa4b2; }
  * { box-sizing:border-box; }
  html, body { margin:0; height:100%; background:#05080d; color:var(--fg); font:14px/1.45 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; overflow:hidden; }
  #app { position:fixed; inset:0; }
  canvas { display:block; width:100%; height:100%; touch-action:none; cursor:grab; }
  canvas:active { cursor:grabbing; }
  .hud { position:absolute; left:0; right:0; pointer-events:none; }
  .top { top:14px; display:flex; justify-content:center; padding:0 12px; }
  .board { display:flex; align-items:stretch; border-radius:12px; overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,.45); backdrop-filter:blur(8px); background:var(--panel); border:1px solid var(--line); max-width:100%; }
  .team { display:flex; align-items:center; gap:10px; padding:8px 16px; font-weight:600; font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:34vw; }
  .team .dot { width:12px; height:12px; border-radius:50%; flex:none; box-shadow:0 0 10px currentColor; }
  .team.a { color:#bbf7d0; } .team.a .dot { background:var(--a); color:var(--a); }
  .team.b { color:#fecaca; } .team.b .dot { background:var(--b); color:var(--b); }
  .mid { display:flex; flex-direction:column; align-items:center; justify-content:center; padding:4px 18px; background:rgba(255,255,255,0.06); }
  .num { font-size:28px; font-weight:800; letter-spacing:2px; font-variant-numeric:tabular-nums; line-height:1.1; }
  .clock { font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; }
  .goal { position:absolute; top:34%; left:0; right:0; text-align:center; font-size:clamp(40px, 9vw, 110px); font-weight:900; letter-spacing:6px; opacity:0; transform:scale(.6); transition:opacity .25s, transform .35s cubic-bezier(.2,1.6,.4,1); text-shadow:0 6px 40px rgba(0,0,0,.6); pointer-events:none; }
  .goal.show { opacity:1; transform:scale(1); }
  .goal small { display:block; font-size:clamp(16px, 2.6vw, 28px); letter-spacing:1px; font-weight:600; margin-top:4px; }
  .bottom { bottom:0; padding:12px; display:flex; flex-direction:column; gap:8px; pointer-events:auto;
            background:linear-gradient(to top, rgba(5,8,13,.9), rgba(5,8,13,0)); }
  .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  button, select { background:var(--panel); color:var(--fg); border:1px solid var(--line); border-radius:8px; padding:6px 12px; font:inherit; cursor:pointer; backdrop-filter:blur(6px); }
  button:hover { border-color:rgba(255,255,255,.35); }
  button.on { border-color:#facc15; color:#fde68a; }
  input[type=range] { flex:1; min-width:140px; accent-color:#facc15; }
  .muted { color:var(--muted); font-size:12px; }
  .legend { position:absolute; right:12px; top:84px; white-space:nowrap; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 12px; font-size:12px; line-height:1.8; backdrop-filter:blur(8px); pointer-events:auto; }
  .legend i { display:inline-block; vertical-align:middle; margin-right:6px; }
  .legend .bar { width:22px; height:5px; border-radius:3px; background:linear-gradient(90deg,#facc15 65%, rgba(255,255,255,.25) 65%); }
  .legend .flame { width:12px; height:12px; border-radius:50%; background:radial-gradient(#fff7cc, #fb923c 55%, rgba(251,146,60,0)); }
  .legend .pack { width:8px; height:14px; border-radius:4px 4px 2px 2px; background:linear-gradient(#1d4ed8 0 30%, #f8fafc 30% 62%, #1d4ed8 62%); box-shadow:0 0 8px #38bdf8; }
  .top { flex-direction:column; align-items:center; gap:6px; }
  .legend .x { float:right; cursor:pointer; color:var(--muted); margin-left:10px; }
  /* 高光回放：转场标志 + 回放角标 */
  .stinger { position:absolute; inset:0; pointer-events:none; overflow:hidden; visibility:hidden; z-index:20; }
  .stinger.run { visibility:visible; }
  .stinger .band { position:absolute; top:-20%; bottom:-20%; left:-30%; width:160%; transform:translateX(-140%) skewX(-18deg); }
  .stinger .b1 { background:#f2b21a; }
  .stinger .b2 { background:#2563eb; }
  /* 纯净画面（拍宣传片用）：藏起所有界面（比分牌、控制栏、说明、数据、进球字幕、转场、REPLAY 角标），只留 3D 画面 */
  body.clean .hud, body.clean .legend, body.clean .stats, body.clean .goal, body.clean .stinger, body.clean .rtag { display:none !important; }
  .toast { position:absolute; left:50%; top:16px; transform:translateX(-50%); padding:6px 14px; border-radius:8px; background:rgba(5,11,28,.8);
    color:#e6fbff; font:600 13px system-ui,sans-serif; opacity:0; transition:opacity .3s; pointer-events:none; z-index:30; white-space:nowrap; }
  .toast.show { opacity:1; }
  .stinger .b3 { background:linear-gradient(100deg,#0b1636,#13235a 55%,#0b1636); }
  /* 转场共 2.2 秒：画面先渐暗、色带缓入盖住画面 -> 标志淡入停留 -> 标志淡出、色带缓出、画面渐亮 */
  .stinger .veil { position:absolute; inset:0; background:#050b1c; opacity:0; }
  .stinger.run .veil { animation:veil 2.2s linear both; }
  @keyframes veil { 0% { opacity:0; } 30% { opacity:.55; } 70% { opacity:.55; } 100% { opacity:0; } }
  .stinger .band { opacity:.96; }
  .stinger.run .b1 { animation:wipe 2.2s both; }
  .stinger.run .b2 { animation:wipe 2.2s .06s both; }
  .stinger.run .b3 { animation:wipe 2.2s .12s both; }
  @keyframes wipe {
    0%   { transform:translateX(-140%) skewX(-18deg); animation-timing-function:cubic-bezier(.25,.75,.35,1); }
    36%  { transform:translateX(0) skewX(-18deg); }
    62%  { transform:translateX(0) skewX(-18deg); animation-timing-function:cubic-bezier(.65,0,.75,.25); }
    100% { transform:translateX(140%) skewX(-18deg); } }
  .stinger .emblem { position:absolute; left:50%; top:50%; width:min(46vw,340px); transform:translate(-50%,-50%) scale(.7); opacity:0; }
  .stinger.run .emblem { animation:pop 2.2s ease-in-out both; }
  @keyframes pop {
    0%, 26% { opacity:0; transform:translate(-50%,-50%) scale(.72); filter:blur(6px); }
    40%     { opacity:1; transform:translate(-50%,-50%) scale(1); filter:blur(0); }
    58%     { opacity:1; transform:translate(-50%,-50%) scale(1.04); filter:blur(0); }
    72%,100%{ opacity:0; transform:translate(-50%,-50%) scale(1.14); filter:blur(4px); } }
  .rtag { position:absolute; left:14px; top:14px; display:flex; align-items:center; gap:8px; padding:6px 12px 6px 8px; border-radius:8px;
          background:rgba(11,22,54,.85); border:1px solid rgba(242,178,26,.7); color:#fff; font-weight:800; letter-spacing:2px; font-size:14px;
          opacity:0; transform:translateX(-12px); transition:opacity .2s, transform .2s; pointer-events:none; z-index:5; }
  .rtag.show { opacity:1; transform:none; }
  .rtag i { width:10px; height:10px; border-radius:50%; background:#f2b21a; animation:blink 1s infinite; }
  .rtag small { color:#f2b21a; font-weight:700; letter-spacing:1px; font-size:12px; }
  @keyframes blink { 50% { opacity:.25; } }
  .stats { position:absolute; left:12px; top:84px; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:8px 10px; font-size:12px; backdrop-filter:blur(8px); display:none; pointer-events:auto; }
  .stats table { border-collapse:collapse; } .stats td, .stats th { padding:3px 8px; text-align:left; white-space:nowrap; font-variant-numeric:tabular-nums; }
  .err { position:absolute; inset:0; display:none; align-items:center; justify-content:center; text-align:center; padding:24px; }
  /* 手机：竖屏和横屏都要能看到完整球场，界面压缩，镜头按剩余空间自动取景 */
  .row.cams { flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none; -webkit-overflow-scrolling:touch; }
  .row.cams::-webkit-scrollbar { display:none; }
  .row.cams button { flex:none; }
  @media (max-width: 640px) {
    .team { padding:5px 8px; font-size:13px; gap:6px; } .num { font-size:22px; } .mid { padding:3px 10px; }
    .bottom { padding:8px; gap:6px; } button, select { padding:5px 9px; font-size:13px; } #tick { display:none; }
    .legend { top:auto; bottom:96px; left:8px; right:8px; white-space:normal; }
    .rtag { top:64px; } .stats { top:108px; left:8px; right:8px; overflow-x:auto; }
  }
  @media (max-height: 520px) {
    .top { top:6px; } .team { padding:3px 10px; font-size:12px; gap:6px; } .team .dot { width:9px; height:9px; }
    .num { font-size:18px; } .clock { font-size:10px; } .mid { padding:2px 12px; }
    .bottom { padding:6px 10px; gap:5px; } button, select { padding:3px 9px; font-size:12px; border-radius:6px; }
    .legend { top:50px; bottom:auto; right:10px; left:auto; font-size:11px; line-height:1.6; padding:6px 10px; max-height:calc(100% - 130px); overflow:auto; }
    .rtag { top:6px; left:8px; padding:4px 8px; font-size:12px; } .stats { top:50px; } #tick { display:none; }
    .goal { top:30%; }
  }
</style>
</head>
<body>
<div id="app"></div>
<div class="hud top"><div class="board">
  <div class="team a"><span class="dot"></span><span id="na"></span></div>
  <div class="mid"><div class="num" id="sc">0 : 0</div><div class="clock" id="clock">0:00</div></div>
  <div class="team b"><span id="nb"></span><span class="dot"></span></div>
</div></div>
<div class="goal" id="goal"></div>
<div class="stinger" id="stinger"><div class="veil"></div><div class="band b1"></div><div class="band b2"></div><div class="band b3"></div>
<svg class="emblem" viewBox="0 0 340 240" xmlns="http://www.w3.org/2000/svg">
  <polygon points="170,6 318,62 318,178 170,234 22,178 22,62" fill="#0b1636" stroke="#f2b21a" stroke-width="7"/>
  <polygon points="170,22 302,72 302,168 170,218 38,168 38,72" fill="none" stroke="#2563eb" stroke-width="3"/>
  <defs><clipPath id="bc"><circle cx="170" cy="72" r="29"/></clipPath></defs>
  <g clip-path="url(#bc)">
    <rect x="130" y="32" width="80" height="80" fill="#f7f8fa"/>
    <polygon points="150,30 214,30 214,94" fill="#0e1b42"/>
    <polygon points="140,30 144,30 214,100 214,104" fill="#f2b21a"/>
    <polygon points="126,48 126,120 198,120" fill="#2563eb"/>
    <path d="M141 72 Q170 62 199 72 M170 43 Q160 72 170 101" stroke="#aab2c0" stroke-width="1.6" fill="none"/>
  </g>
  <circle cx="170" cy="72" r="29" fill="none" stroke="#f7f8fa" stroke-width="2"/>
  <text x="170" y="150" text-anchor="middle" font-family="system-ui,'Arial Black',sans-serif" font-size="44" font-weight="900" font-style="italic" fill="#fff" letter-spacing="2">AI ARENA</text>
  <text id="stLabel" x="170" y="190" text-anchor="middle" font-family="system-ui,sans-serif" font-size="22" font-weight="800" fill="#f2b21a" letter-spacing="8">REPLAY</text>
</svg></div>
<div class="toast" id="toast"></div>
<div class="rtag" id="rtag"><i></i>REPLAY <small id="rtagSub">回放</small></div>

<div class="legend" id="legend"><span class="x" id="lx">✕</span>
  <div><i class="bar"></i>头顶黄条 = 剩余氮气</div>
  <div><i class="flame"></i>背包喷火 + 橙色光晕 = 正在用氮气</div>
  <div><i class="pack"></i>氮气瓶：碰到补满，地上圆环是刷新倒计时</div>
  <div class="muted">进球后自动播放慢动作回放，"高光集锦"连播全场进球</div>
  <div class="muted">拖动旋转 · 滚轮/双指缩放 · 空格播放</div>
  <div class="muted">拍宣传片：T 开关头顶标号，H 或"纯净画面"隐藏全部界面（纯净画面里单击播放/暂停，双击或按 H 退出）；网址加 ?clean=1 直接进入纯净画面，?labels=0 只关标号</div>
</div>
<div class="stats" id="stats"></div>
<div class="hud bottom">
  <div class="row">
    <button id="play">▶ 播放</button>
    <select id="speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option><option value="8">8×</option></select>
    <input type="range" id="seek" min="0" value="0" step="1">
    <span class="muted" id="tick"></span>
  </div>
  <div class="row cams">
    <button data-cam="tv" class="on">转播</button>
    <button data-cam="follow">跟随球</button>
    <button data-cam="top">俯视</button>
    <button data-cam="goalA">绿方门后</button>
    <button data-cam="goalB">红方门后</button>
    <button data-cam="free">自由</button>
    <button id="statsBtn">数据</button>
    <button id="hlBtn">▶ 高光集锦</button>
    <button id="autoRp" class="on">进球自动回放</button>
    <button id="sndBtn" class="on">🔊 音效</button>
    <button id="tagBtn" class="on">头顶标号</button>
    <button id="cleanBtn">纯净画面</button>
    <button id="helpBtn">说明</button>
  </div>
</div>
<div class="err" id="err">这个浏览器不支持 WebGL，无法显示 3D 回放。</div>
<script>__THREE__</script>
<script>
const R = __REPLAY__;
const M = R.meta, F = R.frames, A = M.arena;
const COL_A = 0x22c55e, COL_B = 0xf97316;  // 绿队 / 红队（参考 CodeBall 原版的绿、橙红配色）
const $ = id => document.getElementById(id);
// 网址参数（? 或 # 后面都行），拍宣传片用：clean=1 纯净画面，labels=0 关头顶标号，w/h 固定渲染分辨率（满画质），fps 逐帧截图的帧率
const OPT = new URLSearchParams(location.search.slice(1) + '&' + location.hash.slice(1));
const optOff = k => ['0', 'false', 'off', 'no'].includes((OPT.get(k) || '').toLowerCase());
const optOn = k => OPT.has(k) && !optOff(k);
const CAPW = Math.round(+OPT.get('w') || 0), CAPH = Math.round(+OPT.get('h') || 0), FIXED = CAPW > 0 && CAPH > 0;
// 固定种子的随机数（mulberry32）：观众配色、地面噪点等每次打开都一样，逐帧截图才能复现
function seededRandom(seed) { let a = seed | 0; return () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
Math.random = seededRandom(+OPT.get('seed') || 20181);
$('na').textContent = R.bots[0]; $('nb').textContent = R.bots[1];
$('lx').onclick = () => $('legend').style.display = 'none';
// 小屏（手机竖屏或横屏）默认收起说明，点"说明"再打开
if (innerWidth < 900 || innerHeight < 520) $('legend').style.display = 'none';
$('helpBtn').onclick = () => { const l = $('legend'); l.style.display = l.style.display === 'none' ? '' : 'none'; };

// ---------------------------------------------------------------- 渲染器
let renderer;
try { renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' }); }
catch (e) { $('err').style.display = 'flex'; throw e; }
const MOBILE = !FIXED && (matchMedia('(pointer: coarse)').matches || Math.min(innerWidth, innerHeight) < 600);
let PR = FIXED ? 1 : Math.min(devicePixelRatio, MOBILE ? 1.5 : 2);   // 固定分辨率（拍片）时按 1:1 像素出图          // 手机屏幕像素密度很高，按 1.5 倍渲染已经够清晰，省下大量填充开销
renderer.setPixelRatio(PR);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
$('app').appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070b14);
scene.fog = new THREE.Fog(0x070b14, 140, 320);
const camera = new THREE.PerspectiveCamera(45, 1, 0.5, 1000);

const W2 = A.width / 2, D2 = A.depth / 2, H = A.height, CR = A.corner_radius;
const GW2 = A.goal_width / 2, GH = A.goal_height, GD = A.goal_depth;

// ---------------------------------------------------------------- 灯光
scene.add(new THREE.HemisphereLight(0xbfd8ff, 0x1a1f2a, 0.6));
const sun = new THREE.DirectionalLight(0xfff4e0, 1.15);
sun.position.set(-40, 90, 30);
sun.castShadow = true;
{ const ms = FIXED ? 4096 : MOBILE ? 1024 : 2048; sun.shadow.mapSize.set(ms, ms); }
Object.assign(sun.shadow.camera, { left: -75, right: 75, top: 75, bottom: -75, near: 10, far: 220 });
sun.shadow.bias = -0.0005;
scene.add(sun);
const fill = new THREE.DirectionalLight(0x9ec5ff, 0.35); fill.position.set(50, 40, -40); scene.add(fill);

// ---------------------------------------------------------------- 工具
// 合并网格减少绘制调用（draw call）：把同一个父节点下、用同一种材质的多个小网格合成一个网格。
// 机器人由几十个小零件拼成，整圈墙也有几十段，不合并的话每帧要提交几百次绘制，手机上很容易掉帧。
function mergeChildren(parent, keep) {
  const groups = new Map();
  for (const c of parent.children) if (c.isMesh && !c.isInstancedMesh && !(keep && keep.has(c))) {
    if (!groups.has(c.material)) groups.set(c.material, []); groups.get(c.material).push(c);
  }
  for (const [mat, list] of groups) {
    if (list.length < 2) continue;
    const parts = list.map(m => { m.updateMatrix(); const g = (m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone()); g.applyMatrix4(m.matrix); return g; });
    const names = Object.keys(parts[0].attributes).filter(n => parts.every(g => g.attributes[n] && g.attributes[n].itemSize === parts[0].attributes[n].itemSize));
    const out = new THREE.BufferGeometry();
    for (const n of names) {
      const size = parts[0].attributes[n].itemSize, arr = new Float32Array(parts.reduce((a, g) => a + g.attributes[n].count * size, 0));
      let o = 0; for (const g of parts) { arr.set(g.attributes[n].array, o); o += g.attributes[n].array.length; }
      out.setAttribute(n, new THREE.BufferAttribute(arr, size));
    }
    const merged = new THREE.Mesh(out, mat);
    merged.castShadow = list.some(m => m.castShadow); merged.receiveShadow = list.some(m => m.receiveShadow); merged.renderOrder = list[0].renderOrder;
    list.forEach(m => { parent.remove(m); m.geometry.dispose(); });
    parts.forEach(g => g.dispose());
    parent.add(merged);
  }
}
// 贴图尺寸要适配设备：不能超过显卡的最大贴图尺寸（很多手机是 4096），只支持 WebGL1 的设备还要求边长是 2 的幂。
// 不满足时 three.js 会自己缩放并打出 "Texture has been resized" 警告，所以这里先按设备能力缩放好。
function fitCanvas(c) {
  const cap = renderer.capabilities, max = cap.maxTextureSize || 4096;
  const pot = v => Math.pow(2, Math.round(Math.log2(v)));
  let w = cap.isWebGL2 ? c.width : pot(c.width), h = cap.isWebGL2 ? c.height : pot(c.height);
  w = Math.min(w, max); h = Math.min(h, max);
  if (w === c.width && h === c.height) return c;
  const o = document.createElement('canvas'); o.width = w; o.height = h;
  const g = o.getContext('2d'); g.imageSmoothingQuality = 'high'; g.drawImage(c, 0, 0, w, h);
  return o;
}
function canvasTex(w, h, draw, repeat) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(fitCanvas(c));
  t.redraw = () => { const c2 = document.createElement('canvas'); c2.width = w; c2.height = h; draw(c2.getContext('2d'), w, h); t.image = fitCanvas(c2); t.needsUpdate = true; };
  t.encoding = THREE.sRGBEncoding;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]); }
  return t;
}
function roundedOutline(inset, n, extraZ = 0) {  // 场地俯视轮廓（四角圆弧），返回 [x, z] 列表（逆时针）；extraZ 让两端再往外延伸
  const w = W2 - inset, d = D2 - inset + extraZ, r = Math.max(0.01, CR - inset), pts = [];
  const cs = [[w - r, d - r, 0], [-(w - r), d - r, Math.PI / 2], [-(w - r), -(d - r), Math.PI], [w - r, -(d - r), 1.5 * Math.PI]];
  for (const [cx, cz, a0] of cs) for (let i = 0; i <= n; i++) { const a = a0 + i / n * Math.PI / 2; pts.push([cx + r * Math.cos(a), cz + r * Math.sin(a)]); }
  return pts;
}

// ---------------------------------------------------------------- 场地地面（科技风：深灰地面 + 霓虹青色场线）
const PX = 16;  // 每米像素
function fieldLines(g, core) {                      // 画全部场线（core=false 画外发光，true 画亮芯）
  const X = x => (x + W2) * PX, Z = z => (z + D2) * PX;
  g.beginPath(); roundedOutline(1.2, 16).forEach(([x, z], i) => i ? g.lineTo(X(x), Z(z)) : g.moveTo(X(x), Z(z))); g.closePath(); g.stroke();
  g.beginPath(); g.moveTo(X(-W2 + 1.2), Z(0)); g.lineTo(X(W2 - 1.2), Z(0)); g.stroke();
  g.beginPath(); g.arc(X(0), Z(0), 9 * PX, 0, Math.PI * 2); g.stroke();
  g.beginPath(); g.arc(X(0), Z(0), 2.2 * PX, 0, Math.PI * 2); g.stroke();
  for (const s of [-1, 1]) {
    const zl = s * (D2 - 1.2);
    g.strokeRect(X(-GW2 - 5), Math.min(Z(zl), Z(zl - s * 14)), (A.goal_width + 10) * PX, 14 * PX);
    g.strokeRect(X(-GW2 + 3), Math.min(Z(zl), Z(zl - s * 6)), (A.goal_width - 6) * PX, 6 * PX);
    g.beginPath(); g.arc(X(0), Z(zl - s * 14), 6 * PX, s < 0 ? 0 : Math.PI, s < 0 ? Math.PI : 2 * Math.PI); g.stroke();
  }
}
const floorTex = canvasTex(A.width * PX, A.depth * PX, (g, w, h) => {
  g.fillStyle = '#2a2e35'; g.fillRect(0, 0, w, h);
  // 类似橡胶/沥青的细颗粒 + 大块拼接地板的接缝
  const img = g.getImageData(0, 0, w, h), d = img.data;
  for (let i = 0; i < d.length; i += 4) { const n = (Math.random() - 0.5) * 12; d[i] += n; d[i + 1] += n; d[i + 2] += n * 1.1; }
  g.putImageData(img, 0, 0);
  g.strokeStyle = 'rgba(0,0,0,0.25)'; g.lineWidth = 2;
  for (let x = 0; x <= w; x += 10 * PX) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
  for (let z = 0; z <= h; z += 10 * PX) { g.beginPath(); g.moveTo(0, z); g.lineTo(w, z); g.stroke(); }
  // 中圈里淡淡的六边形纹理
  g.save(); g.beginPath(); g.arc(w / 2, h / 2, 9 * PX, 0, Math.PI * 2); g.clip();
  g.strokeStyle = 'rgba(120,200,255,0.10)'; g.lineWidth = 2; const r = 1.4 * PX;
  for (let j = -8; j <= 8; j++) for (let i = -8; i <= 8; i++) {
    const cx = w / 2 + (i + (j & 1) * 0.5) * Math.sqrt(3) * r, cy = h / 2 + j * 1.5 * r;
    g.beginPath(); for (let k = 0; k < 6; k++) { const an = Math.PI / 6 + k * Math.PI / 3; g[k ? 'lineTo' : 'moveTo'](cx + r * Math.cos(an), cy + r * Math.sin(an)); } g.closePath(); g.stroke();
  }
  g.restore();
  // 球门区用队色微微染一下
  for (const s of [-1, 1]) {
    const zl = s * (D2 - 1.2);
    g.fillStyle = s < 0 ? 'rgba(34,197,94,0.07)' : 'rgba(249,115,22,0.07)';
    g.fillRect((-GW2 - 5 + W2) * PX, Math.min(zl - s * 14, zl) * PX + D2 * PX, (A.goal_width + 10) * PX, 14 * PX);
  }
  g.lineJoin = 'round';
  g.strokeStyle = 'rgba(80,220,255,0.35)'; g.lineWidth = 0.3 * PX; fieldLines(g);
});
const lineTex = canvasTex(A.width * PX, A.depth * PX, (g, w, h) => {   // 自发光贴图：场线外发光 + 亮芯
  g.fillStyle = '#000'; g.fillRect(0, 0, w, h); g.lineJoin = 'round';
  for (const [lw, c] of [[1.6, 'rgba(14,165,233,0.10)'], [0.9, 'rgba(34,211,238,0.22)'], [0.45, 'rgba(56,220,255,0.65)'], [0.2, 'rgba(200,250,255,1)']]) {
    g.strokeStyle = c; g.lineWidth = lw * PX; fieldLines(g);
  }
});
const floorShape = new THREE.Shape();
roundedOutline(0, 24).forEach(([x, z], i) => i ? floorShape.lineTo(x, -z) : floorShape.moveTo(x, -z));
const floorGeo = new THREE.ShapeGeometry(floorShape, 24);
{ // UV 按世界坐标映射到整张贴图
  const pos = floorGeo.attributes.position, uv = floorGeo.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, (pos.getX(i) + W2) / A.width, (D2 - pos.getY(i)) / A.depth);
}
floorTex.flipY = lineTex.flipY = false;
const floor = new THREE.Mesh(floorGeo, new THREE.MeshStandardMaterial({ map: floorTex, emissiveMap: lineTex, emissive: 0xffffff, emissiveIntensity: 1.25, roughness: 0.55, metalness: 0.25 }));
floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);

// 球门内地面
for (const s of [-1, 1]) {
  const g = new THREE.Mesh(new THREE.PlaneGeometry(A.goal_width, GD), new THREE.MeshStandardMaterial({ color: 0x24282f, roughness: 0.6, metalness: 0.2 }));
  g.rotation.x = -Math.PI / 2; g.position.set(0, 0.005, s * (D2 + GD / 2)); g.receiveShadow = true; scene.add(g);
}
// 场外地面
const outer = new THREE.Mesh(new THREE.PlaneGeometry(600, 600), new THREE.MeshStandardMaterial({ color: 0x0b0f17, roughness: 1 }));
outer.rotation.x = -Math.PI / 2; outer.position.y = -0.02; outer.receiveShadow = true; scene.add(outer);

// ---------------------------------------------------------------- 墙面：下部灰色挡板 + 青色灯带，上部发光的六边形能量墙（绿队半场偏青，红队半场偏橙）
const HEX_R = 1.6, HEX_W = Math.sqrt(3) * HEX_R, HEX_H = 3 * HEX_R;   // 贴图一个周期覆盖的世界尺寸
const hexTex = canvasTex(256, Math.round(256 * HEX_H / HEX_W), (g, w, h) => {
  const r = w / Math.sqrt(3);
  g.clearRect(0, 0, w, h);
  for (let j = -1; j <= 2; j++) for (let i = -1; i <= 1; i++) {
    const cx = (i + (j & 1) * 0.5) * w, cy = j * 1.5 * r;
    const hex = () => { g.beginPath(); for (let k = 0; k < 6; k++) { const an = Math.PI / 6 + k * Math.PI / 3; g[k ? 'lineTo' : 'moveTo'](cx + r * 0.94 * Math.cos(an), cy + r * 0.94 * Math.sin(an)); } g.closePath(); };
    const gr = g.createRadialGradient(cx, cy, 0, cx, cy, r);
    gr.addColorStop(0, 'rgba(255,255,255,0.03)'); gr.addColorStop(0.7, 'rgba(255,255,255,0.12)'); gr.addColorStop(1, 'rgba(255,255,255,0.4)');
    hex(); g.fillStyle = gr; g.fill();
    g.strokeStyle = 'rgba(255,255,255,0.35)'; g.lineWidth = 9; hex(); g.stroke();
    g.strokeStyle = 'rgba(255,255,255,1)'; g.lineWidth = 3; hex(); g.stroke();
  }
}, [1, 1]);
// 镜头在场外（转播、俯视）时，挡在镜头和球场之间的那几面墙要几乎透明，否则六边形会糊满整个画面：
// 每个顶点带一个指向场内的法线，片元里看镜头在墙的哪一侧来决定透明度
const camU = { value: camera.position };            // MeshBasicMaterial 不会自动上传 cameraPosition，自己传
function nearWallFade(mat, floorA) {
  mat.onBeforeCompile = sh => {
    sh.uniforms.uCam = camU;
    sh.vertexShader = 'attribute vec3 inward;\nvarying vec3 vWP;\nvarying vec3 vIn;\n' + sh.vertexShader.replace('#include <begin_vertex>',
      '#include <begin_vertex>\nvWP = (modelMatrix * vec4(position, 1.0)).xyz; vIn = inward;');
    sh.fragmentShader = 'uniform vec3 uCam;\nvarying vec3 vWP;\nvarying vec3 vIn;\n' + sh.fragmentShader.replace('#include <dithering_fragment>',
      '#include <dithering_fragment>\ngl_FragColor.a *= mix(' + floorA.toFixed(2) + ', 1.0, smoothstep(-1.0, 1.5, dot(uCam - vWP, normalize(vIn))));');
  };
  return mat;
}
const hexMat = nearWallFade(new THREE.MeshBasicMaterial({ map: hexTex, vertexColors: true, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }), 0.04);
const glass = nearWallFade(new THREE.MeshBasicMaterial({ color: 0x040b16, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false }), 0.05);  // 深色玻璃，压暗墙后的看台，六边形更显眼
const boardMat = new THREE.MeshStandardMaterial({ color: 0xc3c9d2, roughness: 0.5, metalness: 0.35, side: THREE.DoubleSide });
const ledMat = new THREE.MeshBasicMaterial({ color: 0x5ee7ff, side: THREE.DoubleSide });
const edgeMat = new THREE.LineBasicMaterial({ color: 0x8fd3ff, transparent: true, opacity: 0.55 });
const BOARD = 2.4;                                   // 挡板高度
const cA = new THREE.Color(0x10d8b0).convertSRGBToLinear(), cM = new THREE.Color(0x2f7dff).convertSRGBToLinear(), cB = new THREE.Color(0xff6a10).convertSRGBToLinear();
function hexColor(z) { const t = (z + D2) / (2 * D2); return t < 0.5 ? cA.clone().lerp(cM, t * 2) : cM.clone().lerp(cB, t * 2 - 1); }
let wallU = 0;                                       // 沿墙的累计长度，让六边形在相邻墙段之间接得上
// 各家赞助商的代表性标识（手绘近似图形，中心在原点，r 为半径）
function rrect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
const SPONSOR_TEX = [];                              // 用到赞助商标识的贴图，豆包头像加载完后要重绘
const DOUBAO_IMG = new Image();
DOUBAO_IMG.onload = () => SPONSOR_TEX.forEach(t => t && t.redraw());
DOUBAO_IMG.src = '__DOUBAO__';
const ICONS = {
  // Anthropic：A\ 字形——平顶的 A，右边一道和右腿平行的斜杠
  anthropic(g, r, col) {
    g.strokeStyle = col; g.lineWidth = r * 0.3; g.lineCap = 'butt'; g.lineJoin = 'miter';
    g.beginPath(); g.moveTo(-r * 0.98, r * 0.85); g.lineTo(-r * 0.5, -r * 0.7); g.lineTo(-r * 0.16, -r * 0.7); g.lineTo(r * 0.32, r * 0.85); g.stroke();
    g.beginPath(); g.moveTo(-r * 0.62, r * 0.32); g.lineTo(r * 0.0, r * 0.32); g.stroke();
    g.beginPath(); g.moveTo(r * 0.3, -r * 0.7); g.lineTo(r * 0.78, r * 0.85); g.stroke();
  },
  // OpenAI：六瓣花结
  knot(g, r, col) {
    g.strokeStyle = col; g.lineWidth = r * 0.145; g.lineCap = 'round'; g.lineJoin = 'round';
    const x0 = -r * 0.2, x1 = r * 0.36, top = -r * 0.64;
    for (let k = 0; k < 6; k++) { g.save(); g.rotate(k * Math.PI / 3); g.beginPath();
      g.moveTo(x0, -r * 0.27); g.lineTo(x0, top); g.arc((x0 + x1) / 2, top, (x1 - x0) / 2, Math.PI, 0); g.lineTo(x1, -r * 0.05); g.stroke(); g.restore(); }
  },
  // Google DeepMind / Gemini：四角星，蓝紫渐变
  gemini(g, r) {
    const gr = g.createLinearGradient(-r, r, r, -r); gr.addColorStop(0, '#1c7df1'); gr.addColorStop(0.55, '#6f7ff5'); gr.addColorStop(1, '#a86ff0');
    g.fillStyle = gr; g.beginPath(); g.moveTo(0, -r);
    for (const [ax, ay, bx, by] of [[1, -1, 1, 0], [1, 1, 0, 1], [-1, 1, -1, 0], [-1, -1, 0, -1]]) g.quadraticCurveTo(ax * r * 0.08, ay * r * 0.08, bx * r, by * r);
    g.closePath(); g.fill();
  },
  // Meta：无限环
  meta(g, r) {
    const gr = g.createLinearGradient(-r, 0, r, 0); gr.addColorStop(0, '#0064e0'); gr.addColorStop(1, '#0082fb');
    g.strokeStyle = gr; g.lineWidth = r * 0.26; g.lineCap = 'round'; g.beginPath();
    for (let i = 0; i <= 80; i++) { const t = i / 80 * Math.PI * 2, d = 1 + Math.sin(t) ** 2, x = r * 1.05 * Math.cos(t) / d, y = r * 0.95 * Math.sin(t) * Math.cos(t) / d * 1.25; i ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.stroke();
  },
  // Mistral：像素方块拼的 M，从上到下黄→橙→红
  mistral(g, r) {
    const s = r * 2 / 5, rows = ['#ffd800', '#ffaf00', '#ff8205', '#fa500f', '#e10500'];
    const M = ['10001', '11011', '10101', '10001', '10001'];
    M.forEach((row, j) => [...row].forEach((c, i) => { if (c === '1') { g.fillStyle = rows[j]; g.fillRect(-r + i * s, -r + j * s, s + 0.5, s + 0.5); } }));
  },
  // xAI：粗斜杠 X，一笔加长
  xai(g, r, col) {
    g.fillStyle = col; g.lineCap = 'butt';
    g.beginPath(); g.moveTo(-r * 0.85, -r * 0.85); g.lineTo(-r * 0.5, -r * 0.85); g.lineTo(r * 0.85, r * 0.85); g.lineTo(r * 0.5, r * 0.85); g.closePath(); g.fill();
    g.beginPath(); g.moveTo(r * 0.95, -r); g.lineTo(r * 0.72, -r); g.lineTo(r * 0.06, -r * 0.22); g.lineTo(r * 0.2, -r * 0.05); g.closePath(); g.fill();
    g.beginPath(); g.moveTo(-r * 0.2, r * 0.12); g.lineTo(-r * 0.05, r * 0.3); g.lineTo(-r * 0.55, r * 0.85); g.lineTo(-r * 0.85, r * 0.85); g.closePath(); g.fill();
  },
  // DeepSeek：蓝色小鲸鱼
  deepseek(g, r) {
    g.fillStyle = '#4d6bfe'; g.beginPath();
    g.moveTo(-r * 0.95, -r * 0.05);
    g.bezierCurveTo(-r * 0.9, -r * 0.75, r * 0.35, -r * 0.85, r * 0.62, -r * 0.2);
    g.quadraticCurveTo(r * 0.78, -r * 0.55, r * 1.0, -r * 0.62); g.quadraticCurveTo(r * 0.92, -r * 0.3, r * 0.72, -r * 0.05);
    g.quadraticCurveTo(r * 0.9, r * 0.1, r * 0.98, r * 0.35); g.quadraticCurveTo(r * 0.7, r * 0.3, r * 0.55, r * 0.18);
    g.bezierCurveTo(r * 0.3, r * 0.75, -r * 0.7, r * 0.75, -r * 0.95, -r * 0.05); g.closePath(); g.fill();
    g.fillStyle = '#ffffff'; g.beginPath(); g.arc(-r * 0.45, -r * 0.18, r * 0.09, 0, Math.PI * 2); g.fill();
  },
  // Qwen：紫色六边形扭结
  qwen(g, r) {
    const gr = g.createLinearGradient(-r, -r, r, r); gr.addColorStop(0, '#6f5cf5'); gr.addColorStop(1, '#4b3ce0');
    g.strokeStyle = gr; g.lineWidth = r * 0.3; g.lineJoin = 'round';
    for (let k = 0; k < 3; k++) { g.save(); g.rotate(k * Math.PI * 2 / 3); g.beginPath(); g.moveTo(-r * 0.15, -r * 0.82); g.lineTo(r * 0.72, -r * 0.82 + r * 0.0); g.lineTo(r * 0.32, -r * 0.1); g.stroke(); g.restore(); }
  },
  // Kimi：黑色圆角方块、白色 K、右上角蓝点
  kimi(g, r) {
    g.fillStyle = '#111111'; rrect(g, -r, -r, r * 2, r * 2, r * 0.42); g.fill();
    g.strokeStyle = '#ffffff'; g.lineWidth = r * 0.24; g.lineCap = 'round'; g.lineJoin = 'round';
    g.beginPath(); g.moveTo(-r * 0.38, -r * 0.5); g.lineTo(-r * 0.38, r * 0.52); g.moveTo(r * 0.3, -r * 0.45); g.lineTo(-r * 0.3, r * 0.02); g.lineTo(r * 0.36, r * 0.52); g.stroke();
    g.fillStyle = '#1783ff'; g.beginPath(); g.arc(r * 0.5, -r * 0.55, r * 0.17, 0, Math.PI * 2); g.fill();
  },
  // 智谱：照 mr.wang 给的参考图描的几何 Z——上下两块平行四边形，中间一道带折角的斜条
  zhipu(g, r, col) {
    const k = r / 430, P = [
      [[469, 275], [1065, 275], [855, 462], [263, 462]],
      [[665, 502], [833, 502], [908, 437], [958, 536], [613, 787], [472, 787], [385, 857], [330, 748]],
      [[450, 827], [1023, 827], [805, 1010], [235, 1010]],
    ];
    g.fillStyle = col;
    for (const poly of P) { g.beginPath(); poly.forEach(([x, y], i) => g[i ? 'lineTo' : 'moveTo']((x - 650) * k, (y - 642) * k)); g.closePath(); g.fill(); }
  },
  // 豆包：mr.wang 给的红围巾女孩头像（assets/doubao.webp），裁成圆形；图片还没加载完时先画底色，加载完后重绘广告贴图
  doubao(g, r) {
    const gr = g.createLinearGradient(0, -r, 0, r); gr.addColorStop(0, '#e8f0ff'); gr.addColorStop(1, '#c9dafc');
    g.save(); g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.fillStyle = gr; g.fill(); g.clip();
    if (DOUBAO_IMG.complete && DOUBAO_IMG.naturalWidth) g.drawImage(DOUBAO_IMG, -r, -r, r * 2, r * 2);
    g.restore();
    g.save(); g.shadowBlur = 0; g.strokeStyle = '#2b5cff'; g.lineWidth = r * 0.07; g.beginPath(); g.arc(0, 0, r * 0.965, 0, Math.PI * 2); g.stroke(); g.restore();
  },
  // MiniMax：高低错落的圆头竖条（声波），粉红到橙的渐变
  minimax(g, r) {
    const gr = g.createLinearGradient(-r, 0, r, 0); gr.addColorStop(0, '#e2167e'); gr.addColorStop(1, '#fe603c');
    g.strokeStyle = gr; g.lineWidth = r * 0.2; g.lineCap = 'round';
    const hs = [0.35, 0.8, 0.5, 0.95, 0.45, 0.75, 0.3];
    hs.forEach((h, i) => { const x = -r * 0.9 + i * r * 0.3, y0 = (i % 2 ? -0.15 : 0.15) * r; g.beginPath(); g.moveTo(x, y0 - h * r * 0.7); g.lineTo(x, y0 + h * r * 0.5); g.stroke(); });
  },
};
// 赞助商（仿照体育赛事场边广告）：每家是"代表性标识 + 名称"，标识都是照着各家标志手绘的近似图形，名称用各家的品牌色
const SANS = 'system-ui, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif';
const SPONSORS = [
  { t: 'ANTHROPIC', c: '#191919', f: '600 70px Georgia, "Times New Roman", serif', ls: 12, icon: 'anthropic', mono: true },
  { t: 'OpenAI', c: '#0d0d0d', f: '700 80px ' + SANS, ls: 0, icon: 'knot', mono: true },
  { t: 'Google DeepMind', c: '#1a73e8', f: '500 66px ' + SANS, ls: 0, icon: 'gemini' },
  { t: 'Meta AI', c: '#0866ff', f: '700 80px ' + SANS, ls: 0, icon: 'meta' },
  { t: 'DeepSeek', c: '#4d6bfe', f: '700 80px ' + SANS, ls: 0, icon: 'deepseek' },
  { t: 'Qwen 千问', c: '#615ced', f: '700 76px ' + SANS, ls: 0, icon: 'qwen' },
  { t: 'Kimi', c: '#111111', f: '800 84px ' + SANS, ls: 0, icon: 'kimi' },
  { t: '智谱 GLM', c: '#111111', f: '700 76px ' + SANS, ls: 0, icon: 'zhipu', mono: true },
  { t: 'MiniMax', c: '#e2167e', f: '800 80px ' + SANS, ls: 0, icon: 'minimax' },
  { t: '豆包', c: '#2b5cff', f: '800 84px ' + SANS, ls: 2, icon: 'doubao' },
];
function drawSponsor(g, sp, cx, cy, maxW, glow) {   // glow 不为空时是 LED 屏样式：白字 + 品牌色光晕
  g.save(); g.font = sp.f; g.textBaseline = 'middle';
  if ('letterSpacing' in g) g.letterSpacing = sp.ls + 'px';
  const px = parseInt(sp.f.match(/(\d+)px/)[1]), iw = sp.icon ? px * 1.2 : 0, gap = sp.icon ? px * 0.35 : 0;
  const tw = g.measureText(sp.t).width, w = iw + gap + tw, k = Math.min(1, maxW / w);
  g.translate(cx, cy); g.scale(k, k);
  if (glow) { g.shadowColor = glow; g.shadowBlur = 14; }
  const col = glow ? '#ffffff' : sp.c;
  if (sp.icon) { g.save(); g.translate(-w / 2 + iw / 2, 0); ICONS[sp.icon](g, iw / 2, sp.mono ? col : sp.c); g.restore(); }
  g.fillStyle = col; g.textAlign = 'left'; g.fillText(sp.t, -w / 2 + iw + gap, 0);
  g.restore();
}
// 挡板上的赞助商广告：浅色底板，每 11 米一个赞助商，所有赞助商在整圈挡板上轮流出现
const boardAdTex = canvasTex(8192, Math.round(8192 * 1.75 / (11 * SPONSORS.length)), (g, w, h) => {
  const cw = w / SPONSORS.length;
  SPONSORS.forEach((sp, i) => {
    g.fillStyle = i % 2 ? '#f3f5f8' : '#e6eaf0'; g.fillRect(i * cw, 0, cw, h);
    drawSponsor(g, sp, i * cw + cw / 2, h / 2 + 2, cw * 0.82, null);
  });
}, [1, 1]);
SPONSOR_TEX.push(boardAdTex);
const boardAdMat = new THREE.MeshStandardMaterial({ map: boardAdTex, roughness: 0.55, metalness: 0.05, side: THREE.BackSide });
// 广告条要从场内看是正的：把每段墙的点排成"站在场内面朝墙时从左到右"的顺序，这时朝场内的是背面
function adOrder(pts) {
  const [x0, z0] = pts[0], [x1, z1] = pts[pts.length - 1], tx = x1 - x0, tz = z1 - z0;
  const [mx, mz] = pts[Math.floor(pts.length / 2)];
  let nx = -tz, nz = tx; if (nx * (mx + x0) + nz * (mz + z0) < 0) { nx = -nx; nz = -nz; }   // 朝场外的法线
  return tx * -nz + tz * nx < 0 ? pts.slice().reverse() : pts;
}
function wallStrip(pts, y0, y1, mat, keepU, tile) {
  const pos = [], idx = [], uv = [], col = [], inw = [];
  let u = keepU ? keepU : wallU; const uStart = u;
  pts.forEach(([x, z], i) => {
    if (i) u += Math.hypot(x - pts[i - 1][0], z - pts[i - 1][1]);
    pos.push(x, y0, z, x, y1, z);
    if (tile) { const t = (tile.k + (u - uStart) / tile.L * tile.n) / SPONSORS.length; uv.push(t, 0, t, 1); } else uv.push(u / HEX_W, y0 / HEX_H, u / HEX_W, y1 / HEX_H);
    const c = hexColor(z); col.push(c.r, c.g, c.b, c.r, c.g, c.b);
    const [qx, qz] = pts[Math.min(i + 1, pts.length - 1)], [px, pz] = pts[Math.max(i - 1, 0)];
    let nx = -(qz - pz), nz = qx - px; if (nx * -x + nz * -z < 0) { nx = -nx; nz = -nz; }        // 墙段的法线，取指向场内的一侧
    inw.push(nx, 0, nz, nx, 0, nz);
    if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
  });
  if (!keepU) wallU = u;
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setAttribute('inward', new THREE.Float32BufferAttribute(inw, 3));
  g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat || glass); scene.add(m); return m;
}
function polyline(pts3, mat) { const g = new THREE.BufferGeometry().setFromPoints(pts3.map(p => new THREE.Vector3(...p))); scene.add(new THREE.Line(g, mat || edgeMat)); }
{
  const out = roundedOutline(0, 24), n = 24;
  // 整圈墙按逆时针顺序分段（端墙在门口断开），每段都画：挡板、挡板顶的灯带、地面灯带、六边形墙、玻璃
  const segs = [];
  for (let c = 0; c < 4; c++) segs.push({ pts: out.slice(c * (n + 1), (c + 1) * (n + 1)) });
  for (const sx of [-1, 1]) segs.push({ pts: [[sx * W2, -(D2 - CR)], [sx * W2, D2 - CR]] });
  for (const s of [-1, 1]) {
    segs.push({ pts: [[-W2 + CR, s * D2], [-GW2, s * D2]] });
    segs.push({ pts: [[GW2, s * D2], [W2 - CR, s * D2]] });
    segs.push({ pts: [[-GW2, s * D2], [GW2, s * D2]], y0: GH });                 // 门框上方
  }
  let adK = 0;
  for (const sg of segs) {
    const y0 = sg.y0 || 0, u0 = wallU + 0.001;
    if (!sg.y0) {
      wallStrip(sg.pts, 0, BOARD, boardMat, u0);
      // 每段墙放整数个广告位（约 11 米一个），名字不会在墙段接缝处被切开，赞助商顺序接着上一段往下排
      const L = sg.pts.reduce((a, p, i) => i ? a + Math.hypot(p[0] - sg.pts[i - 1][0], p[1] - sg.pts[i - 1][1]) : 0, 0), n = Math.max(1, Math.round(L / 11));
      wallStrip(adOrder(sg.pts).map(([x, z]) => [x * 0.997, z * 0.997]), 0.3, 2.05, boardAdMat, u0, { k: adK, L, n }); adK += n;
      wallStrip(sg.pts.map(([x, z]) => [x * 0.999, z * 0.999]), BOARD - 0.16, BOARD - 0.04, ledMat, u0);
      wallStrip(sg.pts.map(([x, z]) => [x * 0.998, z * 0.998]), 0.02, 0.12, ledMat, u0);
    }
    wallStrip(sg.pts, sg.y0 ? y0 : BOARD, H, hexMat);
    wallStrip(sg.pts, y0, H, glass, u0);
  }
  const top = out.map(([x, z]) => [x, H, z]); top.push(top[0]); polyline(top);
  mergeChildren(scene);                              // 几十段墙按材质合成几个网格
}

// ---------------------------------------------------------------- 球门（门柱 + 球网）
const netTex = canvasTex(256, 256, (g, w, h) => {
  g.clearRect(0, 0, w, h); g.strokeStyle = 'rgba(255,255,255,0.85)'; g.lineWidth = 3;
  const n = 8; for (let i = 0; i <= n; i++) { g.beginPath(); g.moveTo(0, i * h / n); g.lineTo(w, i * h / n + h / n / 2); g.stroke(); g.beginPath(); g.moveTo(i * w / n, 0); g.lineTo(i * w / n + w / n / 2, h); g.stroke(); }
}, [1, 1]);
const goals = [];
for (const s of [-1, 1]) {
  const col = s < 0 ? COL_A : COL_B, grp = new THREE.Group(); scene.add(grp);
  const post = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: col, emissiveIntensity: 0.45, metalness: 0.3, roughness: 0.35 });
  const r = 0.35, z0 = s * D2;
  const cyl = (len) => new THREE.CylinderGeometry(r, r, len, 16);
  for (const x of [-GW2, GW2]) { const m = new THREE.Mesh(cyl(GH), post); m.position.set(x, GH / 2, z0); m.castShadow = true; grp.add(m); }
  const bar = new THREE.Mesh(cyl(A.goal_width), post); bar.rotation.z = Math.PI / 2; bar.position.set(0, GH, z0); bar.castShadow = true; grp.add(bar);
  const netMat = (rx, ry) => { const t = netTex.clone(); t.needsUpdate = true; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rx, ry);
    return new THREE.MeshStandardMaterial({ map: t, transparent: true, side: THREE.DoubleSide, depthWrite: false, color: 0xffffff, emissive: col, emissiveIntensity: 0.15, roughness: 0.8 }); };
  // 球网是细分的网格，每个顶点沿外法线方向有一个位移，用"弹簧 + 相邻顶点耦合"模拟，球撞上去会鼓包并向四周荡开
  const panels = [];
  const panel = (w, h, place, ax, sign) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h, Math.round(w * 2), Math.round(h * 2)), netMat(w / 2, h / 2));
    place(m); m.updateMatrix(); m.geometry.applyMatrix4(m.matrix); m.position.set(0, 0, 0); m.rotation.set(0, 0, 0); grp.add(m);
    const nx = Math.round(w * 2) + 1, ny = Math.round(h * 2) + 1, P = m.geometry.attributes.position, base = Float32Array.from(P.array);
    const lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9];
    for (let i = 0; i < P.count; i++) for (let c = 0; c < 3; c++) { lo[c] = Math.min(lo[c], base[i * 3 + c]); hi[c] = Math.max(hi[c], base[i * 3 + c]); }
    panels.push({ m, nx, ny, base, ax, sign, plane: sign * base[ax], lo, hi, o: new Float32Array(P.count), v: new Float32Array(P.count), live: false });
  };
  panel(A.goal_width, GH, m => m.position.set(0, GH / 2, s * (D2 + GD)), 2, s);                                          // 后网
  panel(A.goal_width, GD, m => { m.rotation.x = Math.PI / 2; m.position.set(0, GH, s * (D2 + GD / 2)); }, 1, 1);        // 顶网
  for (const x of [-GW2, GW2]) panel(GD, GH, m => { m.rotation.y = Math.PI / 2; m.position.set(x, GH / 2, s * (D2 + GD / 2)); }, 0, Math.sign(x));  // 侧网
  // 门内灯带
  const glow = new THREE.PointLight(col, 0, 40); glow.position.set(0, GH * 0.6, s * (D2 + GD * 0.5)); scene.add(glow);
  goals.push({ grp, glow, panels, nets: grp.children.filter(c => c.material.map) });
}
const netPanels = goals.flatMap(g => g.panels);
// 球贴着网时网被压出去的深度：用球心到网面的距离判断，影响范围是以接触点为中心的高斯分布
function netPress(pn, bp, i) {
  const R = M.ball_radius, b = pn.base, ax = pn.ax, a1 = (ax + 1) % 3, a2 = (ax + 2) % 3;
  const gap = pn.sign * bp[ax] + R - pn.plane;                    // >0 表示球面越过了网面
  if (gap < -0.7 || bp[a1] < pn.lo[a1] - 0.5 || bp[a1] > pn.hi[a1] + 0.5 || bp[a2] < pn.lo[a2] - 0.5 || bp[a2] > pn.hi[a2] + 0.5) return 0;
  const d2 = (b[i * 3 + a1] - bp[a1]) ** 2 + (b[i * 3 + a2] - bp[a2]) ** 2;
  return Math.min(1, (gap + 0.7) / 0.7) * Math.exp(-d2 / 5.5);
}
function netImpulse(p, strength) {                                // 球撞网：给接触点附近的顶点一个向外的速度
  for (const pn of netPanels) {
    const ax = pn.ax, a1 = (ax + 1) % 3, a2 = (ax + 2) % 3;
    if (Math.abs(pn.sign * p[ax] - pn.plane) > 1.2) continue;
    if (p[a1] < pn.lo[a1] - 1 || p[a1] > pn.hi[a1] + 1 || p[a2] < pn.lo[a2] - 1 || p[a2] > pn.hi[a2] + 1) continue;
    for (let i = 0; i < pn.o.length; i++) {
      const d2 = (pn.base[i * 3 + a1] - p[a1]) ** 2 + (pn.base[i * 3 + a2] - p[a2]) ** 2;
      pn.v[i] += strength * 26 * Math.exp(-d2 / 7);
    }
    pn.live = true;
  }
}
function stepNets(dt, bp) {
  const push = [0, 0, 0]; let pm = 0;                               // 球所在位置被网顶出去多少（让球也跟着陷进网里）
  for (const pn of netPanels) {
    const { nx, ny, o, v } = pn, near = Math.abs(pn.sign * bp[pn.ax] + M.ball_radius - pn.plane) < 1.5;
    if (!pn.live && !near) continue;
    // 每帧只算一次"球压网"的目标位移，子步里直接用
    const T = pn.T || (pn.T = new Float32Array(o.length));
    let best = 0, bi = -1;
    if (near) for (let i = 0; i < o.length; i++) { const w = netPress(pn, bp, i); T[i] = 1.4 * w; if (w > best) { best = w; bi = i; } }
    else T.fill(0);
    const steps = Math.min(8, Math.max(1, Math.ceil(dt / (1 / 240)))), h = dt / steps;
    let energy = 0;
    for (let st = 0; st < steps; st++) for (let y = 1; y < ny - 1; y++) for (let x = 1; x < nx - 1; x++) {
      const i = y * nx + x, lap = o[i - 1] + o[i + 1] + o[i - nx] + o[i + nx] - 4 * o[i];
      v[i] += (130 * (T[i] - o[i]) + 140 * lap - 5.5 * v[i]) * h;
      o[i] += v[i] * h;
      if (st === steps - 1) energy += Math.abs(o[i]) + Math.abs(v[i]) * 0.1;
    }
    if (dt === 0 && !near) continue;
    const P = pn.m.geometry.attributes.position, arr = P.array, b = pn.base, ax = pn.ax;
    for (let i = 0; i < o.length; i++) arr[i * 3 + ax] = b[i * 3 + ax] + pn.sign * o[i];
    if (bi >= 0) { const d = o[bi] * Math.min(1, best * 1.3); if (d > pm) { pm = d; push.fill(0); push[ax] = pn.sign * d; } }
    P.needsUpdate = true; pn.m.geometry.computeVertexNormals();
    pn.live = energy > 0.02 || near;
    if (!pn.live) { o.fill(0); v.fill(0); arr.set(b); pn.m.geometry.computeVertexNormals(); }
  }
  return push;
}
function resetNets() { for (const pn of netPanels) { pn.o.fill(0); pn.v.fill(0); pn.m.geometry.attributes.position.array.set(pn.base); pn.m.geometry.attributes.position.needsUpdate = true; pn.live = false; } }

// ---------------------------------------------------------------- 看台和灯塔（氛围）
let adTex = null;
{
  const standMat = new THREE.MeshStandardMaterial({ color: 0x1b2433, roughness: 0.9 });
  const seatCols = [0x22324a, 0x2a3c58, 0x1e2a3f];
  const BZ = GD + 8;  // 球门后方的看台额外往后退：球门深 GD，再留 8 米的空地（广告牌）
  for (let tier = 0; tier < 5; tier++) {
    const pts = roundedOutline(-6 - tier * 3.2, 10, BZ);
    const shape = new THREE.Shape(); pts.forEach(([x, z], i) => i ? shape.lineTo(x, -z) : shape.moveTo(x, -z));
    const hole = new THREE.Path(); roundedOutline(-3 - tier * 3.2, 10, BZ).slice().reverse().forEach(([x, z], i) => i ? hole.lineTo(x, -z) : hole.moveTo(x, -z));
    shape.holes.push(hole);
    const g = new THREE.ExtrudeGeometry(shape, { depth: 2.2 + tier * 2.4, bevelEnabled: false });
    const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: seatCols[tier % 3], roughness: 0.85 }));
    m.rotation.x = -Math.PI / 2; m.receiveShadow = true; scene.add(m);
  }
  // 观众（随机彩色小点，用实例化）
  const crowd = new THREE.InstancedMesh(new THREE.BoxGeometry(0.7, 0.9, 0.7), new THREE.MeshStandardMaterial({ roughness: 0.8 }), 2600);
  const col = new THREE.Color(), mtx = new THREE.Matrix4(); let k = 0;
  for (let tier = 0; tier < 5 && k < 2600; tier++) {
    const pts = roundedOutline(-4.6 - tier * 3.2, 40, BZ);
    for (let i = 0; i < pts.length - 1 && k < 2600; i++) {
      const [x0, z0] = pts[i], [x1, z1] = pts[i + 1], n = Math.max(1, Math.floor(Math.hypot(x1 - x0, z1 - z0) / 1.1));
      for (let j = 0; j < n && k < 2600; j++) {
        if (Math.random() < 0.18) continue;
        const t = j / n; mtx.makeTranslation(x0 + (x1 - x0) * t, 2.2 + tier * 2.4 + 0.45, z0 + (z1 - z0) * t);
        crowd.setMatrixAt(k, mtx);
        const side = (z0 < 0) ? 0 : 1; const r = Math.random();
        col.setHex(r < 0.35 ? (side ? 0xef4444 : 0x22c55e) : [0xe5e7eb, 0xfacc15, 0x94a3b8, 0x64748b, 0x0ea5e9][Math.floor(Math.random() * 5)]);
        crowd.setColorAt(k, col); k++;
      }
    }
  }
  crowd.count = k; scene.add(crowd);
  // 每层看台前沿一圈青色灯带
  for (let tier = 0; tier < 5; tier++) {
    const pts = roundedOutline(-3.05 - tier * 3.2, 40, BZ).map(([x, z]) => [x, 2.2 + tier * 2.4 + 0.03, z]); pts.push(pts[0]);
    polyline(pts, new THREE.LineBasicMaterial({ color: tier ? 0x2b6f8f : 0x5ee7ff, transparent: true, opacity: tier ? 0.6 : 0.9 }));
  }
  // 球门后方空地上的 LED 广告牌，字幕缓慢滚动
  // LED 屏：AI ARENA 和各家赞助商轮流滚动，赞助商名字用各自的品牌色发光
  adTex = canvasTex(8192, Math.round(8192 * 1.5 / (A.width - 4)), (g, w, h) => {   // 贴图比例和屏幕一致，字不会被压扁
    const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#071a2c'); gr.addColorStop(1, '#03101d'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
    const n = SPONSORS.length + 1, cw = w / n;
    for (let i = 0; i < n; i++) {
      if (i === 0) { g.save(); g.font = 'italic 900 96px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = '#e6fbff'; g.shadowColor = '#5ee7ff'; g.shadowBlur = 14; g.fillText('AI ARENA', cw / 2, h / 2 + 2); g.restore(); }
      else { const sp = SPONSORS[i - 1]; drawSponsor(g, { ...sp, f: sp.f.replace(/\d+px/, m => Math.round(parseInt(m) * 1.0) + 'px') }, i * cw + cw / 2, h / 2 + 2, cw * 0.82, ['#000000', '#0d0d0d', '#191919', '#111111'].includes(sp.c) ? '#9adfff' : sp.c); }
      g.fillStyle = 'rgba(94,231,255,0.35)'; g.fillRect((i + 1) * cw - 2, h * 0.2, 3, h * 0.6);
    }
  }, [1, 1]);
  SPONSOR_TEX.push(adTex);
  for (const s of [-1, 1]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(A.width - 4, 1.5), new THREE.MeshBasicMaterial({ map: adTex, toneMapped: false }));
    m.position.set(0, 0.75, s * (D2 + GD + 5)); m.rotation.y = s > 0 ? Math.PI : 0; scene.add(m);
    const back = new THREE.Mesh(new THREE.BoxGeometry(A.width - 3.6, 1.8, 0.3), new THREE.MeshStandardMaterial({ color: 0x1e2633, roughness: 0.6, metalness: 0.4 }));
    back.position.set(0, 0.85, s * (D2 + GD + 5.2)); scene.add(back);
  }
  // 四角灯塔
  const poleMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.6, roughness: 0.4 });
  const glowTex = canvasTex(64, 64, (g, w, h) => { const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(255,255,240,1)'); gr.addColorStop(0.25, 'rgba(255,250,220,0.6)'); gr.addColorStop(1, 'rgba(255,250,220,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const x = sx * (W2 + 26), z = sz * (D2 + BZ + 26);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.9, 46, 8), poleMat); pole.position.set(x, 23, z); scene.add(pole);
    const head = new THREE.Mesh(new THREE.BoxGeometry(7, 4, 1), new THREE.MeshStandardMaterial({ color: 0xfffbe6, emissive: 0xfff4c2, emissiveIntensity: 1.2 }));
    head.position.set(x, 47, z); head.lookAt(0, 0, 0); scene.add(head);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    sp.scale.set(26, 26, 1); sp.position.set(x * 0.98, 47, z * 0.98); scene.add(sp);
  }
}

// ---------------------------------------------------------------- 球
// 比赛专用球 "AI ARENA"：参考近几届世界杯用球（大块热粘合面板 + 醒目的几何图形），
// 六块面板（立方体投影到球面），珍珠白底色，每块面板一角是带金边的深蓝三角块，另一角是电光蓝细三角，
// 三角旁边有一道深蓝细条；两块面板上印 AI ARENA 字标。所有图形边缘做抗锯齿，不用渐变。
function makeBallTextures(w, h) {
  const WHITE = [247, 248, 250], NAVY = [14, 27, 66], BLUE = [37, 99, 235], GOLD = [242, 178, 26], SEAM = [150, 158, 172];
  const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  const mix = (c1, c2, t) => t <= 0 ? c1 : [c1[0] + (c2[0] - c1[0]) * t, c1[1] + (c2[1] - c1[1]) * t, c1[2] + (c2[2] - c1[2]) * t];
  const AA = 0.006;  // 抗锯齿宽度（面板坐标）
  const inside = (d) => 1 - sm(-AA, AA, d);  // d < 0 表示在图形内
  // 六个面板：外法向 n、面板内"右"e1 和"上"e2（从球外看文字不会镜像），motif 旋转 k×90°
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const faces = [[1, 0, 0], [-1, 0, 0], [0, 0, 1], [0, 0, -1], [0, 1, 0], [0, -1, 0]].map((n, i) => {
    const e2 = Math.abs(n[1]) > 0.5 ? [0, 0, 1] : [0, 1, 0];
    return { n, e1: cross(e2, n), e2, k: [0, 0, 1, 3, 2, 1][i], logo: i < 2 };
  });
  // 字标
  const logo = document.createElement('canvas'); logo.width = 1024; logo.height = 320;
  { const g = logo.getContext('2d'); g.fillStyle = '#000'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.font = 'italic 900 190px system-ui, "Arial Black", sans-serif'; g.fillText('AI ARENA', 512, 135);
    g.font = '700 52px system-ui, sans-serif'; g.fillText('OFFICIAL  MATCH  BALL', 512, 272); }
  const logoPx = logo.getContext('2d').getImageData(0, 0, 1024, 320).data;
  // 字标按球面角度铺开（不是按面板平面坐标），这样左右两端的字母不会被投影压窄
  const LW = 0.84, LH = LW * 320 / 1024;  // 字标的张角（弧度）
  const col = document.createElement('canvas'); col.width = w; col.height = h;
  const bump = document.createElement('canvas'); bump.width = w; bump.height = h;
  const ci = col.getContext('2d').createImageData(w, h), bi = bump.getContext('2d').createImageData(w, h);
  for (let py = 0; py < h; py++) {
    const th = (py + 0.5) / h * Math.PI, st = Math.sin(th), ct = Math.cos(th);
    for (let px = 0; px < w; px++) {
      const ph = (px + 0.5) / w * 2 * Math.PI;
      const d = [-Math.cos(ph) * st, ct, Math.sin(ph) * st];   // three.js SphereGeometry 的 UV 约定
      let f = faces[0], best = -2;
      for (const F of faces) { const v = d[0] * F.n[0] + d[1] * F.n[1] + d[2] * F.n[2]; if (v > best) { best = v; f = F; } }
      const u = (d[0] * f.e1[0] + d[1] * f.e1[1] + d[2] * f.e1[2]) / best, v = (d[0] * f.e2[0] + d[1] * f.e2[1] + d[2] * f.e2[2]) / best;
      const edge = 1 - Math.max(Math.abs(u), Math.abs(v));   // 到面板接缝的距离（0 = 接缝）
      // motif 坐标：旋转 k×90°
      let p = u, q = v;
      for (let r = 0; r < f.k; r++) { const t = p; p = -q; q = t; }
      const s = p + q;
      let c = WHITE;
      c = mix(c, GOLD, inside(0.865 - s) * inside(s - 0.925));      // 金色细边
      c = mix(c, NAVY, inside(0.965 - s));                          // 深蓝三角块
      c = mix(c, BLUE, inside(s + 1.3));                            // 对角的电光蓝三角
      c = mix(c, NAVY, inside(s + 1.17) * inside(-1.215 - s));      // 旁边的深蓝细条
      if (f.logo) {
        const lu = Math.atan(u) / LW + 0.5, lv = 0.5 - (Math.atan(v) + 0.04) / LH;
        if (lu >= 0 && lu < 1 && lv >= 0 && lv < 1) {
          const a = logoPx[((Math.floor(lv * 320) * 1024 + Math.floor(lu * 1024)) << 2) + 3] / 255;
          c = mix(c, NAVY, a);
        }
      }
      c = mix(SEAM, c, sm(0.004, 0.012, edge));     // 面板接缝
      const k4 = (py * w + px) << 2;
      ci.data[k4] = c[0]; ci.data[k4 + 1] = c[1]; ci.data[k4 + 2] = c[2]; ci.data[k4 + 3] = 255;
      const bv = 255 * sm(0.0, 0.016, edge); bi.data[k4] = bi.data[k4 + 1] = bi.data[k4 + 2] = bv; bi.data[k4 + 3] = 255;
    }
  }
  col.getContext('2d').putImageData(ci, 0, 0); bump.getContext('2d').putImageData(bi, 0, 0);
  const map = new THREE.CanvasTexture(fitCanvas(col)); map.encoding = THREE.sRGBEncoding; map.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const bumpMap = new THREE.CanvasTexture(fitCanvas(bump));
  return { map, bumpMap };
}
const ballTx = makeBallTextures(2048, 1024);
const ball = new THREE.Mesh(new THREE.SphereGeometry(M.ball_radius, 64, 48),
  new THREE.MeshPhysicalMaterial({ map: ballTx.map, bumpMap: ballTx.bumpMap, bumpScale: 0.012, roughness: 0.38, metalness: 0.0, clearcoat: 0.6, clearcoatRoughness: 0.25 }));
ball.castShadow = true; scene.add(ball);
// 球的拖尾
const TRAIL = 36;
const trailGeo = new THREE.BufferGeometry(); trailGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(TRAIL * 3), 3));
const trailCol = new Float32Array(TRAIL * 3); for (let i = 0; i < TRAIL; i++) { const a = 1 - i / TRAIL; trailCol.set([a, a, a * 0.8], i * 3); }
trailGeo.setAttribute('color', new THREE.Float32BufferAttribute(trailCol, 3));
const trail = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
scene.add(trail);
// 球的落点指示
const marker = new THREE.Mesh(new THREE.RingGeometry(1.2, 1.6, 40), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.35, depthWrite: false }));
marker.rotation.x = -Math.PI / 2; scene.add(marker);

// ---------------------------------------------------------------- 机器人
function labelSprite(text, color) {
  const t = canvasTex(128, 128, (g, w, h) => {
    g.fillStyle = color; g.beginPath(); g.arc(64, 64, 52, 0, Math.PI * 2); g.fill();
    g.lineWidth = 8; g.strokeStyle = 'rgba(255,255,255,0.9)'; g.stroke();
    g.fillStyle = '#fff'; g.font = 'bold 66px system-ui'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, 64, 70);
  });
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false, transparent: true })); s.scale.set(1.3, 1.3, 1); s.renderOrder = 10; return s;
}
const V2 = pts => pts.map(p => new THREE.Vector2(p[0], p[1]));
const softTex = canvasTex(64, 64, (g) => { const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.35, 'rgba(255,255,255,0.5)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 64); });
// ---------------------------------------------------------------- 场边全息投影
// 按 mr.wang 给的设计图（assets/holo_ref.png），两端球门两侧各 4 台投影仪，投出各家 AI 的卡通形象。
// 角色图是从设计图里抠出来的（assets/holo_atlas.webp，4×2 格），用叠加混合画在一块始终正对镜头的竖直面片上，
// 着色器里加扫描线、闪烁、上移的亮带和偶尔的横向错位，看起来像全息影像；8 个面片合成一个网格，一次绘制。
const HOLO = [
  { name: 'CLAUDE', c: '#ff9a4d' }, { name: 'DEEPSEEK', c: '#5b8cff' }, { name: 'GEMINI', c: '#a77bff' }, { name: 'CHATGPT', c: '#3ee8d0' },
  { name: 'QWEN', c: '#9b7bff' }, { name: 'DOUBAO', c: '#ff6b9a' }, { name: 'GLM', c: '#4fb4ff' }, { name: 'KIMI', c: '#6f8bff' },
];
const holoU = { map: { value: null }, uTime: { value: 0 } };
let holoT = 0;
{
  const tex = new THREE.Texture(); const img = new Image();
  img.onload = () => { tex.image = img; tex.needsUpdate = true; holoMesh.visible = true; };
  img.src = '__HOLO__';
  tex.minFilter = THREE.LinearMipmapLinearFilter; tex.anisotropy = 4; holoU.map.value = tex;
  const HS = 10.5, Y0 = 2.7;                          // HS：每格 512 像素对应的边长（米）；Y0：投影仪立柱高度，高出挡板，从场内也能看到整个角色
  const spots = [];
  for (const sz of [-1, 1]) for (const x of [-28, -20.5, 20.5, 28]) spots.push([-sz * x, sz * (D2 + 6.5)]);   // 站在场内看过去从左到右和设计图同序
  // 绿方（z<0）一端放前 4 个，红方一端放后 4 个
  const order = [0, 1, 2, 3, 4, 5, 6, 7];
  const pos = [], corner = [], uv = [], seed = [], idx = [];
  order.forEach((k, i) => {
    const [x, z] = spots[i], cu = (k % 4) / 4, cv = 1 - (Math.floor(k / 4) + 1) / 2, b = i * 4;
    for (const [qx, qy, u, v] of [[-0.5, 0, 0, 0], [0.5, 0, 1, 0], [0.5, 1, 1, 1], [-0.5, 1, 0, 1]]) {
      pos.push(x, Y0 + 0.75, z); corner.push(qx * HS, qy * HS); uv.push(cu + u / 4, cv + v / 2); seed.push(i * 1.7 + 0.3);
    }
    idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('corner', new THREE.Float32BufferAttribute(corner, 2));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute('seed', new THREE.Float32BufferAttribute(seed, 1)); g.setIndex(idx);
  const mat = new THREE.ShaderMaterial({
    uniforms: holoU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `
      attribute vec2 corner; attribute float seed; uniform float uTime;
      varying vec2 vUv; varying float vH; varying float vSeed;
      void main() {
        vec3 f = cameraPosition - position; f.y = 0.0; f = normalize(f + vec3(1e-4, 0.0, 0.0));
        vec3 right = vec3(f.z, 0.0, -f.x);
        float bob = sin(uTime * 1.1 + seed) * 0.12 * step(0.01, corner.y);
        vec3 wp = position + right * corner.x + vec3(0.0, corner.y + bob, 0.0);
        vUv = uv; vH = corner.y / ${HS.toFixed(2)}; vSeed = seed;
        gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
      }`,
    fragmentShader: `
      uniform sampler2D map; uniform float uTime; varying vec2 vUv; varying float vH; varying float vSeed;
      float h1(float n) { return fract(sin(n) * 43758.5453); }
      void main() {
        float band = floor(vH * 48.0), tick = floor(uTime * 9.0);
        float glitch = step(0.975, h1(band * 12.9898 + tick * 78.233 + vSeed * 3.1)) * step(0.55, h1(tick + vSeed));
        vec2 uv = vUv + vec2(glitch * 0.006 * (h1(band + tick) - 0.5) * 4.0, 0.0);
        vec3 c = texture2D(map, uv).rgb;
        float scan = 0.84 + 0.16 * sin(vH * 520.0 - uTime * 7.0);
        float flick = 0.93 + 0.07 * sin(uTime * 19.0 + vSeed * 5.0) * sin(uTime * 6.3 + vSeed);
        float sweep = exp(-pow((fract(vH * 0.8 - uTime * 0.22 + vSeed * 0.17) - 0.5) * 9.0, 2.0)) * 0.45;
        gl_FragColor = vec4(c * (scan * flick * 1.45 + sweep + glitch * 0.6), 1.0);
      }`,
  });
  var holoMesh = new THREE.Mesh(g, mat); holoMesh.frustumCulled = false; holoMesh.visible = false; holoMesh.renderOrder = 5; scene.add(holoMesh);

  // 投影仪底座：深色金属圆台 + 侧面一圈名字灯带 + 顶面发光圆环和光盘 + 向上散开的光柱，按材质合并成几次绘制
  const nameTex = canvasTex(1024, 512, (c, w, h) => {
    c.fillStyle = '#060b16'; c.fillRect(0, 0, w, h);
    HOLO.forEach((o, i) => {
      const y = (i + 0.5) * h / 8;
      c.fillStyle = 'rgba(94,231,255,0.55)'; c.fillRect(0, i * h / 8 + 3, w, 2); c.fillRect(0, (i + 1) * h / 8 - 5, w, 2);
      c.font = '700 38px ' + SANS; c.textAlign = 'center'; c.textBaseline = 'middle'; if ('letterSpacing' in c) c.letterSpacing = '8px';
      c.shadowColor = o.c; c.shadowBlur = 12; c.fillStyle = '#eafcff';
      for (const cx of [w * 0.25, w * 0.75]) c.fillText(o.name, cx, y + 1);
    });
  });
  const baseGrp = new THREE.Group(); scene.add(baseGrp);
  const metal = new THREE.MeshStandardMaterial({ color: 0x141b27, metalness: 0.7, roughness: 0.35 });
  const nameMat = new THREE.MeshBasicMaterial({ map: nameTex, toneMapped: false });
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x7ff3ff, toneMapped: false });
  const discMat = new THREE.MeshBasicMaterial({ map: softTex, color: 0x48c8ff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
  const beamMat = new THREE.ShaderMaterial({
    uniforms: holoU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `uniform float uTime; varying vec2 vUv;
      void main() {
        float a = pow(1.0 - vUv.y, 2.2) * 0.32;
        float streak = 0.6 + 0.4 * sin(vUv.x * 120.0 + sin(vUv.x * 31.0) * 3.0);
        float ripple = 0.75 + 0.25 * sin(vUv.y * 30.0 - uTime * 5.0);
        gl_FragColor = vec4(vec3(0.25, 0.75, 1.0) * a * streak * ripple, 1.0);
      }`,
  });
  HOLO.forEach((o, i) => {
    const [x, z] = spots[i];
    const add = (geo, m, y) => { const mesh = new THREE.Mesh(geo, m); mesh.position.set(x, y, z); baseGrp.add(mesh); return mesh; };
    add(new THREE.CylinderGeometry(1.6, 2.1, 0.3, 40), metal, 0.15);                  // 底盘
    add(new THREE.CylinderGeometry(0.75, 0.95, Y0, 24), metal, Y0 / 2);              // 立柱
    add(new THREE.CylinderGeometry(1.75, 1.2, 0.3, 40), metal, Y0 + 0.03);           // 投影仪下沿
    const band = new THREE.CylinderGeometry(1.75, 1.75, 0.5, 48, 1, true), bu = band.attributes.uv;
    for (let k = 0; k < bu.count; k++) bu.setXY(k, bu.getX(k), (7 - i + bu.getY(k)) / 8);   // 每台取名字贴图里自己那一行
    add(band, nameMat, Y0 + 0.43);
    add(new THREE.CylinderGeometry(1.85, 1.85, 0.08, 40), metal, Y0 + 0.72);
    const ring = add(new THREE.TorusGeometry(1.5, 0.06, 8, 48), ringMat, Y0 + 0.78); ring.rotation.x = Math.PI / 2;
    const disc = add(new THREE.PlaneGeometry(3.6, 3.6), discMat, Y0 + 0.8); disc.rotation.x = -Math.PI / 2;
    add(new THREE.CylinderGeometry(3.4, 1.4, 4.8, 40, 1, true), beamMat, Y0 + 0.8 + 2.4);
  });
  baseGrp.traverse(o => { if (o.isMesh && o.material === metal) o.castShadow = o.receiveShadow = true; });
  mergeChildren(baseGrp);
}
// ---------------------------------------------------------------- 看台顶上的鼓风充气人偶
// 按 mr.wang 给的概念图（assets/airdancer_ref.png）：8 家 AI 的吉祥物做成鼓风机吹起来的布筒人偶，立在两条长边最高一层看台上。
// 全是立体模型：身体和两条手臂是布筒，头部按各家形象用球、柱、圆环、挤出的四角星和 Z 字拼出来，表情是贴在脸上的贴花。
// 动画在顶点着色器里算：身体沿一条被风吹得左右前后甩的"脊柱"弯折，布面有往上走的鼓包；手臂按自己的节奏乱挥；
// 隔一阵泄气塌下去、往前弯折、手臂耷拉，再被吹起来。头部和贴花跟着脊柱顶端的姿态走。所有人偶合成两个网格（布料 + 贴花）。
const airU = { uTime: { value: 0 }, uCamPos: { value: camera.position } };
{
  const AL = 5.6, RB = 0.55, ARM = 2.0;              // 身体长、身体半径、手臂长（米）
  const C = h => new THREE.Color(h).convertSRGBToLinear();
  const B = { pos: [], nrm: [], col: [], base: [], meta: [], idx: [] }, D = { pos: [], nrm: [], uv: [], base: [], meta: [], idx: [] };
  let cur = null;                                    // 当前人偶：{ base, facing, seed }
  const meta = (kind, extra) => [cur.facing, cur.seed, kind, extra];
  const pushV = (T, p, n, m) => { T.pos.push(p[0], p[1], p[2]); T.nrm.push(n[0], n[1], n[2]); T.base.push(...cur.base); T.meta.push(...m); };
  // 身体布筒：position = (r·cosθ, v·AL, r·sinθ)，θ=π/2 朝场内
  function body(colFn) {
    const NI = 28, NJ = 34, o = B.pos.length / 3;
    for (let j = 0; j <= NJ; j++) for (let i = 0; i <= NI; i++) {
      const v = j / NJ, th = i / NI * Math.PI * 2, r = RB * (0.9 + 0.1 * Math.sin(Math.min(1, v * 1.4) * Math.PI / 2)) * (1 + 0.05 * Math.sin(v * Math.PI));
      pushV(B, [r * Math.cos(th), v * AL, r * Math.sin(th)], [Math.cos(th), 0, Math.sin(th)], meta(0, 0));
      const c = C(colFn(v, th)); B.col.push(c.r, c.g, c.b);
    }
    for (let j = 0; j < NJ; j++) for (let i = 0; i < NI; i++) { const a = o + j * (NI + 1) + i, b = a + NI + 1; B.idx.push(a, b, a + 1, a + 1, b, b + 1); }
  }
  // 手臂布筒：position = (u, r·cosθ, r·sinθ)，末端开口带袖口
  function arms(colFn) {
    for (const side of [-1, 1]) {
      const NI = 14, NJ = 18, o = B.pos.length / 3;
      for (let j = 0; j <= NJ; j++) for (let i = 0; i <= NI; i++) {
        const u = j / NJ, th = i / NI * Math.PI * 2, r = (u > 0.86 ? 0.25 : 0.215) * (1 + 0.06 * Math.sin(u * 9));
        pushV(B, [u, r * Math.cos(th), r * Math.sin(th)], [0, Math.cos(th), Math.sin(th)], meta(1, side));
        const c = C(colFn(u)); B.col.push(c.r, c.g, c.b);
      }
      for (let j = 0; j < NJ; j++) for (let i = 0; i < NI; i++) { const a = o + j * (NI + 1) + i, b = a + NI + 1; B.idx.push(a, b, a + 1, a + 1, b, b + 1); }
    }
  }
  // 刚性部件（头部等）：局部坐标 x 向右、y 沿脊柱向上、z 朝场内，原点在脊柱上参数 at 处
  const mtx = new THREE.Matrix4(), nm = new THREE.Matrix3(), tv = new THREE.Vector3(), tn = new THREE.Vector3();
  function part(geo, { p = [0, 0, 0], r = [0, 0, 0], s = [1, 1, 1], col = 0xffffff, at = 1 } = {}) {
    mtx.compose(new THREE.Vector3(...p), new THREE.Quaternion().setFromEuler(new THREE.Euler(...r)), new THREE.Vector3(...s)); nm.getNormalMatrix(mtx);
    const P = geo.attributes.position, N = geo.attributes.normal, o = B.pos.length / 3;
    for (let i = 0; i < P.count; i++) {
      tv.fromBufferAttribute(P, i).applyMatrix4(mtx); tn.fromBufferAttribute(N, i).applyMatrix3(nm).normalize();
      pushV(B, [tv.x, tv.y, tv.z], [tn.x, tn.y, tn.z], meta(2, at));
      const c = C(typeof col === 'function' ? col(tv) : col); B.col.push(c.r, c.g, c.b);
    }
    if (geo.index) for (const k of geo.index.array) B.idx.push(o + k); else for (let i = 0; i < P.count; i++) B.idx.push(o + i);
    geo.dispose();
  }
  const sph = (rad, o) => part(new THREE.SphereGeometry(rad, 24, 16), o);
  function rod(a, b, rad, o = {}, seg = 12) {         // 两点之间的圆柱（两端加球帽）
    const A = new THREE.Vector3(...a), Bv = new THREE.Vector3(...b), d = Bv.clone().sub(A), L = d.length();
    const g = new THREE.CylinderGeometry(rad, rad, L, seg, 1, true);
    g.applyMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize())));
    g.translate(...A.clone().add(Bv).multiplyScalar(0.5).toArray());
    part(g, o);
    for (const e of [a, b]) part(new THREE.SphereGeometry(rad, seg, 8), { ...o, p: [e[0] + (o.p ? o.p[0] : 0), e[1] + (o.p ? o.p[1] : 0), e[2] + (o.p ? o.p[2] : 0)] });
  }
  function ext(shape, depth, bevel, o) {
    const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel * 0.8, bevelSegments: 4, curveSegments: 14 });
    g.translate(0, 0, -depth / 2); g.computeVertexNormals(); part(g, o);
  }
  // 表情贴花：网格投到一组椭球（取最外层）或平面上，略浮起一点
  function decal(cell, cx, cy, size, surf, at = 1) {
    const n = 10, o = D.pos.length / 3, cu = (cell % 4) / 4, cv = 1 - (Math.floor(cell / 4) + 1) / 4;
    for (let j = 0; j <= n; j++) for (let i = 0; i <= n; i++) {
      const x = cx + (i / n - 0.5) * size, y = cy + (j / n - 0.5) * size;
      let z = -1e9, nz = [0, 0, 1];
      for (const e of surf) {
        if (e.flat !== undefined) { if (e.flat > z) { z = e.flat; nz = [0, 0, 1]; } continue; }
        const dx = (x - e.c[0]) / e.r[0], dy = (y - e.c[1]) / e.r[1], q = 1 - dx * dx - dy * dy;
        const zz = e.c[2] + e.r[2] * Math.sqrt(Math.max(0, q));
        if (zz > z) { z = zz; const g = [dx / e.r[0], dy / e.r[1], Math.sqrt(Math.max(0, q)) / e.r[2]], l = Math.hypot(...g); nz = g.map(t => t / l); }
      }
      pushV(D, [x, y, z + 0.014], nz, meta(2, at)); D.uv.push(cu + i / n / 4, cv + j / n / 4);
    }
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const a = o + j * (n + 1) + i, b = a + n + 1; D.idx.push(a, a + 1, b, a + 1, b + 1, b); }
  }
  const sw = (th, c, w) => Math.abs(Math.atan2(Math.sin(th - c), Math.cos(th - c))) < w;   // θ 是否在 c 附近 w 以内
  const F = Math.PI / 2;                                                                  // 正前方
  const cuff = (base, band) => u => u > 0.88 ? band : base;
  // 8 个吉祥物
  const MASCOTS = [
    () => {                                               // Claude：橙色，头是一圈光芒
      body(() => 0xf06a2e); arms(u => (u > 0.76 && u < 0.8) || (u > 0.84 && u < 0.88) ? 0xffffff : 0xf06a2e);
      sph(0.56, { p: [0, 0.52, 0], col: 0xf06a2e });
      for (let k = 0; k < 10; k++) { const a = k * Math.PI / 5 + Math.PI / 10; if (Math.abs(a - Math.PI * 1.5) < 0.5) continue;
        const c = Math.cos(a), s = Math.sin(a); rod([c * 0.5, 0.52 + s * 0.5, 0], [c * 1.05, 0.52 + s * 1.05, 0], 0.15, { col: 0xf06a2e }); }
      decal(0, 0, 0.5, 0.9, [{ c: [0, 0.52, 0], r: [0.56, 0.56, 0.56] }]);
    },
    () => {                                               // DeepSeek：蓝鲸，白肚皮，头顶鲸尾
      body((v, th) => sw(th, F, 0.75) && v > 0.04 ? 0xf4f6fb : 0x2459d8); arms(cuff(0x2459d8, 0x1a3f9e));
      sph(0.6, { p: [0, 0.22, 0], s: [1, 1.25, 1], col: p => p.z > 0.28 && p.y < 0.22 ? 0xf4f6fb : 0x2459d8 });
      rod([0, 0.85, -0.05], [0, 1.12, -0.12], 0.12, { col: 0x2459d8 });
      for (const sx of [-1, 1]) sph(0.3, { p: [sx * 0.3, 1.2, -0.12], s: [1.45, 0.42, 0.7], r: [0, 0, sx * 0.45], col: 0x2459d8 });
      sph(0.3, { p: [0.62, 0.0, 0.12], s: [1.0, 0.38, 0.6], r: [0, 0, -0.6], col: 0x5f9dff, at: 0.42 });
      decal(1, 0, 0.55, 0.85, [{ c: [0, 0.22, 0], r: [0.6, 0.75, 0.6] }]);
    },
    () => {                                               // Gemini：蓝紫渐变，头是鼓鼓的四角星
      const grad = v => '#' + new THREE.Color(0xb35be6).lerp(new THREE.Color(0x4a6cf0), v).getHexString();
      body(v => +('0x' + grad(v).slice(1))); arms(cuff(0x8a5ce8, 0x5a35b8));
      const st = new THREE.Shape(); st.moveTo(0, 1); st.quadraticCurveTo(0.16, 0.16, 0.92, 0); st.quadraticCurveTo(0.16, -0.16, 0, -1); st.quadraticCurveTo(-0.16, -0.16, -0.92, 0); st.quadraticCurveTo(-0.16, 0.16, 0, 1);
      ext(st, 0.22, 0.16, { p: [0, 0.78, 0], r: [0, 0, 0.22], s: [0.82, 0.82, 1], col: p => '#' + new THREE.Color(0x4a7cf5).lerp(new THREE.Color(0xd06ad8), Math.min(1, Math.max(0, (p.x + p.y - 0.5) * 0.6 + 0.5))).getHexString() });
      decal(2, 0, 0.72, 0.62, [{ flat: 0.11 + 0.16 }]);
    },
    () => {                                               // ChatGPT：米白身体、绿色下摆和兜帽，胸口 OpenAI 标志
      body(v => v < 0.2 ? 0x5ec9a0 : 0xefe8da); arms(cuff(0x5ec9a0, 0x3fa982));
      sph(0.6, { p: [0, 0.55, 0], col: 0x5ec9a0 });
      sph(1, { p: [0, 0.5, 0.36], s: [0.46, 0.42, 0.3], col: 0xf4ede0 });
      rod([0, 1.1, 0], [0, 1.2, 0], 0.06, { col: 0x5ec9a0 }); sph(0.14, { p: [0, 1.3, 0], col: 0x5ec9a0 });
      decal(3, 0, 0.5, 0.78, [{ c: [0, 0.5, 0.36], r: [0.46, 0.42, 0.3] }, { c: [0, 0.55, 0], r: [0.6, 0.6, 0.6] }]);
      decal(8, 0, 0, 0.56, [{ c: [0, 0, 0], r: [RB * 1.02, 9, RB * 1.02] }], 0.6);
    },
    () => {                                               // Qwen：紫色，头是交织的六角形结，中间深紫色的脸
      body(() => 0x8a5ad8); arms(cuff(0xb59cf0, 0x8a5ad8));
      sph(0.4, { p: [0, 0.72, 0], col: 0x3d2b78 });
      for (const [t0, dz] of [[Math.PI / 2, 0.07], [-Math.PI / 2, -0.07]]) for (let k = 0; k < 3; k++) {
        const a = t0 + k * Math.PI * 2 / 3, b = a + Math.PI * 2 / 3, R0 = 0.82;
        const pa = [Math.cos(a) * R0, 0.72 + Math.sin(a) * R0], pb = [Math.cos(b) * R0, 0.72 + Math.sin(b) * R0], ex = [(pb[0] - pa[0]) * 0.12, (pb[1] - pa[1]) * 0.12];
        rod([pa[0] - ex[0], pa[1] - ex[1], dz * (k % 2 ? 1 : -1)], [pb[0] + ex[0], pb[1] + ex[1], dz * (k % 2 ? -1 : 1)], 0.13, { col: 0xc3aef5 }, 6);
      }
      decal(4, 0, 0.72, 0.62, [{ c: [0, 0.72, 0], r: [0.4, 0.4, 0.4] }]);
    },
    () => {                                               // 豆包：米白衣服红条纹，棕色短发，红围巾
      body((v, th) => sw(th, F + 0.55, 0.05) || sw(th, F + 0.38, 0.05) ? 0xd93030 : 0xf1ead9); arms(cuff(0xf1ead9, 0xd93030));
      sph(0.54, { p: [0, 0.66, 0], col: 0xffdcc8 });
      sph(0.58, { p: [0, 0.74, -0.1], s: [1.04, 1, 1], col: 0x5a3a2a });
      sph(0.3, { p: [0, 1.04, 0.3], s: [1.6, 0.5, 0.8], col: 0x5a3a2a });
      for (const sx of [-1, 1]) sph(0.3, { p: [sx * 0.5, 0.48, -0.02], s: [0.6, 1.35, 0.95], col: 0x5a3a2a });
      part(new THREE.TorusGeometry(0.42, 0.14, 10, 24), { p: [0, 0.12, 0], r: [Math.PI / 2, 0, 0], col: 0xd92b2b });
      part(new THREE.BoxGeometry(0.24, 0.7, 0.08), { p: [0.3, -0.25, 0.44], r: [0.15, 0, 0.35], col: 0xd92b2b });
      part(new THREE.BoxGeometry(0.22, 0.55, 0.08), { p: [0.52, -0.12, 0.36], r: [0.1, 0, 0.75], col: 0xc72424 });
      decal(5, 0, 0.62, 0.8, [{ c: [0, 0.66, 0], r: [0.54, 0.54, 0.54] }]);
    },
    () => {                                               // GLM：正面白、侧后藏青，头是一个立体的 Z
      body((v, th) => Math.sin(th) > 0.3 ? 0xeef0f6 : 0x1f2a4d); arms(cuff(0x1f2a4d, 0x7fb6f0));
      const z = new THREE.Shape([[-0.7, 0.65], [0.7, 0.65], [0.7, 0.36], [-0.18, -0.34], [0.7, -0.34], [0.7, -0.65], [-0.7, -0.65], [-0.7, -0.36], [0.18, 0.34], [-0.7, 0.34]].map(([x, y]) => new THREE.Vector2(x, y)));
      ext(z, 0.22, 0.1, { p: [0, 0.82, -0.08], s: [1.07, 1.07, 1], col: 0x1f2a4d });
      ext(z, 0.24, 0.12, { p: [0, 0.82, 0.02], col: 0xf5f6fa });
      decal(6, 0, 0.82, 0.62, [{ flat: 0.02 + 0.12 + 0.12 }]);
    },
    () => {                                               // Kimi：藏青色小猫，米色肚皮和口鼻，蓝围巾，额头 K·
      body((v, th) => sw(th, F, 0.7) && v > 0.3 && v < 0.92 ? 0xf0e2c8 : 0x232d55); arms(cuff(0x232d55, 0xf0e2c8));
      sph(0.6, { p: [0, 0.62, 0], col: 0x232d55 });
      sph(1, { p: [0, 0.46, 0.36], s: [0.42, 0.32, 0.28], col: 0xf0e2c8 });
      for (const sx of [-1, 1]) {
        part(new THREE.ConeGeometry(0.24, 0.55, 14), { p: [sx * 0.36, 1.12, 0], r: [0, 0, -sx * 0.35], col: 0x232d55 });
        part(new THREE.ConeGeometry(0.13, 0.32, 10), { p: [sx * 0.35, 1.1, 0.09], r: [0, 0, -sx * 0.35], col: 0xf2a0b8 });
      }
      part(new THREE.TorusGeometry(0.44, 0.13, 10, 24), { p: [0, 0.1, 0], r: [Math.PI / 2, 0, 0], col: 0x3b6fe0 });
      part(new THREE.BoxGeometry(0.22, 0.6, 0.08), { p: [0.32, -0.22, 0.45], r: [0.15, 0, 0.3], col: 0x3b6fe0 });
      part(new THREE.TorusGeometry(0.38, 0.11, 8, 18, Math.PI * 1.25), { p: [0.55, -0.1, -0.35], r: [0, 0.9, 0], col: 0x232d55, at: 0.22 });
      decal(7, 0, 0.6, 0.92, [{ c: [0, 0.62, 0], r: [0.6, 0.6, 0.6] }, { c: [0, 0.46, 0.36], r: [0.42, 0.32, 0.28] }]);
    },
  ];
  // 两条长边各 8 个，从对面看过去从左到右都是 Claude … Kimi
  const Y = 2.2 + 4 * 2.4, XS = W2 + 17.6, bases = [];
  for (const sx of [-1, 1]) for (let k = 0; k < 8; k++) {
    const z = sx * (k - 3.5) * 11.5;
    cur = { base: [sx * XS, Y + 1.2, z], facing: Math.atan2(-sx, 0), seed: (sx + 1) * 4.1 + k * 1.37 + 0.5 };
    MASCOTS[k](); bases.push([sx * XS, z]);
  }
  // 表情贴图：4×4 格，0-7 是各家的脸，8 是 OpenAI 胸标
  const faceTex = canvasTex(1024, 1024, (g) => {
    const ell = (x, y, rx, ry) => { g.beginPath(); g.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); g.fill(); };
    const FACE = [{}, {}, {}, {}, { hi: 1.3 }, { iris: '#7a4a2e', lash: 1 }, {}, { iris: '#2f7bff', k: 1, nose: 1 }];
    FACE.forEach((o, i) => {
      const s = 256, cx = (i % 4) * s + s / 2, cy = Math.floor(i / 4) * s + s / 2 + 8;
      for (const sx of [-1, 1]) {
        const ex = cx + sx * 0.19 * s, ey = cy - 0.03 * s;
        if (o.iris) { g.fillStyle = '#16121c'; ell(ex, ey, 0.085 * s, 0.11 * s); g.fillStyle = o.iris; ell(ex, ey + 0.012 * s, 0.068 * s, 0.088 * s); g.fillStyle = '#0b0a10'; ell(ex, ey + 0.02 * s, 0.034 * s, 0.05 * s); }
        else { g.fillStyle = '#15121b'; ell(ex, ey, 0.062 * s, 0.084 * s); }
        if (o.lash) { g.strokeStyle = '#16121c'; g.lineWidth = 0.018 * s; g.beginPath(); g.moveTo(ex - sx * 0.07 * s, ey - 0.09 * s); g.lineTo(ex + sx * 0.1 * s, ey - 0.12 * s); g.stroke(); }
        g.fillStyle = '#ffffff'; ell(ex - 0.022 * s, ey - 0.035 * s, 0.026 * s * (o.hi || 1), 0.026 * s * (o.hi || 1)); ell(ex + 0.02 * s, ey + 0.03 * s, 0.012 * s, 0.012 * s);
      }
      g.save(); g.beginPath(); g.moveTo(cx - 0.085 * s, cy + 0.1 * s); g.quadraticCurveTo(cx, cy + 0.3 * s, cx + 0.085 * s, cy + 0.1 * s); g.closePath();
      g.fillStyle = '#5b1424'; g.fill(); g.clip(); g.fillStyle = '#ff7a93'; ell(cx, cy + 0.2 * s, 0.05 * s, 0.035 * s); g.restore();
      g.fillStyle = 'rgba(255,110,140,0.5)'; for (const sx of [-1, 1]) ell(cx + sx * 0.31 * s, cy + 0.07 * s, 0.065 * s, 0.036 * s);
      if (o.nose) { g.fillStyle = '#f08aa0'; ell(cx, cy + 0.065 * s, 0.03 * s, 0.02 * s); }
      if (o.k) { g.fillStyle = '#ffffff'; g.font = '900 ' + Math.round(0.2 * s) + 'px ' + SANS; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('K', cx - 0.02 * s, cy - 0.31 * s); ell(cx + 0.08 * s, cy - 0.37 * s, 0.026 * s, 0.026 * s); }
    });
    g.save(); g.translate(256 / 2, 2 * 256 + 128); ICONS.knot(g, 100, '#1fa68a'); g.restore();
  });
  // 共用的形变着色器片段（注入 MeshStandardMaterial / MeshDepthMaterial）
  const common = `
    uniform float uTime; uniform vec3 uCamPos; attribute vec3 aBase; attribute vec4 aMeta; varying float vFade;
    vec3 gR, gF; float gSeed, gT, gFlop, gHs;
    void dSpine(float v, out vec3 P, out vec3 T) {
      float L = ${AL.toFixed(2)}, amp = (0.10 + 0.20 * gFlop) * L;
      float p1 = gT * 2.2 - v * 3.2, p2 = gT * 3.7 - v * 5.6 + gSeed, p3 = gT * 1.6 - v * 2.4 + gSeed * 1.3;
      float w = sin(p1) * 0.65 + sin(p2) * 0.35, dw = -cos(p1) * 3.2 * 0.65 - cos(p2) * 5.6 * 0.35;
      float w2 = sin(p3) * 0.5 + 0.55 * gFlop, dw2 = -cos(p3) * 2.4 * 0.5;
      float sx = w * v * v * amp, dsx = dw * v * v * amp + w * 2.0 * v * amp;
      float sz = w2 * v * v * amp, dsz = dw2 * v * v * amp + w2 * 2.0 * v * amp;
      P = aBase + gR * sx + gF * sz + vec3(0.0, v * L * gHs, 0.0);
      T = normalize(gR * dsx + gF * dsz + vec3(0.0, L * gHs, 0.0));
    }
    void dDeform(vec3 p, vec3 n, out vec3 wp, out vec3 wn) {
      float a = aMeta.x; gF = vec3(sin(a), 0.0, cos(a)); gR = vec3(gF.z, 0.0, -gF.x);
      gSeed = aMeta.y; gT = uTime + gSeed * 7.0;
      gFlop = smoothstep(0.82, 1.0, sin(gT * 0.41 + gSeed * 3.0)); gHs = 1.0 - 0.33 * gFlop;
      vec3 P, T, R, F;
      if (aMeta.z < 0.5) {
        float v = p.y / ${AL.toFixed(2)}; dSpine(v, P, T); R = normalize(gR - dot(gR, T) * T); F = cross(R, T);
        float rip = (1.0 + 0.04 * sin(v * 34.0 - gT * 7.0)) * (1.0 - 0.1 * gFlop * v);
        wp = P + (p.x * R + p.z * F) * rip; wn = normalize(n.x * R + n.z * F);
      } else if (aMeta.z < 1.5) {
        float side = aMeta.w; dSpine(0.8, P, T); R = normalize(gR - dot(gR, T) * T); F = cross(R, T);
        vec3 S = P + side * R * ${(RB * 0.7).toFixed(3)};
        float ph0 = 0.3 + 0.65 * sin(gT * 3.1 + side * 1.3 + gSeed) - 1.2 * gFlop, k = 1.5 * sin(gT * 4.4 + side * 2.1 + gSeed * 1.7);
        float u = p.x, ph = ph0 + k * u; vec2 q;
        if (abs(k) < 0.03) q = u * vec2(cos(ph0 + k * u * 0.5), sin(ph0 + k * u * 0.5));
        else q = vec2(sin(ph) - sin(ph0), cos(ph0) - cos(ph)) / k;
        vec3 Ta = cos(ph) * side * R + sin(ph) * T, Na = normalize(cross(Ta, F));
        wp = S + ${ARM.toFixed(2)} * (q.x * side * R + q.y * T) + p.y * F + p.z * Na; wn = normalize(n.y * F + n.z * Na);
      } else {
        dSpine(aMeta.w, P, T); R = normalize(gR - dot(gR, T) * T); F = cross(R, T);
        wp = P + p.x * R + p.y * T + p.z * F; wn = normalize(n.x * R + n.y * T + n.z * F);
      }
      // 镜头在看台外面时，镜头这一侧的人偶会挡住球场，逐渐隐去（阴影也一起去掉）
      vec2 cp = uCamPos.xz, dp = aBase.xz;
      vFade = 1.0 - smoothstep(48.0, 70.0, length(cp)) * smoothstep(0.3, 0.5, dot(normalize(dp), normalize(cp + vec2(1e-4))));
    }`;
  const dither = 'if (vFade <= fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))))) discard;';
  const hook = depth => sh => {
    sh.uniforms.uTime = airU.uTime; sh.uniforms.uCamPos = airU.uCamPos;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\n' + common)
      .replace('#include <beginnormal_vertex>', 'vec3 dP0, objectNormal; dDeform(position, normal, dP0, objectNormal);')
      .replace('#include <begin_vertex>', 'vec3 transformed, dN0; dDeform(position, normal, transformed, dN0);' + (depth ? ' if (vFade < 0.5) transformed = vec3(0.0, -500.0, 0.0);' : ''));
    if (!depth) sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vFade;').replace('void main() {', 'void main() {\n' + dither);
  };
  const build = (T, uv) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(T.pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(T.nrm, 3));
    g.setAttribute('aBase', new THREE.Float32BufferAttribute(T.base, 3)); g.setAttribute('aMeta', new THREE.Float32BufferAttribute(T.meta, 4));
    if (T.col) g.setAttribute('color', new THREE.Float32BufferAttribute(T.col, 3)); if (uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(T.uv, 2));
    g.setIndex(T.idx); return g;
  };
  const cloth = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.0, side: THREE.DoubleSide });
  cloth.onBeforeCompile = hook(false);
  const decalMat = new THREE.MeshStandardMaterial({ map: faceTex, transparent: true, alphaTest: 0.3, roughness: 0.5, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
  decalMat.onBeforeCompile = hook(false);
  const depthMat = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking }); depthMat.onBeforeCompile = hook(true);
  const clothMesh = new THREE.Mesh(build(B), cloth); clothMesh.frustumCulled = false; clothMesh.castShadow = true; clothMesh.customDepthMaterial = depthMat; scene.add(clothMesh);
  const decalMesh = new THREE.Mesh(build(D, true), decalMat); decalMesh.frustumCulled = false; decalMesh.renderOrder = 2; scene.add(decalMesh);

  // 鼓风机：深藏青箱体 + 出风口圈 + 四个小脚（和人偶一起隐去，不投影）
  const baseGrp = new THREE.Group(); scene.add(baseGrp);
  const boxMat = new THREE.MeshStandardMaterial({ color: 0x1d2742, metalness: 0.35, roughness: 0.55 });
  const grilleMat = new THREE.MeshStandardMaterial({ color: 0x0b1020, metalness: 0.5, roughness: 0.7 });
  const fadeHook = sh => {
    sh.uniforms.uCamPos = airU.uCamPos;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nuniform vec3 uCamPos; varying float vFade;').replace('#include <begin_vertex>', `#include <begin_vertex>
      { vec2 cp = uCamPos.xz, dp = position.xz; vFade = 1.0 - smoothstep(48.0, 70.0, length(cp)) * smoothstep(0.3, 0.5, dot(normalize(dp), normalize(cp + vec2(1e-4)))); }`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vFade;').replace('void main() {', 'void main() {\n' + dither);
  };
  boxMat.onBeforeCompile = grilleMat.onBeforeCompile = fadeHook;
  for (const [x, z] of bases) {
    const box = new THREE.Mesh(new THREE.BoxGeometry(1.7, 1.0, 1.7), boxMat); box.position.set(x, Y + 0.62, z); baseGrp.add(box);
    const vent = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.7, 0.16, 20), grilleMat); vent.position.set(x, Y + 1.18, z); baseGrp.add(vent);
    const grille = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.04, 20), grilleMat); grille.rotation.z = Math.PI / 2; grille.position.set(x - Math.sign(x) * 0.86, Y + 0.62, z); baseGrp.add(grille);
    for (const [fx, fz] of [[-0.6, -0.6], [0.6, -0.6], [-0.6, 0.6], [0.6, 0.6]]) {
      const foot = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.14, 0.22), grilleMat); foot.position.set(x + fx, Y + 0.07, z + fz); baseGrp.add(foot);
    }
  }
  mergeChildren(baseGrp);
}
// 尾焰贴图：根部白黄、中段橙、尖端渐隐（加色混合，黑色即透明）
const flameTex = canvasTex(32, 128, (g, w, h) => { const gr = g.createLinearGradient(0, h, 0, 0); gr.addColorStop(0, 'rgba(255,250,225,1)'); gr.addColorStop(0.3, 'rgba(255,170,60,1)'); gr.addColorStop(0.7, 'rgba(230,70,20,0.6)'); gr.addColorStop(1, 'rgba(120,20,10,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); });
function numberTex(num, css) {
  return canvasTex(256, 128, (g, w, h) => {
    g.fillStyle = '#eef2f8'; g.fillRect(0, 0, w, h);
    g.fillStyle = css; g.fillRect(0, 0, w, 16); g.fillRect(0, h - 12, w, 12);
    g.font = '900 86px system-ui, "Arial Black", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(num, w / 2, h / 2 + 4);
  });
}
// 机器人：参考 CodeBall 原版的低多边形宇航员机器人——队色头盔包着一个深蓝色大球形面罩，白色躯干，
// 队色的大拳套和靴子上有白色条纹，所有硬壳都用平直着色做出切面感。
// 物理上它仍是半径 robot_radius 的球，模型正好装在这个球里（脚底贴地）。
function buildRobot(col, css, num) {
  const root = new THREE.Group(); scene.add(root);
  const yawG = new THREE.Group(); root.add(yawG);
  const body = new THREE.Group(); body.scale.setScalar(M.robot_radius); yawG.add(body);
  const metal = new THREE.MeshStandardMaterial({ color: new THREE.Color(col).convertSRGBToLinear(), roughness: 0.42, metalness: 0.05, flatShading: true, emissive: 0xff6a00, emissiveIntensity: 0 });
  const white = new THREE.MeshStandardMaterial({ color: 0xeef0f3, roughness: 0.45, metalness: 0.02, flatShading: true });
  const whiteDS = white.clone(); whiteDS.side = THREE.DoubleSide;
  const dark = new THREE.MeshStandardMaterial({ color: 0x15181e, roughness: 0.6, flatShading: true });
  const visor = new THREE.MeshPhysicalMaterial({ color: 0x0e2d55, metalness: 0.2, roughness: 0.1, clearcoat: 1, clearcoatRoughness: 0.05 });
  const add = (geo, mat, x, y, z, parent) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; (parent || body).add(m); return m; };
  const cyl = (r0, r1, h, seg) => new THREE.CylinderGeometry(r0, r1, h, seg || 6);
  const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
  // 躯干：队色胸甲上沿 + 白色胸腹 + 队色腰带
  add(cyl(0.37, 0.33, 0.14, 8), metal, 0, 0.17, 0).rotation.y = Math.PI / 8;
  add(cyl(0.33, 0.24, 0.36, 8), white, 0, -0.06, 0).rotation.y = Math.PI / 8;
  add(cyl(0.25, 0.2, 0.13, 8), metal, 0, -0.29, 0).rotation.y = Math.PI / 8;
  add(cyl(0.27, 0.3, 0.07, 10), white, 0, 0.26, 0);                                  // 领口
  // 胸前小号码牌
  const plate = add(new THREE.PlaneGeometry(0.22, 0.11), new THREE.MeshStandardMaterial({ map: numberTex(num, css), roughness: 0.5 }), 0, -0.02, 0.305);
  plate.rotation.x = -0.22; plate.castShadow = false;
  // 头：低多边形队色头盔 + 深蓝球形面罩 + 面罩下沿的白色护颚 + 两侧带格栅的耳罩
  const head = new THREE.Group(); head.position.set(0, 0.56, 0); body.add(head);
  add(new THREE.IcosahedronGeometry(0.42, 1), metal, 0, 0.02, -0.03, head).scale.set(1, 0.93, 0.98);
  add(new THREE.SphereGeometry(0.335, 40, 28), visor, 0, -0.01, 0.12, head);
  add(new THREE.CylinderGeometry(0.33, 0.33, 0.09, 14, 1, true, -1.25, 2.5), whiteDS, 0, -0.29, 0.06, head).scale.set(1, 1, 1.05);
  for (const sx of [-1, 1]) {
    add(box(0.12, 0.3, 0.3), metal, sx * 0.4, 0.04, 0.02, head);
    for (let k = -1; k <= 1; k++) add(box(0.015, 0.2, 0.035), dark, sx * 0.462, 0.04, 0.02 + k * 0.07, head);
  }
  // 手臂：小肩关节 + 白色上臂 + 队色大拳套（上面两道白条纹）
  const arms = [-1, 1].map(sx => {
    add(new THREE.IcosahedronGeometry(0.12, 0), metal, sx * 0.4, 0.13, 0);
    const pv = new THREE.Group(); pv.position.set(sx * 0.44, 0.12, 0); pv.rotation.z = sx * 0.22; body.add(pv);
    add(cyl(0.07, 0.065, 0.2, 6), white, 0, -0.12, 0, pv);
    add(box(0.22, 0.24, 0.25), metal, 0, -0.32, 0.03, pv);
    for (const dz of [-0.04, 0.05]) add(box(0.226, 0.035, 0.035), white, 0, -0.26, 0.03 + dz, pv);
    add(box(0.2, 0.08, 0.2), metal, 0, -0.47, 0.05, pv).rotation.x = 0.3;            // 握拳的指节
    return pv;
  });
  // 腿：队色髋关节 + 白色粗小腿 + 队色厚靴子（侧面白条纹）
  const legs = [-1, 1].map(sx => {
    const pv = new THREE.Group(); pv.position.set(sx * 0.17, -0.36, 0); body.add(pv);
    add(new THREE.IcosahedronGeometry(0.1, 0), metal, 0, -0.04, 0, pv);
    add(cyl(0.12, 0.16, 0.3, 6), white, 0, -0.22, 0, pv);
    for (const dy of [-0.2, -0.27]) add(box(0.3, 0.03, 0.12), metal, 0, dy, 0.07, pv).rotation.x = -0.35;
    add(box(0.25, 0.17, 0.38), metal, 0, -0.46, 0.05, pv);
    add(box(0.23, 0.07, 0.12), metal, 0, -0.42, 0.25, pv).rotation.x = 0.5;           // 鞋头
    for (const dx of [-1, 1]) add(box(0.01, 0.04, 0.2), white, dx * 0.128, -0.45, 0.06, pv);
    return pv;
  });
  // 背包和氮气喷口
  add(box(0.42, 0.36, 0.17), white, 0, 0.0, -0.34);
  add(box(0.44, 0.06, 0.18), metal, 0, 0.12, -0.34);
  add(new THREE.CylinderGeometry(0.12, 0.17, 0.2, 16, 1, true), new THREE.MeshStandardMaterial({ color: 0xaab4c2, metalness: 0.9, roughness: 0.25, side: THREE.DoubleSide }), 0, -0.04, -0.5).rotation.x = Math.PI / 2;
  const cap = add(new THREE.CircleGeometry(0.14, 20), new THREE.MeshBasicMaterial({ color: 0x1a1d24 }), 0, -0.04, -0.49); cap.rotation.y = Math.PI;
  const flame = new THREE.Group(); flame.position.set(0, -0.04, -0.6); flame.rotation.x = -Math.PI / 2; body.add(flame);
  const fmat = new THREE.MeshBasicMaterial({ map: flameTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, side: THREE.DoubleSide });
  for (const [r, l] of [[0.18, 1.9], [0.1, 1.2]]) { const g = new THREE.ConeGeometry(r, l, 16, 1, true); g.translate(0, l / 2, 0); /* 宽口在喷口处，尖端向外 */ flame.add(new THREE.Mesh(g, fmat)); }
  flame.visible = false;
  // 远景也看得见的氮气光晕
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: softTex, color: 0xff7a1a, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.4 }));
  glow.scale.set(3.5, 3.5, 1); glow.visible = false; root.add(glow);
  const keep = new Set([cap]);
  for (const part of [body, head, ...arms, ...legs]) mergeChildren(part, keep);
  return { grp: root, yawG, body, metal, arms, legs, cap, flame, glow };
}
const robots = F[0].r.map((_, i) => {
  const team = M.teams[i], idx = M.teams.slice(0, i).filter(t => t === team).length, col = team === 0 ? COL_A : COL_B;
  const css = team === 0 ? '#16a34a' : '#e2401c';
  const rb = buildRobot(team === 0 ? 0x13b832 : 0xf0441a, css, String(idx + 1));
  rb.grp.traverse(o => { if (o.isMesh && o.material.type !== 'MeshBasicMaterial') o.castShadow = true; });
  const label = labelSprite(String(idx + 1), css); label.position.y = 2.3; rb.grp.add(label); rb.label = label;
  // 氮气条（只在开启氮气时显示）
  const barBg = new THREE.Sprite(new THREE.SpriteMaterial({ color: 0x000000, opacity: 0.55, transparent: true, depthTest: false })); barBg.center.set(0, 0.5); barBg.scale.set(2.2, 0.24, 1); barBg.renderOrder = 11;
  const barFg = new THREE.Sprite(new THREE.SpriteMaterial({ color: 0xfacc15, depthTest: false, transparent: true })); barFg.center.set(0, 0.5); barFg.scale.set(2.2, 0.24, 1); barFg.renderOrder = 12;
  const bars = new THREE.Group(); bars.add(barBg, barFg); bars.position.set(-1.1, 3.2, 0); rb.grp.add(bars); bars.visible = M.packs.length > 0; rb.bars = bars;
  return Object.assign(rb, { barFg, team, idx, css, last: null, yaw: team === 0 ? 0 : Math.PI, phase: 0 });
});
// 氮气喷射的火花粒子
const NP = 1200, pPos = new Float32Array(NP * 3), pCol = new Float32Array(NP * 3), pVel = new Float32Array(NP * 3), pLife = new Float32Array(NP), pMax = new Float32Array(NP);
for (let i = 0; i < NP; i++) pPos[i * 3 + 1] = -999;
const pGeo = new THREE.BufferGeometry();
pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3)); pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3));
const sparks = new THREE.Points(pGeo, new THREE.PointsMaterial({ size: 0.8, map: softTex, vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
sparks.frustumCulled = false; scene.add(sparks);
let pNext = 0;
function emitSpark(p, v, life) {
  const i = pNext; pNext = (pNext + 1) % NP;
  pPos.set(p, i * 3); pVel.set(v, i * 3); pLife[i] = pMax[i] = life;
}
function stepSparks(dt) {
  if (dt <= 0) return;
  const drag = Math.pow(0.04, dt);
  for (let i = 0; i < NP; i++) {
    if (pLife[i] <= 0) continue;
    pLife[i] -= dt;
    const j = i * 3;
    if (pLife[i] <= 0) { pPos[j + 1] = -999; pCol[j] = pCol[j + 1] = pCol[j + 2] = 0; continue; }
    pVel[j] *= drag; pVel[j + 1] = pVel[j + 1] * drag + 3 * dt; pVel[j + 2] *= drag;
    pPos[j] += pVel[j] * dt; pPos[j + 1] += pVel[j + 1] * dt; pPos[j + 2] += pVel[j + 2] * dt;
    const t = pLife[i] / pMax[i] * 0.75;  // 1 -> 0：黄 -> 橙 -> 暗红（整体压暗，避免过曝）
    pCol[j] = t > 0.5 ? 1 : 0.35 + 1.3 * t; pCol[j + 1] = t > 0.5 ? 0.45 + 1.1 * (t - 0.5) : 0.9 * t * t; pCol[j + 2] = t > 0.7 ? (t - 0.7) * 2 : 0.04 * t;
  }
  pGeo.attributes.position.needsUpdate = true; pGeo.attributes.color.needsUpdate = true;
}

// 氮气瓶：蓝色高压气瓶 + 白色 NITRO 标签 + 镀铬阀门和红色手轮
function bottleLabelTex() {
  return canvasTex(512, 128, (g, w, h) => {
    g.fillStyle = '#f8fafc'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#dc2626'; g.fillRect(0, 0, w, 12); g.fillRect(0, h - 12, w, 12);
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let i = 0; i < 2; i++) {
      const cx = w / 4 + i * w / 2;
      g.fillStyle = '#0f172a'; g.font = 'italic 900 52px system-ui, "Arial Black", sans-serif'; g.fillText('NITRO', cx, 54);
      g.fillStyle = '#dc2626'; g.font = '800 26px system-ui, sans-serif'; g.fillText('N₂O  ·  100', cx, 96);
    }
  });
}
const tankMat = new THREE.MeshPhysicalMaterial({ color: 0x1d4ed8, metalness: 0.55, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.06, emissive: 0x0b2a72, emissiveIntensity: 0.35 });
const chromeMat = new THREE.MeshStandardMaterial({ color: 0xe5ebf2, metalness: 1, roughness: 0.16 });
const redMat = new THREE.MeshStandardMaterial({ color: 0xdc2626, metalness: 0.3, roughness: 0.35 });
const bottleLabel = bottleLabelTex();
function makeBottle() {
  const b = new THREE.Group();
  const add = (geo, mat, x, y, z) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; b.add(m); return m; };
  add(new THREE.LatheGeometry(V2([[0, -0.62], [0.2, -0.62], [0.26, -0.58], [0.28, -0.5], [0.28, 0.3], [0.26, 0.4], [0.2, 0.48], [0.12, 0.53], [0.08, 0.56], [0, 0.56]]), 36), tankMat, 0, 0, 0);
  add(new THREE.CylinderGeometry(0.285, 0.285, 0.42, 36, 1, true), new THREE.MeshPhysicalMaterial({ map: bottleLabel, roughness: 0.4, clearcoat: 0.6 }), 0, -0.08, 0);
  add(new THREE.CylinderGeometry(0.07, 0.085, 0.12, 16), chromeMat, 0, 0.6, 0);
  add(new THREE.CylinderGeometry(0.095, 0.095, 0.15, 16), chromeMat, 0, 0.73, 0);
  add(new THREE.CylinderGeometry(0.035, 0.035, 0.2, 10), chromeMat, 0.13, 0.72, 0).rotation.z = Math.PI / 2;
  add(new THREE.CylinderGeometry(0.055, 0.055, 0.06, 6), chromeMat, 0.24, 0.72, 0).rotation.z = Math.PI / 2;
  add(new THREE.CylinderGeometry(0.025, 0.025, 0.1, 8), chromeMat, 0, 0.84, 0);
  add(new THREE.TorusGeometry(0.11, 0.024, 8, 28), redMat, 0, 0.89, 0).rotation.x = Math.PI / 2;
  for (const a of [0, Math.PI / 2]) add(new THREE.BoxGeometry(0.22, 0.02, 0.025), redMat, 0, 0.89, 0).rotation.y = a;
  b.scale.setScalar(1.3);
  return b;
}
const PACK_RESPAWN = M.pack_respawn || 600;
const packs = (M.packs || []).map((p, k) => {
  const grp = new THREE.Group(); grp.position.set(p[0], p[1], p[2]); scene.add(grp);
  const bottle = makeBottle(); grp.add(bottle);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: softTex, color: 0x38bdf8, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.55 }));
  halo.scale.set(3.4, 3.4, 1); grp.add(halo);
  const pad = new THREE.Mesh(new THREE.RingGeometry(1.05, 1.32, 48), new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.5, side: THREE.DoubleSide, depthWrite: false }));
  pad.rotation.x = -Math.PI / 2; pad.position.y = -p[1] + 0.03; grp.add(pad);
  const ring = new THREE.Mesh(new THREE.RingGeometry(1.05, 1.32, 48), new THREE.MeshBasicMaterial({ color: 0x7dd3fc, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false }));
  ring.rotation.x = -Math.PI / 2; ring.position.y = -p[1] + 0.05; ring.visible = false; grp.add(ring);
  const burst = new THREE.Sprite(new THREE.SpriteMaterial({ map: softTex, color: 0x7dd3fc, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0 }));
  burst.visible = false; grp.add(burst);
  // 每一帧这个氮气瓶从哪个 tick 开始消失（用来画刷新倒计时圆环）
  const dead = new Int32Array(F.length); let ds = -1;
  F.forEach((f, i) => { const alive = !f.n || f.n[k]; if (alive) ds = -1; else if (ds < 0) ds = f.t; dead[i] = ds; });
  return { grp, bottle, halo, pad, ring, burst, dead, q: -1, prev: null, flash: 0 };
});
function setRing(pk, v) {
  const q = Math.round(Math.max(0, Math.min(1, v)) * 64);
  if (q === pk.q) return;
  pk.q = q; pk.ring.geometry.dispose();
  pk.ring.geometry = new THREE.RingGeometry(1.05, 1.32, 48, 1, Math.PI / 2, Math.max(0.001, q / 64 * Math.PI * 2));
}
const tmpV = new THREE.Vector3();

// ---------------------------------------------------------------- 相机
const cam = { mode: 'tv', yaw: Math.PI, pitch: 0.42, dist: 95, target: new THREE.Vector3(0, 3, 0) };
const presets = {
  tv:     { yaw: Math.PI,       pitch: 0.42, dist: 92 },
  follow: { yaw: Math.PI,       pitch: 0.30, dist: 20 },
  top:    { yaw: Math.PI,       pitch: 1.47, dist: 120 },
  goalA:  { yaw: -Math.PI / 2,  pitch: 0.46, dist: 78 },
  goalB:  { yaw: Math.PI / 2,   pitch: 0.46, dist: 78 },
  free:   {},
};
// 竖屏时把转播和俯视镜头转 90°，让球场的长边竖着放，画面更大
const presetsPortrait = { tv: { yaw: Math.PI / 2, pitch: 0.78 }, top: { yaw: Math.PI / 2, pitch: 1.47 } };
const portrait = () => innerWidth < innerHeight;
const TVF = { x: 0.12, z: 0.25 };                   // 转播镜头跟着球微微平移的幅度
// 自动取景：算出上方比分牌和下方控制栏之间还剩多少空间，把画面中心挪到这块空间的正中，
// 再找一个刚好让整块场地（含两个球门）都装得下的镜头距离
const view = { top: 0, bot: 0 };
function measureHud() {
  if (FIXED || document.body.classList.contains('clean')) { view.top = view.bot = 0; camera.clearViewOffset(); camera.updateProjectionMatrix(); return; }
  const h = innerHeight, tb = document.querySelector('.board').getBoundingClientRect(), rows = document.querySelectorAll('.bottom .row');
  view.top = tb.bottom + 4; view.bot = h - rows[0].getBoundingClientRect().top + 4;
  const shift = (view.bot - view.top) / 2;
  camera.setViewOffset(innerWidth, h, 0, shift, innerWidth, h); camera.updateProjectionMatrix();
}
const fitPts = [];
for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
  fitPts.push([sx * W2, 0, sz * D2], [sx * GW2, 0, sz * (D2 + GD)], [sx * GW2, GH, sz * (D2 + GD)], [sx * (W2 - CR), 0, sz * D2], [sx * W2, 0, sz * (D2 - CR)]);
}
const fitCam = new THREE.PerspectiveCamera();
function fitDist(yaw, pitch, follow) {
  fitCam.copy(camera);
  const lim = Math.max(0.2, 1 - (view.top + view.bot) / innerHeight) * 0.94, v = new THREE.Vector3();
  const targets = follow ? [[-1, -1], [-1, 1], [1, -1], [1, 1]].map(([a, b]) => new THREE.Vector3(a * TVF.x * W2, 3, b * TVF.z * D2)) : [new THREE.Vector3(0, 3, 0)];
  const fits = d => targets.every(t => {
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    fitCam.position.set(t.x + d * cp * Math.cos(yaw), t.y + d * sp, t.z + d * cp * Math.sin(yaw)); fitCam.lookAt(t); fitCam.updateMatrixWorld();
    return fitPts.every(p => { v.set(p[0], p[1], p[2]).project(fitCam); return Math.abs(v.x) <= 0.95 && Math.abs(v.y) <= lim && v.z < 1; });
  });
  let lo = 15, hi = 600;
  for (let k = 0; k < 28; k++) { const mid = (lo + hi) / 2; if (fits(mid)) hi = mid; else lo = mid; }
  return hi;
}
function setCam(m) {
  cam.mode = m; Object.assign(cam, presets[m], portrait() ? presetsPortrait[m] : {});
  if (m !== 'follow' && m !== 'tv') cam.target.set(0, 3, 0);
  if (m === 'tv' || m === 'top' || m === 'goalA' || m === 'goalB') cam.dist = fitDist(cam.yaw, cam.pitch, m === 'tv');
  if (m === 'follow') { chase.off = 0; chase.last = null; camera.position.copy(clampInArena(camera.position.clone(), 1.5)); }
  document.querySelectorAll('[data-cam]').forEach(b => b.classList.toggle('on', b.dataset.cam === m));
}
document.querySelectorAll('[data-cam]').forEach(b => b.onclick = () => setCam(b.dataset.cam));
let shake = 0;
// 跟随视角：镜头在球的运动方向后方追着球，并且始终限制在场内（不会被墙和看台挡住）
const chase = { yaw: -Math.PI / 2, off: 0, last: null };
function clampInArena(p, m) {
  const w = W2 - m, d = D2 - m, r = Math.max(0.5, CR - m);
  p.x = Math.max(-w, Math.min(w, p.x)); p.z = Math.max(-d, Math.min(d, p.z));
  const cx = w - r, cz = d - r, ax = Math.abs(p.x), az = Math.abs(p.z);
  if (ax > cx && az > cz) {  // 圆角处投影回圆弧内
    const dx = ax - cx, dz = az - cz, l = Math.hypot(dx, dz);
    if (l > r) { p.x = Math.sign(p.x) * (cx + dx / l * r); p.z = Math.sign(p.z) * (cz + dz / l * r); }
  }
  p.y = Math.max(1.5, Math.min(H - 1.2, p.y));
  return p;
}
function placeCamera(bp, dt) {
  if (cam.mode === 'tv') cam.target.lerp(new THREE.Vector3(bp.x * TVF.x, 3, bp.z * TVF.z), 1 - Math.exp(-dt * 2.5));
  if (cam.mode === 'follow') {
    cam.target.lerp(new THREE.Vector3(bp.x, 1 + bp.y * 0.5, bp.z), 1 - Math.exp(-dt * 6));  // 看向球和地面之间，球在空中时也能看到场地
    // 用球的水平速度决定镜头方向：镜头放在速度反方向
    if (chase.last && dt > 0) {
      const vx = (bp.x - chase.last.x) / dt, vz = (bp.z - chase.last.z) / dt, sp = Math.hypot(vx, vz);
      if (sp > 4 && sp < 200) {
        const want = Math.atan2(-vz, -vx);
        let dy = want - chase.yaw; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
        chase.yaw += dy * (1 - Math.exp(-dt * 1.6));
      }
    }
    chase.last = bp.clone();
    const yaw = chase.yaw + chase.off, cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    const want = new THREE.Vector3(cam.target.x + cam.dist * cp * Math.cos(yaw), cam.target.y + cam.dist * sp, cam.target.z + cam.dist * cp * Math.sin(yaw));
    clampInArena(want, 1.5);
    camera.position.lerp(want, 1 - Math.exp(-dt * 5));
    clampInArena(camera.position, 1.5);
  } else {
    const cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
    camera.position.set(cam.target.x + cam.dist * cp * Math.cos(cam.yaw), cam.target.y + cam.dist * sp, cam.target.z + cam.dist * cp * Math.sin(cam.yaw));
  }
  if (shake > 0) { camera.position.x += (Math.random() - 0.5) * shake; camera.position.y += (Math.random() - 0.5) * shake; shake *= Math.exp(-dt * 4); }
  camera.lookAt(cam.target);
}
// 拖动旋转 / 缩放
const ptrs = new Map(); let pinch0 = null;
const cv = renderer.domElement;
cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); });
const up = e => { ptrs.delete(e.pointerId); pinch0 = null; };
cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
cv.addEventListener('pointermove', e => {
  if (!ptrs.has(e.pointerId)) return;
  const [px, py] = ptrs.get(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]);
  if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]); if (pinch0) cam.dist = Math.min(260, Math.max(12, cam.dist * pinch0 / d)); pinch0 = d; }
  else { if (cam.mode === 'follow') chase.off += (e.clientX - px) * 0.007; else cam.yaw += (e.clientX - px) * 0.007; cam.pitch = Math.min(1.5, Math.max(0.04, cam.pitch + (e.clientY - py) * 0.005)); }
});
cv.addEventListener('wheel', e => { e.preventDefault(); cam.dist = Math.min(260, Math.max(12, cam.dist * Math.exp(e.deltaY * 0.001))); }, { passive: false });

// ---------------------------------------------------------------- 音效（Web Audio 实时合成，不需要外部音频文件）
// 开场号角、开球/终场哨、踢球、撞墙、撞网、落地、氮气喷射、吃氮气瓶、进球号角 + 观众欢呼、回放转场，
// 外加一直在的观众环境声（球越靠近球门越躁动）。浏览器要求用户先点一下页面才能出声。
const SND = (() => {
  let ac = null, out = null, nbuf = null, on = true, crowd = null, hiss = null, lastKick = 0, pendIntro = 0, onState = null;
  // 浏览器（尤其 iOS Safari）只在真正的点击/抬手里允许出声，pointerdown 里 resume 常常无效。
  // 所以每次手势都尝试 resume + 播一个空样本解锁；还没解锁时触发的开场号角先记下，解锁后补播。
  function stateChanged() {
    if (ac && ac.state === 'running' && pendIntro && performance.now() - pendIntro < 2500) { pendIntro = 0; API.intro(); }
    if (onState) onState();
  }
  function init() {
    if (!ac) {
      try {
        ac = new (window.AudioContext || window.webkitAudioContext)();
        ac.onstatechange = stateChanged;
        const comp = ac.createDynamicsCompressor(); comp.connect(ac.destination);
        out = ac.createGain(); out.gain.value = on ? 0.6 : 0; out.connect(comp);
        // 体育馆混响：用一段按指数衰减的噪声做卷积混响，尾音是平滑的一片，不会像反馈延迟那样听成"咚咚咚"好几下
        const send = ac.createGain(); send.gain.value = 0.18; out.connect(send);
        const rev = ac.createConvolver(), len = Math.round(ac.sampleRate * 1.4), ir = ac.createBuffer(2, len, ac.sampleRate);
        for (let ch = 0; ch < 2; ch++) { const d = ir.getChannelData(ch); for (let i = 0; i < len; i++) { const t = i / len; d[i] = (Math.random() * 2 - 1) * Math.pow(1 - t, 3.2) * (i < ac.sampleRate * 0.012 ? i / (ac.sampleRate * 0.012) : 1); } }
        rev.buffer = ir; const rlp = ac.createBiquadFilter(); rlp.type = 'lowpass'; rlp.frequency.value = 2400;
        send.connect(rev); rev.connect(rlp); rlp.connect(comp);
        nbuf = ac.createBuffer(1, ac.sampleRate * 3, ac.sampleRate);
        const ch = nbuf.getChannelData(0); for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
        // 观众环境声：粉噪声过几组"人声共振峰"带通，各自被慢速随机起伏调制，听起来像远处一片人声
        const pink = ac.createBuffer(1, ac.sampleRate * 4, ac.sampleRate), pc = pink.getChannelData(0);
        let b0 = 0, b1 = 0, b2 = 0;
        for (let i = 0; i < pc.length; i++) { const w = Math.random() * 2 - 1; b0 = 0.997 * b0 + w * 0.03; b1 = 0.985 * b1 + w * 0.05; b2 = 0.95 * b2 + w * 0.1; pc[i] = (b0 + b1 + b2 + w * 0.05) * 1.6; }
        crowd = { g: ac.createGain(), f: [] }; crowd.g.gain.value = 0; crowd.g.connect(out);
        for (const [f, q, v] of [[420, 1.2, 1], [900, 1.6, 0.8], [1700, 2, 0.45], [2900, 2.5, 0.2]]) {
          const src = ac.createBufferSource(); src.buffer = pink; src.loop = true;
          const flt = ac.createBiquadFilter(); flt.type = 'bandpass'; flt.frequency.value = f; flt.Q.value = q;
          const g = ac.createGain(); g.gain.value = v;
          const lfo = ac.createOscillator(), lg = ac.createGain(); lfo.frequency.value = 0.13 + Math.random() * 0.3; lg.gain.value = v * 0.35;
          lfo.connect(lg); lg.connect(g.gain); lfo.start();
          src.connect(flt); flt.connect(g); g.connect(crowd.g); src.start(0, Math.random() * 3);
          crowd.f.push(flt);
        }
        // 氮气喷射的持续嘶声
        hiss = ac.createGain(); hiss.gain.value = 0; hiss.connect(out);
        const hs = ac.createBufferSource(); hs.buffer = nbuf; hs.loop = true;
        const hf = ac.createBiquadFilter(); hf.type = 'bandpass'; hf.frequency.value = 2400; hf.Q.value = 0.7;
        const rumble = ac.createBiquadFilter(); rumble.type = 'lowpass'; rumble.frequency.value = 160;
        const rg = ac.createGain(); rg.gain.value = 2.2;
        hs.connect(hf); hf.connect(hiss); hs.connect(rumble); rumble.connect(rg); rg.connect(hiss); hs.start();
      } catch (e) { ac = null; }
    }
    if (ac && ac.state !== 'running') {
      try { const b = ac.createBufferSource(); b.buffer = ac.createBuffer(1, 1, 22050); b.connect(ac.destination); b.start(0); } catch (e) {}
      const r = ac.resume(); if (r && r.then) r.then(stateChanged, () => {});
    }
  }
  const ok = () => on && ac && ac.state === 'running';
  const T = () => ac.currentTime;
  function env(g, t, a, d, v) { g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d); }
  function tone(f, d, o = {}) {
    const t = T() + (o.at || 0), osc = ac.createOscillator(), g = ac.createGain();
    osc.type = o.type || 'sine'; osc.frequency.setValueAtTime(f, t);
    if (o.f2) osc.frequency.exponentialRampToValueAtTime(o.f2, t + d);
    if (o.det) osc.detune.value = o.det;
    let node = osc;
    if (o.lp) { const flt = ac.createBiquadFilter(); flt.type = 'lowpass'; flt.frequency.setValueAtTime(o.lp, t); if (o.lp2) flt.frequency.exponentialRampToValueAtTime(o.lp2, t + (o.a || 0.005) + d * 0.3); osc.connect(flt); node = flt; }
    env(g, t, o.a || 0.005, d, o.v || 0.2); node.connect(g); g.connect(out); osc.start(t); osc.stop(t + (o.a || 0.005) + d + 0.05);
  }
  function noise(d, o = {}) {
    const t = T() + (o.at || 0), src = ac.createBufferSource(), flt = ac.createBiquadFilter(), g = ac.createGain();
    src.buffer = nbuf; flt.type = o.ft || 'bandpass'; flt.Q.value = o.q || 1;
    flt.frequency.setValueAtTime(o.f || 1500, t); if (o.f2) flt.frequency.exponentialRampToValueAtTime(o.f2, t + d);
    env(g, t, o.a || 0.004, d, o.v || 0.3); src.connect(flt); flt.connect(g); g.connect(out);
    src.start(t, Math.random() * 2); src.stop(t + d + 0.1);
  }
  // 裁判哨：豌豆哨的高音 + 很快的颤音（里面的小球在转），带一点气声
  function whistle(at, d, v = 0.12) {
    const t = T() + at, osc = ac.createOscillator(), g = ac.createGain(), trem = ac.createOscillator(), tg = ac.createGain(), vib = ac.createOscillator(), vg = ac.createGain();
    osc.type = 'sine'; osc.frequency.value = 2750;
    vib.frequency.value = 6; vg.gain.value = 25; vib.connect(vg); vg.connect(osc.frequency);
    trem.frequency.value = 32; tg.gain.value = 0.45;
    const am = ac.createGain(); am.gain.value = 0.55; trem.connect(tg); tg.connect(am.gain);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + 0.03); g.gain.setValueAtTime(v, t + d - 0.06); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
    osc.connect(am); am.connect(g); g.connect(out);
    for (const n of [osc, trem, vib]) { n.start(t); n.stop(t + d + 0.05); }
    noise(d, { f: 2900, q: 6, v: v * 0.5, at, a: 0.03 });
  }
  // 铜管号角：锯齿波 + 打开的低通，听起来像短号
  const brass = (f, d, at, v = 0.05) => { tone(f, d, { type: 'sawtooth', at, v, a: 0.04, lp: 500, lp2: 3200 }); tone(f * 1.004, d, { type: 'sawtooth', at, v: v * 0.6, a: 0.05, lp: 400, lp2: 2400 }); };
  let excite = 0, roar = 0, tAcc = 0;
  const API = {
    init, ok,
    get audible() { return on && !!ac && ac.state === 'running'; },
    get on() { return on; },
    set on(v) { on = !!v; if (out) out.gain.value = on ? 0.6 : 0; },
    set onState(f) { onState = f; },
    toggle() { if (!(on && !(ac && ac.state === 'running'))) on = !on; init(); if (out) out.gain.setTargetAtTime(on ? 0.6 : 0, T(), 0.05); return on; },
    // 每帧调用：观众躁动程度、氮气嘶声
    tick(dt, live, ballZ, boosting, playing) {
      if (!ac) return;
      tAcc += dt; if (tAcc < 0.1) return; dt = tAcc; tAcc = 0;      // 音量包络每 0.1 秒更新一次就够了，不用每帧都往音频线程塞自动化事件
      roar = Math.max(0, roar - dt * 0.18);
      const near = Math.max(0, 1 - (D2 - Math.abs(ballZ)) / 22);
      excite += ((playing ? 0.35 + 0.45 * near * near : 0.18) - excite) * Math.min(1, dt * 1.5);
      const lvl = Math.min(1.4, excite + roar * 1.3);
      crowd.g.gain.setTargetAtTime(0.05 + 0.2 * lvl, T(), 0.15);
      crowd.f.forEach((f, k) => f.frequency.setTargetAtTime([420, 900, 1700, 2900][k] * (1 + 0.35 * lvl), T(), 0.2));
      hiss.gain.setTargetAtTime(playing ? 0.035 * Math.min(3, boosting) : 0, T(), 0.06);
    },
    ball(e) {
      if (!ok()) return;
      const s = e.s, now = performance.now();
      if (e.type === 'kick') {                       // 机器人踢球：低频闷响 + 金属"咔"
        if (now - lastKick < 40) return; lastKick = now;
        tone(150, 0.16, { f2: 50, v: 0.25 + 0.35 * s });
        noise(0.05, { f: 1800, q: 1.2, v: 0.15 + 0.25 * s });
        tone(950, 0.06, { type: 'triangle', f2: 420, v: 0.04 + 0.06 * s });
      } else if (e.type === 'wall') {                // 撞玻璃墙：沉闷的"咚" + 墙板共振
        tone(95, 0.3, { f2: 42, v: 0.2 + 0.35 * s });
        noise(0.25, { ft: 'lowpass', f: 900, f2: 200, v: 0.18 + 0.3 * s });
        noise(0.35, { f: 220, q: 9, v: 0.12 + 0.2 * s });
        tone(1650, 0.18, { type: 'sine', v: 0.015 + 0.03 * s, at: 0.01 });
      } else if (e.type === 'net') {                 // 撞网："唰"一声，再带一点网绳抖动的沙沙声
        noise(0.4, { f: 3200, f2: 1200, q: 1.3, v: 0.18 + 0.3 * s, a: 0.01 });
        noise(0.5, { ft: 'highpass', f: 5000, v: 0.05 + 0.08 * s, at: 0.08, a: 0.05 });
        tone(110, 0.2, { f2: 60, v: 0.08 + 0.1 * s });
      } else if (e.type === 'floor' && s > 0.25) {   // 落地弹起
        tone(120, 0.12, { f2: 60, v: 0.08 + 0.18 * s });
        noise(0.06, { ft: 'lowpass', f: 700, v: 0.06 + 0.1 * s });
      }
    },
    pickup() { if (!ok()) return; [1318, 1760, 2349].forEach((f, i) => tone(f, 0.35, { type: 'triangle', v: 0.06, at: i * 0.05 })); noise(0.3, { f: 3000, f2: 8000, q: 2, v: 0.08, a: 0.02 }); },
    kickoff() { if (ok()) whistle(0, 0.75); },
    finalWhistle() { if (!ok()) return; whistle(0, 0.3); whistle(0.42, 0.3); whistle(0.84, 1.1); roar = Math.max(roar, 0.6); },
    goal() {                                          // 进球：号角 + 观众爆发
      if (!ok()) return;
      roar = 1;
      noise(2.6, { ft: 'lowpass', f: 600, f2: 2500, v: 0.22, a: 0.25 });
      noise(1.8, { f: 1400, q: 0.8, v: 0.14, a: 0.15 });
      tone(55, 0.6, { f2: 35, v: 0.4 });
      // 体育场进球号角：三个音的和弦长鸣两次
      for (const at of [0.05, 0.75]) for (const f of [146.8, 185, 220]) tone(f, at ? 1.6 : 0.5, { type: 'sawtooth', at, v: 0.045, a: 0.04, lp: 700, lp2: 1800 });
    },
    swoosh() {                                        // 回放转场：呼啸而过 + 正中间一声冲击
      if (!ok()) return;
      const D = STINGER_MS / 1000;
      noise(D * 0.45, { f: 300, f2: 5000, q: 2.2, v: 0.22, a: D * 0.35 });
      tone(48, 0.7, { f2: 30, v: 0.35, at: D * 0.45 });
      noise(0.5, { ft: 'highpass', f: 3000, f2: 9000, v: 0.12, at: D * 0.45 });
      [1568, 2093, 2637].forEach((f, i) => tone(f, 0.6, { type: 'sine', v: 0.03, at: D * 0.47 + i * 0.04 }));
      noise(D * 0.4, { f: 4500, f2: 400, q: 2.2, v: 0.14, at: D * 0.55, a: 0.05 });
    },
    intro() {                                         // 开场号角：大调上行 + 收尾长和弦
      if (!ok()) { if (on) pendIntro = performance.now(); return; }
      const N = [[293.7, 0], [370, 0.16], [440, 0.32], [587.3, 0.48]];
      N.forEach(([f, at]) => brass(f, 0.18, at));
      for (const f of [293.7, 370, 440, 587.3]) brass(f, 1.3, 0.72, 0.04);
      tone(73.4, 1.5, { type: 'triangle', v: 0.2, at: 0.72 });
      noise(1.2, { ft: 'highpass', f: 6000, v: 0.05, at: 0.72, a: 0.05 });
      roar = Math.max(roar, 0.5);
    },
  };
  return API;
})();
['pointerdown', 'pointerup', 'touchend', 'click', 'keydown'].forEach(ev => addEventListener(ev, () => SND.init(), { passive: true, capture: true }));

// ---------------------------------------------------------------- 播放
const seek = $('seek'); seek.max = F.length - 1;
let pos = 0, playing = false, lastT = performance.now(), goalUntil = -1;
const goalTicks = []; F.forEach((f, i) => { if (f.g !== undefined) goalTicks.push(i); });
function setPlay(v) {
  playing = v; if (v && pos >= F.length - 1) { pos = 0; resetTrail(); }
  $('play').textContent = v ? '⏸ 暂停' : '▶ 播放';
  if (v && pos < 1 && HL.mode === 'live' && !HL.busy) intro();
}
// 从头播放时的开场：AI ARENA 标志闪过 + 号角，标志散去后裁判鸣哨开球
function intro() {
  SND.init(); HL.intro = true; SND.intro();
  stinger('KICK OFF', () => {});
  setTimeout(() => { HL.intro = false; SND.kickoff(); }, STINGER_MS * 0.9);
}
$('play').onclick = () => setPlay(!playing);
seek.oninput = () => { if (HL.mode === 'replay') exitReplayNow(); pos = +seek.value; resetTrail(); };
addEventListener('keydown', e => {
  if (e.code === 'Space') { e.preventDefault(); setPlay(!playing); }
  if (e.code === 'ArrowRight') { pos = Math.min(F.length - 1, Math.floor(pos) + 1); }
  if (e.code === 'ArrowLeft') { pos = Math.max(0, Math.ceil(pos) - 1); resetTrail(); }
});
// ---------------------------------------------------------------- 拍宣传片用：头顶标号开关、纯净画面
let showTags = !(optOff('labels') || optOn('clean'));
function toast(msg) { const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 1600); }
function setTags(v) {
  showTags = v; $('tagBtn').classList.toggle('on', v);
  for (const rb of robots) { rb.label.visible = v; rb.bars.visible = v && M.packs.length > 0; }
}
function setClean(v, quiet) {
  document.body.classList.toggle('clean', v); $('cleanBtn').classList.toggle('on', v);
  if (v) setTags(false);
  resize();
  if (!quiet) toast(v ? '纯净画面：单击播放/暂停，双击或按 H 退出' : '已退出纯净画面');
}
$('tagBtn').onclick = () => setTags(!showTags);
$('cleanBtn').onclick = () => setClean(true);
addEventListener('keydown', e => {
  if (e.code === 'KeyT') setTags(!showTags);
  if (e.code === 'KeyH') setClean(!document.body.classList.contains('clean'));
});
{ // 纯净画面里没有按钮：单击画面播放/暂停（拖动转视角不算），双击退出
  let down = null, tapT = null;
  cv.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY, t: performance.now() }; });
  cv.addEventListener('pointerup', e => {
    if (!down || !document.body.classList.contains('clean')) return;
    const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 8, long = performance.now() - down.t > 300; down = null;
    if (moved || long) return;
    if (tapT) { clearTimeout(tapT); tapT = null; setClean(false); return; }
    tapT = setTimeout(() => { tapT = null; setPlay(!playing); }, 280);
  });
}
setTags(showTags);
$('statsBtn').onclick = () => { const s = $('stats'); s.style.display = s.style.display === 'block' ? 'none' : 'block'; };
const esc = s => String(s).replace(/[<&>]/g, c => ({ '<': '&lt;', '&': '&amp;', '>': '&gt;' })[c]);
$('stats').innerHTML = '<table><tr><th>参赛者</th><th>进球</th><th>超时</th><th>平均</th><th>最长</th><th>崩溃</th></tr>' +
  (R.stats || []).map((s, i) => `<tr><td style="color:${i ? '#fca5a5' : '#86efac'}">${esc(s.name)}</td><td>${R.scores[i]}</td><td>${s.timeouts}</td><td>${s.avg_ms ?? '-'} ms</td><td>${s.max_ms} ms</td><td>${s.crashed ? '是' : '否'}</td></tr>`).join('') + '</table>';

// ---------------------------------------------------------------- 高光回放
// 和电视转播一样：进球后过一会儿，AI ARENA 标志从画面中间闪过（转场），切到慢动作回放（跟随视角、左上角 REPLAY 角标），
// 回放完再闪一次标志回到直播。"高光集锦"按钮把全场进球连起来播一遍。
const RESET_T = M.reset_ticks || 120;
const HL = { t0: 0, mode: 'live', auto: true, rate: 0.5, done: new Set(), queue: [], goal: -1, end: 0, resume: 0, savedCam: 'tv', busy: false, ending: false, reel: false };
const STINGER_MS = 2200;
function stinger(label, mid) {
  const st = $('stinger'); $('stLabel').textContent = label;
  st.classList.remove('run'); void st.offsetWidth; st.classList.add('run'); HL.busy = true; HL.t0 = performance.now();
  setTimeout(mid, STINGER_MS * 0.49); if (label !== 'KICK OFF') SND.swoosh();                      // 色带完全盖住画面的中段切镜头
  setTimeout(() => { st.classList.remove('run'); HL.busy = false; }, STINGER_MS + 80);
}
// 播放速度系数：回放是慢动作；转场时像转播一样先把画面减速，切过去以后再从慢速逐渐提回来
function playRate() {
  if (HL.intro) return 0;
  let f = HL.mode === 'replay' ? HL.rate : 1;
  if (HL.busy) {
    const e = Math.min(1, (performance.now() - HL.t0) / STINGER_MS), ss = x => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
    f *= e < 0.49 ? 1 - 0.8 * ss(e / 0.49) : 0.2 + 0.8 * ss((e - 0.49) / 0.51);
  }
  return f;
}
function goReplay(g) {                                    // 在转场遮住画面时调用
  HL.mode = 'replay'; HL.goal = g; HL.ending = false;
  pos = Math.max(0, g - 4 * M.tps); HL.end = Math.min(F.length - 1, g + Math.round(0.8 * M.tps));
  const k = goalTicks.indexOf(g) + 1, team = F[g].g;
  $('rtagSub').textContent = `${R.bots[team]} 进球` + (HL.reel ? ` · ${k}/${goalTicks.length}` : '');
  $('rtag').classList.add('show'); resetTrail(); setCam('follow'); cam.pitch = 0.34; cam.dist = 24;
}
function startReplay(g) {
  if (HL.busy) return;
  if (HL.mode !== 'replay') HL.savedCam = cam.mode === 'free' ? 'tv' : cam.mode;
  stinger('REPLAY', () => goReplay(g));
}
function backToLive() {
  HL.mode = 'live'; HL.reel = false; $('rtag').classList.remove('show');
  pos = HL.resume; resetTrail(); setCam(HL.savedCam);
}
function exitReplayNow() { HL.queue = []; if (HL.mode === 'replay') backToLive(); }
function highlightTick() {
  if (HL.busy) return;
  const i = Math.floor(pos);
  if (HL.mode === 'replay') {
    if (!HL.ending && pos >= HL.end) {
      HL.ending = true;
      const next = HL.queue.shift();
      stinger(next === undefined ? 'LIVE' : 'REPLAY', () => next === undefined ? backToLive() : goReplay(next));
    }
    return;
  }
  if (!HL.auto || !playing) return;
  for (const g of goalTicks) {                             // 进球庆祝 1.5 秒后自动回放
    if (!HL.done.has(g) && i >= g + 1.5 * M.tps && i < g + RESET_T) {
      HL.done.add(g); HL.resume = Math.min(F.length - 1, g + RESET_T + 1); HL.reel = false;
      startReplay(g); break;
    }
  }
}
$('hlBtn').onclick = () => {
  if (!goalTicks.length) { $('hlBtn').textContent = '本场没有进球'; return; }
  if (HL.mode !== 'replay') HL.resume = pos;
  HL.reel = true; HL.queue = goalTicks.slice(1); startReplay(goalTicks[0]); setPlay(true);
};
$('autoRp').onclick = () => { HL.auto = !HL.auto; $('autoRp').classList.toggle('on', HL.auto); };
// 按钮显示真实状态：开着但浏览器还没放行时提示"轻点开声"，而不是假装已经有声音
function sndLabel() { const b = $('sndBtn'); b.classList.toggle('on', SND.on); b.textContent = !SND.on ? '🔇 静音' : SND.audible ? '🔊 音效' : '🔈 轻点开声'; }
SND.onState = sndLabel; sndLabel();
$('sndBtn').onclick = () => { SND.toggle(); sndLabel(); };
window.__replay = startReplay;

// 球撞墙反馈：从回放帧里找出"球的速度突然改变、附近又没有机器人、也不是落地"的时刻，即球撞到了墙、
// 天花板、角落或门框。播放到这些时刻时，在撞击点沿墙面扩散两道光圈并闪一下，撞得越重越大越亮。
const wallHits = new Map();
function wallDist(x, y, z) {  // 点到最近的墙面 / 天花板 / 门框的近似距离（不含地面）
  const ax = Math.abs(x), az = Math.abs(z);
  let d = Math.min(H - y, W2 - ax);
  if (az > D2) d = Math.min(d, GW2 - ax, GH - y, D2 + GD - az);                     // 球门里面
  else if (ax > GW2 || y > GH) d = Math.min(d, D2 - az);                             // 底线墙
  if (ax > W2 - CR && az > D2 - CR) d = Math.min(d, CR - Math.hypot(ax - (W2 - CR), az - (D2 - CR)));  // 四角
  const gs = A.goal_side_radius;
  d = Math.min(d, Math.hypot(ax - GW2 - gs, az - D2 - gs) - gs, Math.hypot(y - GH - gs, az - D2 - gs) - gs);  // 门柱、横梁
  return d;
}
{
  const BR = M.ball_radius, near = BR + M.robot_radius * 1.05 + 2;
  let skip = -1;
  for (let i = 2; i + 2 < F.length; i++) {
    if (i <= skip) continue;
    const a = F[i - 2].b, b = F[i].b, c = F[i + 2].b;
    if (Math.hypot(c[0] - a[0], c[2] - a[2]) > 16) continue;          // 进球后重新开球的瞬移
    const dv = [(c[0] - b[0]) - (b[0] - a[0]), (c[1] - b[1]) - (b[1] - a[1]) + 2 * 30 / M.tps / M.tps * 2, (c[2] - b[2]) - (b[2] - a[2])];
    const mag = Math.hypot(...dv) / 2;                                  // 每 tick 的速度变化
    if (mag < 0.3) continue;
    const n = dv.map(v => v / (mag * 2));
    if (n[1] > 0.7) continue;                                           // 地面反弹不算
    if (wallDist(b[0], b[1], b[2]) - BR > 1.5) continue;                 // 离墙太远（多半是被机器人撞的）
    let hitByRobot = false;
    for (let j = i - 3; j <= i + 3 && !hitByRobot; j++) { const fb = F[Math.max(0, Math.min(F.length - 1, j))];
      hitByRobot = fb.r.some(r => Math.hypot(r[0] - fb.b[0], r[1] - fb.b[1], r[2] - fb.b[2]) < near); }
    if (hitByRobot) continue;
    // 精确到撞击的那一帧：速度方向变化最大的一帧
    let hi = i, best = -1;
    for (let j = i - 1; j <= i + 1; j++) {
      const p = F[j - 1].b, q = F[j].b, r = F[j + 1].b;
      const d = Math.hypot((r[0] - q[0]) - (q[0] - p[0]), (r[1] - q[1]) - (q[1] - p[1]), (r[2] - q[2]) - (q[2] - p[2]));
      if (d > best) { best = d; hi = j; }
    }
    const pb = F[hi].b;
    wallHits.set(hi, { p: [pb[0] - n[0] * BR, pb[1] - n[1] * BR, pb[2] - n[2] * BR], n, s: Math.min(1, mag / 1.1) });
    skip = i + 8;
  }
}
// 球的所有碰撞事件（音效和球网用）：被机器人踢、撞墙、撞网、落地
// 只算真正的"弹开"：球朝着墙面（或地面）的法向速度够大，并且碰后反向离开；贴着弯墙滚动、蹭着墙走都不算。
// 同一类碰撞 0.25 秒内只保留最重的一次，所以一次撞墙只响一声。
const ballEv = new Map();
{
  const BR = M.ball_radius, near = BR + M.robot_radius * 1.05 + 1.5, G = 30 / M.tps / M.tps, MERGE = Math.round(0.25 * M.tps);
  const last = { kick: -99, surf: -99 };              // 落地和撞墙算同一类：球砸在墙脚时只响一声
  const put = (cls, i, e, gap) => {                                  // 同类事件靠得太近时只留最重的
    if (i - last[cls] < gap) { const o = ballEv.get(last[cls]); if (!o || o.s >= e.s) return; ballEv.delete(last[cls]); }
    ballEv.set(i, e); last[cls] = i;
  };
  const wallN = (x, y, z) => {                                       // 墙面法线（指向场内）：wallDist 的梯度
    const h = 0.05, d0 = wallDist(x, y, z);
    const g = [wallDist(x + h, y, z) - d0, wallDist(x, y + h, z) - d0, wallDist(x, y, z + h) - d0], l = Math.hypot(...g) || 1;
    return g.map(v => v / l);
  };
  for (let i = 1; i + 1 < F.length; i++) {
    const a = F[i - 1].b, b = F[i].b, c = F[i + 1].b;
    if (Math.hypot(c[0] - a[0], c[2] - a[2]) > 16) continue;          // 进球后重新开球的瞬移
    const v0 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v1 = [c[0] - b[0], c[1] - b[1] + G, c[2] - b[2]];
    const dv = Math.hypot(v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]);
    if (dv < 0.1) continue;
    let kick = false;
    for (let j = i - 1; j <= i + 1 && !kick; j++) { const fb = F[j];
      kick = fb.r.some(r => Math.hypot(r[0] - fb.b[0], r[1] - fb.b[1], r[2] - fb.b[2]) < near); }
    if (kick) { put('kick', i, { type: 'kick', s: Math.min(1, dv / 1.4), p: b }, 6); continue; }
    if (b[1] < BR + 0.6) {                                          // 落地：向下砸下来再弹起
      const vin = -v0[1], vout = v1[1];
      if (vin > 0.12 && vout > 0.02) put('surf', i, { type: 'floor', s: Math.min(1, (vin + vout) / 1.4), p: [b[0], 0, b[2]] }, MERGE);
      continue;
    }
    if (wallDist(b[0], b[1], b[2]) - BR > 1.2) continue;
    const n = wallN(b[0], b[1], b[2]), vin = -(v0[0] * n[0] + v0[1] * n[1] + v0[2] * n[2]), vout = v1[0] * n[0] + v1[1] * n[1] + v1[2] * n[2];
    if (vin < 0.1 || vout < 0.02) continue;                          // 没有朝墙撞过去或没有弹开：贴墙滚动
    const type = Math.abs(b[2]) > D2 + 0.3 && Math.abs(b[0]) < GW2 + 0.5 && b[1] < GH + 0.5 ? 'net' : 'wall';
    put('surf', i, { type, s: Math.min(1, (vin + vout) / 1.4), p: [b[0] - n[0] * BR, b[1] - n[1] * BR, b[2] - n[2] * BR] }, MERGE);
  }
}
let evLastI = -1;
function ballEvents(i0) {
  if (playing && i0 > evLastI && i0 - evLastI < 30) for (let i = evLastI + 1; i <= i0; i++) {
    if (i > 0 && Math.hypot(F[i].b[0] - F[i - 1].b[0], F[i].b[2] - F[i - 1].b[2]) > 8 && HL.mode !== 'replay') SND.kickoff();   // 进球后重新开球
    const e = ballEv.get(i); if (!e) continue;
    if (e.type === 'net') netImpulse(e.p, 0.35 + 0.65 * e.s);
    SND.ball(e);
  }
  evLastI = i0;
}
const ringTex = canvasTex(128, 128, (g, w, h) => {
  const gr = g.createRadialGradient(64, 64, 40, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.55, 'rgba(255,255,255,1)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, w, h);
});
const fxPool = [];
for (let i = 0; i < 10; i++) {
  const mk = (color) => new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: ringTex, color, transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  const grp = new THREE.Group(), r1 = mk(0x7dd3fc), r2 = mk(0xffffff);
  const flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: softTex, color: 0xbfe9ff, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0 }));
  grp.add(r1, r2); scene.add(grp, flash); grp.visible = flash.visible = false;
  fxPool.push({ grp, r1, r2, flash, t: 9, s: 1 });
}
let fxNext = 0, fxLastI = -1;
const zAxis = new THREE.Vector3(0, 0, 1);
function spawnWallFx(h) {
  if (Math.abs(h.p[2]) > D2 + 0.3) return;                         // 撞到球网的不画光圈，由球网鼓包来表现
  const fx = fxPool[fxNext]; fxNext = (fxNext + 1) % fxPool.length;
  fx.t = 0; fx.s = 0.45 + 0.55 * h.s;
  fx.grp.position.set(h.p[0] + h.n[0] * 0.08, h.p[1] + h.n[1] * 0.08, h.p[2] + h.n[2] * 0.08);
  fx.grp.quaternion.setFromUnitVectors(zAxis, new THREE.Vector3(h.n[0], h.n[1], h.n[2]));
  fx.flash.position.set(h.p[0] + h.n[0] * 0.6, h.p[1] + h.n[1] * 0.6, h.p[2] + h.n[2] * 0.6);
  fx.grp.visible = fx.flash.visible = true;
  if (h.s > 0.75 && HL.mode !== 'replay') shake = Math.max(shake, 0.35 * h.s);
}
function wallFx(i0, dt) {
  if (playing && i0 > fxLastI && i0 - fxLastI < 30) for (let i = fxLastI + 1; i <= i0; i++) { const h = wallHits.get(i); if (h) spawnWallFx(h); }
  fxLastI = i0;
  const rt = CAP.on ? CAP.simDt : dt * (playing ? Math.max(0.35, playRate()) : 0);   // 慢动作回放时特效也放慢
  for (const fx of fxPool) {
    if (!fx.grp.visible) continue;
    fx.t += rt;
    const k = fx.t / 0.7;                                          // 0.7 秒内扩散并消失
    if (k >= 1) { fx.grp.visible = fx.flash.visible = false; continue; }
    const e = 1 - Math.pow(1 - k, 3);
    const s1 = (2 + 9 * e) * fx.s, s2 = (1.5 + 6 * Math.max(0, (k - 0.12) / 0.88)) * fx.s;
    fx.r1.scale.set(s1, s1, 1); fx.r2.scale.set(s2, s2, 1);
    fx.r1.material.opacity = 0.9 * (1 - k) * fx.s; fx.r2.material.opacity = 0.7 * Math.max(0, 1 - k * 1.4) * fx.s;
    const fk = Math.max(0, 1 - k * 3.5);
    fx.flash.material.opacity = fk * fx.s; fx.flash.scale.setScalar((3 + 4 * k) * fx.s);
  }
}

const lerp = (a, b, t) => a + (b - a) * t;
const lp = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const trailPts = []; function resetTrail() { fxLastI = evLastI = Math.floor(pos); resetNets(); trailPts.length = 0; robots.forEach(r => r.last = null); lastBall = null; }
let lastBall = null;
const q = new THREE.Quaternion(), axis = new THREE.Vector3();

function update(dt) {
  if (playing && !CAP.on) { pos += dt * M.tps * parseFloat($('speed').value) * playRate(); if (pos >= F.length - 1) { pos = F.length - 1; if (HL.mode !== 'replay') { setPlay(false); SND.finalWhistle(); } } }
  highlightTick();
  const i0 = Math.floor(pos), i1 = Math.min(F.length - 1, i0 + 1), t = pos - i0;
  const f0 = F[i0], f1 = F[i1];
  // 进球后重置的那一帧不要插值
  const jump = Math.hypot(f1.b[0] - f0.b[0], f1.b[2] - f0.b[2]) > 8;
  const tt = jump ? 0 : t;
  const bp = lp(f0.b, f1.b, tt);
  ball.position.set(bp[0], bp[1], bp[2]);
  if (lastBall) {  // 按位移让球滚动
    const dx = bp[0] - lastBall[0], dz = bp[2] - lastBall[2], d = Math.hypot(dx, dz);
    if (d > 1e-4 && d < 5) { axis.set(dz, 0, -dx).normalize(); q.setFromAxisAngle(axis, d / M.ball_radius); ball.quaternion.premultiply(q); }
  }
  lastBall = bp;
  if (playing) { trailPts.unshift(bp); if (trailPts.length > TRAIL) trailPts.pop(); }
  const arr = trailGeo.attributes.position.array;
  for (let k = 0; k < TRAIL; k++) { const p = trailPts[Math.min(k, trailPts.length - 1)] || bp; arr[k * 3] = p[0]; arr[k * 3 + 1] = p[1]; arr[k * 3 + 2] = p[2]; }
  trailGeo.attributes.position.needsUpdate = true; trailGeo.computeBoundingSphere();
  marker.position.set(bp[0], 0.03, bp[2]); const hgt = bp[1] - M.ball_radius;
  marker.material.opacity = Math.max(0, 0.45 - hgt * 0.02); marker.scale.setScalar(1 + hgt * 0.06);

  const simDt = CAP.on ? CAP.simDt : playing ? dt * parseFloat($('speed').value) * playRate() : 0;
  f0.r.forEach((r0, k) => {
    const rb = robots[k], r1 = f1.r[k], p = lp(r0, r1, tt);
    rb.grp.position.set(p[0], p[1], p[2]);
    // 用前后几帧的位置估计速度，决定朝向、前倾和步伐
    // 速度用前后 4 帧估计，并在相邻两帧之间插值，避免每个 tick 跳一下；朝向、前倾和手脚姿势都平滑过渡
    const vel = j => { const ia = Math.max(0, j - 4), ib = Math.min(F.length - 1, j + 4), fa = F[ia].r[k], fb = F[ib].r[k], span = Math.max(1, ib - ia) / M.tps;
      const v = [(fb[0] - fa[0]) / span, (fb[1] - fa[1]) / span, (fb[2] - fa[2]) / span]; return Math.hypot(...v) > 80 ? [0, 0, 0] : v; };   // 进球后重置的瞬移
    const va = vel(i0), vb = vel(i1), vx = lerp(va[0], vb[0], tt), vy = lerp(va[1], vb[1], tt), vz = lerp(va[2], vb[2], tt);
    const hs = Math.hypot(vx, vz), ease = r => 1 - Math.exp(-dt * r);
    if (hs > 3) {
      const want = Math.atan2(vx, vz);
      if (rb.last === null) rb.yaw = want;
      else { const d = Math.atan2(Math.sin(want - rb.yaw), Math.cos(want - rb.yaw)); rb.yaw += d * ease(8); }
    }
    rb.last = p;
    rb.yawG.rotation.y = rb.yaw;
    const air = p[1] > M.robot_radius + 0.3;
    rb.phase += simDt * Math.min(hs, 30) * 0.45;      // 步频约 2 步/秒（满速），比原来慢一半，看起来不会抽搐
    const sw = Math.sin(rb.phase), amp = Math.min(0.7, hs * 0.035), P = rb.pose || (rb.pose = [0, 0, 0, 0, 0]);
    const tgt = air ? [-0.15, -0.6, -0.2, -2.4, -2.4] : [Math.min(0.28, hs * 0.011), sw * amp, -sw * amp, -sw * amp * 0.8, sw * amp * 0.8];
    const e = ease(air ? 10 : 18); for (let q = 0; q < 5; q++) P[q] += (tgt[q] - P[q]) * e;
    rb.body.rotation.x = P[0];
    rb.legs[0].rotation.x = P[1]; rb.legs[1].rotation.x = P[2];
    rb.arms[0].rotation.x = P[3]; rb.arms[1].rotation.x = P[4];
    // 氮气
    const boost = !!r0[4], nit = Math.max(0, Math.min(1, r0[3] / 100));
    rb.barFg.scale.x = 2.2 * nit;
    rb.flame.visible = rb.glow.visible = boost;
    rb.metal.emissiveIntensity = boost ? 0.06 : 0;
    rb.cap.material.color.setHex(boost ? 0xfff1c1 : 0x1a1d24);
    if (boost) {
      rb.flame.scale.set(1, 0.8 + Math.random() * 0.5, 1);
      rb.glow.scale.setScalar(3.4 + Math.random() * 0.8);
      if (simDt > 0) {
        rb.cap.getWorldPosition(tmpV);
        const bx = -Math.sin(rb.yaw), bz = -Math.cos(rb.yaw), n = Math.min(6, Math.ceil(simDt * 110));
        for (let e = 0; e < n; e++) {
          const r = () => (Math.random() - 0.5) * 2;
          emitSpark([tmpV.x + r() * 0.15, tmpV.y + r() * 0.15, tmpV.z + r() * 0.15],
            [vx * 0.25 + bx * 13 + r() * 3, vy * 0.25 + r() * 3, vz * 0.25 + bz * 13 + r() * 3], 0.35 + Math.random() * 0.3);
        }
      }
    }
  });
  stepSparks(simDt);
  if (adTex) adTex.offset.x = (adTex.offset.x + dt * 0.02) % 1;
  holoT += dt; holoU.uTime.value = airU.uTime.value = holoT % 1000;
  wallFx(i0, dt);
  ballEvents(i0);
  SND.tick(dt, HL.mode, bp[2], f0.r.reduce((n, r) => n + (r[4] ? 1 : 0), 0), playing && !HL.intro);
  const push = stepNets(simDt, bp);
  ball.position.set(bp[0] + push[0], bp[1] + push[1], bp[2] + push[2]);
  packs.forEach((pk, k) => {
    const alive = !f0.n || !!f0.n[k];
    pk.bottle.visible = pk.halo.visible = alive;
    pk.bottle.position.y = 0.15 * Math.sin((CAP.on ? CAP.t * 1000 : performance.now()) / 500 + k);
    pk.bottle.rotation.y += dt * 0.9;
    pk.pad.material.opacity = alive ? 0.5 : 0.15;
    pk.ring.visible = !alive;
    if (!alive) setRing(pk, pk.dead[i0] >= 0 ? (f0.t - pk.dead[i0]) / PACK_RESPAWN : 0);
    if (pk.prev === true && !alive && playing) { pk.flash = 1; SND.pickup(); }  // 被吃掉的瞬间闪一下
    pk.prev = alive;
    pk.burst.visible = pk.flash > 0;
    if (pk.flash > 0) { pk.flash -= dt * 2.2; const s = 2 + (1 - pk.flash) * 8; pk.burst.scale.set(s, s, 1); pk.burst.material.opacity = Math.max(0, pk.flash); }
  });

  // 进球效果
  const recent = goalTicks.filter(g => g <= i0 && i0 - g < (HL.mode === 'replay' ? 60 : 150)).pop();
  if (recent !== undefined) {
    const team = F[recent].g;
    if (goalUntil !== recent) {
      goalUntil = recent; shake = playing && HL.mode !== 'replay' ? 1.6 : 0;
      if (playing && HL.mode !== 'replay' && i0 - recent < 10) SND.goal();
      $('goal').innerHTML = `<span style="color:${team ? '#f87171' : '#4ade80'}">GOAL!</span><small>${esc(R.bots[team])}</small>`;
    }
    $('goal').classList.toggle('show', HL.mode !== 'replay');
    const g = goals[team === 0 ? 1 : 0], k = Math.max(0, 1 - (i0 - recent) / 150);
    g.glow.intensity = 3 * k; g.nets.forEach(n => n.material.emissiveIntensity = 0.15 + 1.2 * k);
  } else {
    $('goal').classList.remove('show'); goalUntil = -1;
    goals.forEach(g => { g.glow.intensity = 0; g.nets.forEach(n => n.material.emissiveIntensity = 0.15); });
  }

  $('sc').textContent = f0.s[0] + ' : ' + f0.s[1];
  const sec = f0.t / M.tps;
  $('clock').textContent = `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;
  $('tick').textContent = `tick ${f0.t} / ${M.ticks}`;
  if (document.activeElement !== seek) seek.value = i0;
  placeCamera(ball.position, dt);
}

function resize() {
  const w = FIXED ? CAPW : innerWidth, h = FIXED ? CAPH : innerHeight;
  renderer.setSize(w, h, FIXED); camera.aspect = w / h;   // 固定分辨率时画布就是 w×h 像素，不跟窗口走
  camera.fov = w < h ? 62 : 45; camera.updateProjectionMatrix();
  measureHud();
  if (cam.mode !== 'follow' && cam.mode !== 'free') setCam(cam.mode);   // 转屏或改窗口大小后重新取景
}
addEventListener('resize', resize); resize();
if (optOn('clean')) setClean(true, true);
if (window.ResizeObserver) new ResizeObserver(() => resize()).observe(document.querySelector('.bottom'));
setCam('tv');
// 自动降画质：持续掉到 40 帧以下时，先逐步降低渲染分辨率，还不够再关掉实时阴影（球下面的影子圆盘还在）
const perf = { ema: 1 / 60, t: 0, level: 0 };
function autoQuality(raw) {
  if (raw > 0.25 || document.hidden) return;                       // 切后台回来的那一帧不算
  perf.ema += (raw - perf.ema) * 0.05; perf.t += raw;
  if (perf.t < 3 || perf.ema < 1 / 40) return;
  perf.t = 0;
  if (PR > 1) { PR = Math.max(1, PR - 0.25); renderer.setPixelRatio(PR); resize(); }
  else if (sun.castShadow) { sun.castShadow = false; renderer.shadowMap.enabled = false; scene.traverse(o => { if (o.material) o.material.needsUpdate = true; }); }
}
function frame(now) {
  const raw = (now - lastT) / 1000, dt = Math.min(0.1, raw); lastT = now;
  if (!CAP.on) {                                     // 逐帧截图时由 arenaCapture.render() 出图，这里不动画面
    if (playing && !FIXED) autoQuality(raw);
    update(dt); renderer.render(scene, camera);
  }
  requestAnimationFrame(frame);
}
// ---------------------------------------------------------------- 逐帧截图接口（拍宣传片用，用法见 README）
// 无头浏览器按固定帧率一帧一帧地 seek + render + 截图：不播声音、不自动进球回放、不自动降画质，随机数固定种子，
// 同一串调用每次出来的画面都一样。相邻两帧回放时间跳得太多（往回跳或超过 0.25 秒）算切镜头，拖尾、球网、姿势等直接复位。
const CAP = { on: false, simDt: 0, t: 0, last: null, cam: null };
function capBegin() {
  if (CAP.on) return;
  CAP.on = true; exitReplayNow(); HL.auto = false; HL.intro = false; HL.queue = [];
  SND.on = false; setClean(true, true); playing = true;
  // 开始截图前页面已经实时跑过一阵，把和"跑了多久"有关的状态清零，保证每次结果一样
  CAP.t = 0; holoT = 0; shake = 0; ball.quaternion.identity(); if (adTex) adTex.offset.x = 0;
  packs.forEach(pk => { pk.bottle.rotation.y = 0; pk.flash = 0; }); robots.forEach(rb => { rb.phase = 0; rb.pose = null; });
  Math.random = seededRandom(0x2f6b9c1d);            // 截图开始时重新播种，火花等特效也一样
}
window.arenaCapture = {
  ticks: F.length, tps: M.tps, fps: +OPT.get('fps') || 60,
  goals: goalTicks.slice(),                          // 每个进球所在的 tick
  field: { width: A.width, depth: A.depth, height: A.height, goal_width: A.goal_width, goal_height: A.goal_height, goal_depth: A.goal_depth, greenGoalZ: -D2, redGoalZ: D2 },
  seek(tick, frac = 0) { capBegin(); pos = Math.max(0, Math.min(F.length - 1, tick + frac)); },
  render() {
    capBegin();
    const dt = 1 / this.fps, cut = CAP.last === null || pos < CAP.last || pos - CAP.last > 0.25 * M.tps;
    if (cut) { resetTrail(); stepSparks(5); fxPool.forEach(fx => fx.grp.visible = fx.flash.visible = false); CAP.simDt = 0; for (let k = 0; k < 4; k++) update(1); }   // 镜头和姿势的缓动直接到位
    CAP.simDt = cut ? 0 : (pos - CAP.last) / M.tps; CAP.t += dt;
    update(dt);
    if (CAP.cam) {
      const [p, t, fov] = CAP.cam;
      camera.position.set(p[0], p[1], p[2]); camera.up.set(0, 1, 0); camera.lookAt(t[0], t[1], t[2]);
      if (fov) camera.fov = fov; camera.updateProjectionMatrix();
    }
    renderer.render(scene, camera); CAP.last = pos;
  },
  camera(pos3, target, fov) { CAP.cam = pos3 ? [pos3, target, fov] : null; if (!pos3) resize(); },   // 传 null 回到内置镜头
  preset(name) { CAP.cam = null; setCam(name); },  // 内置镜头：tv / follow / top / goalA / goalB
  state() {
    const i = Math.floor(pos), f = F[i];
    return { tick: pos, score: f.s.slice(), ball: ball.position.toArray(),
      robots: robots.map((rb, k) => ({ team: rb.team ? 'red' : 'green', num: rb.idx + 1, pos: rb.grp.position.toArray(), yaw: rb.yaw, boost: !!f.r[k][4] })),
      camera: { pos: camera.position.toArray(), fov: camera.fov } };
  },
  dataURL(type = 'image/png', q) { return cv.toDataURL(type, q); },   // 紧接着 render() 在同一次调用里取
  stop() { if (!CAP.on) return; CAP.on = false; CAP.cam = null; playing = false; CAP.last = null; setPlay(false); resize(); },
};
window.__seek = p => { exitReplayNow(); pos = Math.max(0, Math.min(F.length - 1, p)); resetTrail(); };
requestAnimationFrame(frame);
</script>
</body>
</html>
"""


def render(replay: dict) -> str:
    title = f"{replay['bots'][0]} vs {replay['bots'][1]}"
    data = json.dumps(replay, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    with open(os.path.join(VENDOR, "three.min.js"), encoding="utf-8") as f:
        three = f.read().replace("</script", "<\\/script")
    with open(os.path.join(ASSETS, "doubao.webp"), "rb") as f:
        doubao = "data:image/webp;base64," + base64.b64encode(f.read()).decode()
    with open(os.path.join(ASSETS, "holo_atlas.webp"), "rb") as f:
        holo = "data:image/webp;base64," + base64.b64encode(f.read()).decode()
    return (TEMPLATE.replace("__TITLE__", html.escape(title))
            .replace("__DOUBAO__", doubao)
            .replace("__HOLO__", holo)
            .replace("__REPLAY__", data)
            .replace("<script>__THREE__</script>", "<script>" + three + "</script>"))
