'use strict';
// 八方旅人风格对决回放。所有美术（像素角色、场景、图标）都在这里用代码现场绘制，原创，不使用原作素材。
const R = window.__REPLAY__;
const M = R.meta, F = R.frames;
const TR = M.travelers, SKN = M.skills;
// 赛前配置（旧回放没有这些字段）：副职、支援技能、每人实际的最大 HP/SP
const LOS = M.loadouts || [[], []], SUPN = M.supports || {}, JOBZ = M.jobs_zh || {}, ITN = M.items || {}, BAGS = M.bags || [{}, {}];
const MAXHS = (t, i) => (M.unit_max && M.unit_max[t] && M.unit_max[t][i]) || [TR[M.picks[t][i]].hp, TR[M.picks[t][i]].sp];
const LW = 480, LH = 270, SC = 3, W = LW * SC, H = LH * SC;
// 镜头：从低分辨率画布里取 400×225 的区域放大（拉近角色）
const CAM = { x: 40, y: 34, w: 400, h: 225 }, Z = W / CAM.w;
function toScr(x, y) { return [(x - CAM.x) * Z, (y - CAM.y) * Z]; }
const TEAM_COL = ['#5aa9ff', '#ff6b6b'];
const TYPE_COL = { sword: '#c9d2de', polearm: '#c9b48a', dagger: '#b9c7d6', axe: '#d0a070', bow: '#a8d07a', staff: '#c79ad8',
  fire: '#ff7a3a', ice: '#7fe3ff', lightning: '#ffe34a', wind: '#7af0a0', light: '#fff2a8', dark: '#a070ff' };
const TYPE_ZH = M.type_zh;
const POSITIVE_ST = ['counter', 'sidestep', 'sacred', 'regen', 'immune', 'taunt', 'extra', 'spread', 'charity'];
const STAT_ZH = { pa: '物攻', pd: '物防', ea: '属攻', ed: '属防', spd: '速度', crit: '暴击', acc: '命中', eva: '回避' };
const STATUS_ZH = { poison: '中毒', poison_weak: '弱毒', immune: '免疫', taunt: '挑衅', counter: '反击', sidestep: '闪避',
  sacred: '圣盾', regen: '再生', leghold: '捕兽夹', extra: '祝福', spread: '魅惑', charity: '慈悲', ward: '预防药' };

const cv = document.getElementById('cv');
cv.width = W; cv.height = H;
const QS = new URLSearchParams(location.search);
const CLEAN = QS.get('clean') === '1';
const FIXED = +QS.get('w') > 0 && +QS.get('h') > 0;
// 录制时所有画布都固定用软件渲染：GPU 画布之间互相取图时结果会有细微差别，同一帧就画不成一模一样
if (CLEAN || FIXED) { const gc = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (t, o) { return gc.call(this, t, t === '2d' ? { willReadFrequently: true, ...(o || {}) } : o); }; }
const ctx = cv.getContext('2d');

// ------------------------------------------------------------------ 录制模式（宣传片用；不带参数时与普通回放完全一样）
// ?clean=1 去掉所有界面，只留场景、技能特写、伤害数字和破防/增幅等特效；?w=3840&h=2160 指定输出分辨率；?fps=60
// window.arenaCapture 提供逐帧确定性渲染（见文件末尾）
const CAP = { on: false, fps: Math.max(1, +QS.get('fps') || 60) };
let OW = W, OH = H, VIEW = { z: 1, cx: W / 2, cy: H / 2 };
let rng = Math.random; // 伤害数字的随机偏移；录制时换成固定种子
function outSize() {
  if (FIXED) { OW = Math.min(8192, Math.round(+QS.get('w'))); OH = Math.min(8192, Math.round(+QS.get('h'))); }
  else if (CLEAN) { const d = window.devicePixelRatio || 1; OW = Math.max(16, Math.round(innerWidth * d)); OH = Math.max(16, Math.round(innerHeight * d)); }
  else { OW = W; OH = H; }
  if (cv.width !== OW) cv.width = OW;
  if (cv.height !== OH) cv.height = OH;
}
// 场景变换：横屏铺满（16:9 时正好是原画面），竖屏取中间 60% 宽度并按 VIEW 推近
function worldXf() {
  const s = (OW >= OH ? Math.max(OW / W, OH / H) : OW / (W * 0.6)) * VIEW.z;
  const hw = OW / 2 / s, hh = OH / 2 / s;
  const cx = hw * 2 >= W ? W / 2 : Math.min(W - hw, Math.max(hw, VIEW.cx));
  const cy = hh * 2 >= H ? H / 2 : Math.min(H - hh, Math.max(hh, VIEW.cy));
  return [s, OW / 2 - cx * s, OH / 2 - cy * s];
}
// 叠加层（技能特写、大字）：不跟着推近，竖屏时按 75% 宽度排版
function overlayXf() {
  const s = OW >= OH ? Math.min(OW / W, OH / H) : OW / (W * 0.75);
  return [s, OW / 2 - W / 2 * s, OH / 2 - H / 2 * s];
}
let VR = { x: 0, y: 0, w: W, h: H }; // 叠加层坐标里可见的区域
function useWorld() { const [s, x, y] = worldXf(); ctx.setTransform(s, 0, 0, s, x, y); }
function useOverlay() { const [s, x, y] = overlayXf(); ctx.setTransform(s, 0, 0, s, x, y); VR = { x: -x / s, y: -y / s, w: OW / s, h: OH / s }; }
function mk(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
// 场景画布放大 3 倍：背景仍是 480×270 的像素画，角色用高精度像素立绘
const ART_SCALE = 3;
const low = mk(LW * ART_SCALE, LH * ART_SCALE), lx = low.getContext('2d');
lx.scale(ART_SCALE, ART_SCALE); lx.imageSmoothingEnabled = false;

// ------------------------------------------------------------------ 颜色工具
function hex2rgb(h) { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.substr(i, 2), 16)); }
function rgb2hex(r) { return '#' + r.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join(''); }
function shade(h, f) { const c = hex2rgb(h); return rgb2hex(c.map(v => f >= 0 ? v + (255 - v) * f : v * (1 + f))); }
function mix(a, b, t) { const x = hex2rgb(a), y = hex2rgb(b); return rgb2hex(x.map((v, i) => v + (y[i] - v) * t)); }
function hash(n) { n = (n << 13) ^ n; return 1 - ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7fffffff) / 1073741824; }
function rnd(i) { return (hash(i) + 1) / 2; }

// ------------------------------------------------------------------ 像素角色生成
class Grid {
  constructor(w, h, ox = 0) { this.w = w; this.h = h; this.ox = ox; this.c = new Array(w * h).fill(null); }
  px(x, y, col) { x = (x + this.ox) | 0; y |= 0; if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.c[y * this.w + x] = col; }
  get(x, y) { return (x < 0 || y < 0 || x >= this.w || y >= this.h) ? null : this.c[y * this.w + x]; }
  rect(x, y, w, h, col) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this.px(x + i, y + j, col); }
  block(x, y, w, h, col) {
    this.rect(x, y, w, h, col);
    if (w > 2) for (let j = 0; j < h; j++) { this.px(x, y + j, shade(col, 0.16)); this.px(x + w - 1, y + j, shade(col, -0.3)); }
    if (h > 2) for (let i = 1; i < w - 1; i++) this.px(x + i, y + h - 1, shade(col, -0.25));
  }
  line(x0, y0, x1, y1, col) {
    const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) || 1;
    for (let i = 0; i <= n; i++) this.px(Math.round(x0 + (x1 - x0) * i / n), Math.round(y0 + (y1 - y0) * i / n), col);
  }
}

// 外观按原作公开的角色设定（发型、服色、配饰、武器）用像素重新绘制，不使用原作素材。
const OUTLINE = '#1a1222';
const SPR_W = 64, SPR_H = 64, GROUND = 61, SPR_PAD = 8; // 左右各留 8 像素给武器
Grid.prototype.poly = function (pts, col) {
  const ys = pts.map(p => p[1]);
  const y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys));
  for (let y = y0; y <= y1; y++) {
    const xs = [], yc = y + 0.5;
    for (let i = 0; i < pts.length; i++) {
      const [ax, ay] = pts[i], [bx, by] = pts[(i + 1) % pts.length];
      if ((ay <= yc && by > yc) || (by <= yc && ay > yc)) xs.push(ax + (yc - ay) * (bx - ax) / (by - ay));
    }
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) for (let x = Math.round(xs[k]); x < Math.round(xs[k + 1]); x++) this.px(x, y, col);
  }
};

// 每个角色一个绘制函数；S 提供姿势相关的坐标
function poseCtx(pose, f, short, wp) {
  const kneel = pose === 'kneel';
  const by = (pose === 'idle' && f) ? 1 : 0, dn = kneel ? 8 : 0, sh = short || 0;
  const S = { pose, kneel, sh, wp, U: y => y + by + dn + sh };
  return S;
}
function headBase(g, S, skin, eye, opts = {}) {
  const U = S.U, t = U(12);
  g.rect(16, t, 14, 13, skin);
  for (const [x, y] of [[16, t], [29, t], [16, t + 12], [29, t + 12], [16, t + 11], [29, t + 11]]) g.px(x, y, null);
  g.rect(21, t + 13, 5, 2, shade(skin, -0.12)); // 脖子
  g.px(20, t + 7, shade(skin, -0.2));
  for (const ex of [24, 27]) { if (opts.hideFront && ex === 27) continue; g.rect(ex, t + 6, 1, 3, '#1c1420'); g.px(ex, t + 8, eye); g.px(ex, t + 6, '#3a2a3a'); }
  g.px(26, t + 11, shade(skin, -0.25));
}
function legs(g, S, col, shoe, opts = {}) {
  const sh = S.sh;
  if (S.kneel) {
    g.rect(13, 54, 10, 4, col); g.rect(12, 58, 4, 3, shoe);           // 后腿跪地
    g.rect(22, 50, 7, 4, shade(col, 0.06)); g.rect(26, 53, 4, 7, shade(col, 0.06)); g.rect(26, 59, 6, 3, shoe);
    return;
  }
  const top = 41 + sh;
  g.rect(18, top, 4, GROUND - top - 1, col); g.rect(23, top, 4, GROUND - top - 1, shade(col, 0.06));
  g.rect(17, GROUND - 2, 5, 3, shoe); g.rect(23, GROUND - 2, 6, 3, shoe);
  if (opts.straps) for (let y = top + 6; y < GROUND - 2; y += 3) { g.rect(18, y, 4, 1, opts.straps); g.rect(23, y, 4, 1, opts.straps); }
}
function arm(g, S, front, sleeve, hand, opts = {}) {
  const U = S.U;
  if (!front) { g.rect(14, U(27), 3, 10, shade(sleeve, -0.12)); g.rect(14, U(37), 3, 2, shade(hand, -0.1)); return [15, U(38)]; }
  if (S.pose === 'atk') { g.rect(27, U(28), 8, 3, sleeve); g.rect(35, U(28), 2, 3, hand); if (opts.band) g.rect(31, U(28), 1, 3, opts.band); return [36, U(29)]; }
  if (S.pose === 'cast') { g.rect(27, U(18), 3, 10, sleeve); g.rect(27, U(16), 3, 2, hand); if (opts.band) g.rect(27, U(22), 3, 1, opts.band); return [28, U(16)]; }
  g.rect(27, U(27), 3, 10, sleeve); g.rect(27, U(37), 3, 2, hand); if (opts.band) g.rect(27, U(32), 3, 1, opts.band);
  return [28, U(38)];
}
function weapon(g, S, type, hx, hy, cols = {}) {
  // 武器画成 2 像素粗、带高光和暗边，比身体更亮，描边后在场上一眼能认出来
  const blade = cols.blade || '#f2f6fc', bdark = '#8c98ae', hilt = cols.hilt || '#3a2418', guard = cols.guard || '#d8b048';
  const shaft = cols.shaft || '#8a5a2c', sdark = shade(shaft, -0.3), metal = '#c4ccd8', mdark = '#6c7688', orb = cols.orb || '#8fe0ff';
  const L2 = (x0, y0, x1, y1, c1, c2, dx = 1, dy = 0) => { g.line(x0, y0, x1, y1, c1); g.line(x0 + dx, y0 + dy, x1 + dx, y1 + dy, c2); };
  const p = S.pose === 'atk' ? 'atk' : S.pose === 'cast' ? 'cast' : 'idle';
  if (type === 'staff' && cols.sun) { // 太阳杖：宝珠外一圈金色光芒（先画，宝珠盖在上面）
    const [cx, cy] = p === 'atk' ? [hx + 14, hy - 5] : p === 'cast' ? [hx + 1, hy - 11] : [hx + 2, hy - 26];
    for (let k = 0; k < 8; k++) { const an = k * Math.PI / 4, r = k % 2 ? 4 : 5; g.px(Math.round(cx + Math.cos(an) * r), Math.round(cy + Math.sin(an) * r), cols.sun); }
    g.rect(cx - 3, cy - 3, 7, 7, cols.sun);
  }
  if (p === 'atk') { // 手臂前伸，武器指向对手
    if (type === 'sword') { L2(hx + 1, hy - 1, hx + 17, hy - 6, '#ffffff', blade, 0, 1); g.line(hx + 2, hy + 1, hx + 16, hy - 4, bdark); g.line(hx, hy - 3, hx, hy + 2, guard); g.rect(hx - 3, hy, 3, 2, hilt); }
    else if (type === 'dagger') { L2(hx + 1, hy - 1, hx + 9, hy - 3, '#ffffff', blade, 0, 1); g.line(hx, hy - 2, hx, hy + 2, guard); g.rect(hx - 2, hy, 2, 2, hilt); }
    else if (type === 'polearm') { L2(hx - 14, hy + 3, hx + 11, hy - 1, shaft, sdark, 0, 1); g.poly([[hx + 11, hy - 4], [hx + 20, hy - 1], [hx + 11, hy + 3]], blade); g.line(hx + 12, hy - 1, hx + 18, hy - 1, bdark); g.rect(hx + 9, hy - 3, 2, 5, guard); }
    else if (type === 'axe') { L2(hx - 3, hy + 4, hx + 7, hy - 12, shaft, sdark); g.poly([[hx + 6, hy - 19], [hx + 15, hy - 16], [hx + 14, hy - 5], [hx + 7, hy - 9]], metal); g.line(hx + 15, hy - 16, hx + 14, hy - 5, '#ffffff'); g.line(hx + 7, hy - 9, hx + 9, hy - 17, mdark); }
    else if (type === 'bow') { for (let t = -1; t <= 1.001; t += 0.1) { const x = hx + 3 + Math.round(6 * (1 - t * t)), y = hy + Math.round(15 * t); g.px(x, y, shaft); g.px(x + 1, y, sdark); } g.line(hx + 3, hy - 15, hx - 4, hy, '#f0f0f0'); g.line(hx - 4, hy, hx + 3, hy + 15, '#f0f0f0'); g.line(hx - 4, hy, hx + 14, hy, '#d8c8a0'); g.poly([[hx + 14, hy - 2], [hx + 18, hy], [hx + 14, hy + 2]], metal); }
    else if (type === 'staff') { L2(hx - 7, hy + 3, hx + 12, hy - 3, shaft, sdark, 0, 1); g.rect(hx + 12, hy - 7, 5, 5, orb); g.px(hx + 13, hy - 6, '#ffffff'); g.rect(hx + 11, hy - 3, 2, 2, guard); }
    return;
  }
  if (p === 'cast') { // 举起武器
    if (type === 'bow') { for (let t = -1; t <= 1.001; t += 0.1) { const x = hx + 2 + Math.round(5 * (1 - t * t)), y = hy - 2 + Math.round(13 * t); g.px(x, y, shaft); g.px(x + 1, y, sdark); } g.line(hx + 2, hy - 15, hx + 2, hy + 11, '#f0f0f0'); return; }
    // 举手施法时手在头顶附近，武器往下握，免得超出精灵上沿
    if (type === 'sword' || type === 'dagger') { const n = type === 'sword' ? 12 : 7; L2(hx, hy - 1, hx, hy - n, '#ffffff', blade); g.line(hx - 2, hy, hx + 3, hy, guard); g.rect(hx, hy + 1, 2, 3, hilt); }
    else {
      L2(hx, hy + 14, hx, hy - 8, shaft, sdark);
      if (type === 'staff') { g.rect(hx - 2, hy - 14, 6, 6, orb); g.px(hx - 1, hy - 13, '#ffffff'); g.line(hx - 3, hy - 8, hx + 4, hy - 8, guard); }
      if (type === 'axe') { g.poly([[hx + 2, hy - 11], [hx + 10, hy - 13], [hx + 10, hy - 1], [hx + 2, hy - 4]], metal); g.line(hx + 10, hy - 13, hx + 10, hy - 1, '#ffffff'); }
      if (type === 'polearm') { g.poly([[hx - 2, hy - 8], [hx + 0.5, hy - 16], [hx + 3, hy - 8]], blade); g.rect(hx - 1, hy - 8, 4, 2, guard); }
    }
    return;
  }
  // 待机：剑、短剑斜举在身前，长柄武器竖握
  if (type === 'sword') { L2(hx + 1, hy - 2, hx + 9, hy - 19, '#ffffff', blade); g.line(hx + 3, hy - 2, hx + 10, hy - 17, bdark); g.line(hx - 2, hy - 3, hx + 5, hy, guard); g.rect(hx - 1, hy, 2, 3, hilt); }
  else if (type === 'dagger') { L2(hx + 1, hy - 2, hx + 5, hy - 10, '#ffffff', blade); g.line(hx - 1, hy - 3, hx + 4, hy - 1, guard); g.rect(hx, hy, 2, 2, hilt); }
  else if (type === 'polearm') { L2(hx - 2, hy + 15, hx + 8, hy - 24, shaft, sdark); g.poly([[hx + 6, hy - 25], [hx + 11, hy - 35], [hx + 11, hy - 23]], blade); g.line(hx + 10, hy - 32, hx + 9, hy - 26, bdark); g.rect(hx + 6, hy - 25, 5, 2, guard); g.rect(hx + 6, hy - 23, 2, 3, '#c83030'); } // 枪向前斜立，避开帽檐
  else if (type === 'axe') { L2(hx + 1, hy + 12, hx + 1, hy - 16, shaft, sdark); g.poly([[hx + 3, hy - 18], [hx + 12, hy - 22], [hx + 13, hy - 8], [hx + 3, hy - 11]], metal); g.line(hx + 12, hy - 22, hx + 13, hy - 8, '#ffffff'); g.line(hx + 3, hy - 17, hx + 3, hy - 11, mdark); g.poly([[hx, hy - 17], [hx - 4, hy - 14], [hx, hy - 12]], mdark); }
  else if (type === 'bow') { for (let t = -1; t <= 1.001; t += 0.08) { const x = hx + 3 + Math.round(6 * (1 - t * t)), y = hy - 2 + Math.round(17 * t); g.px(x, y, shaft); g.px(x + 1, y, sdark); } g.line(hx + 3, hy - 19, hx + 3, hy + 15, '#f0f0f0'); g.rect(hx + 8, hy - 4, 2, 4, '#d8c8a0'); }
  else if (type === 'staff') { L2(hx + 1, hy + 16, hx + 1, hy - 22, shaft, sdark); g.rect(hx - 1, hy - 29, 6, 6, orb); g.px(hx, hy - 28, '#ffffff'); g.rect(hx - 2, hy - 23, 8, 2, guard); g.px(hx - 2, hy - 30, guard); g.px(hx + 5, hy - 30, guard); }
}

const DRAW = {
  // 剑士 光：高马尾（红绳束发）垂到背后，金边红羽织罩黑色胸甲和肩甲，白衬领，红腰带，金纹黑袴，白足袋草鞋，腰间刀鞘
  hikari(g, S) {
    const U = S.U, hair = '#1a1822', hairH = '#3c3650', red = '#b02428', redD = '#7a1418', gold = '#d8a838', blk = '#1c1a22', armor = '#2c2a34', skin = '#efc6a0';
    g.poly([[18, U(9)], [13, U(14)], [10, U(24)], [9, U(36)], [12, U(38)], [14, U(28)], [17, U(18)], [21, U(10)]], hair);
    g.line(11, U(22), 11, U(34), hairH);
    arm(g, S, false, red, blk);
    const hemY = S.kneel ? GROUND : GROUND - 3;
    g.poly([[16, U(38)], [29, U(38)], [32, hemY], [13, hemY]], blk);                                   // 黑袴
    for (let y = U(41), k = 0; y < hemY - 1; y += 4, k++) { g.px(16 + (k % 3) * 4, y, gold); g.px(27 - (k % 2) * 3, y + 2, gold); }
    g.rect(22, U(40), 1, hemY - U(40), '#0c0b10');
    if (!S.kneel) { g.rect(16, GROUND - 3, 5, 2, '#f0ece2'); g.rect(23, GROUND - 3, 6, 2, '#f0ece2'); g.rect(16, GROUND - 1, 5, 1, '#7a5a30'); g.rect(23, GROUND - 1, 6, 1, '#7a5a30'); }
    else { g.rect(12, GROUND - 2, 6, 2, '#f0ece2'); g.rect(27, GROUND - 2, 5, 2, '#f0ece2'); }
    g.poly([[15, U(25)], [30, U(25)], [32, U(45)], [28, U(45)], [26, U(30)], [19, U(30)], [17, U(45)], [13, U(45)]], red); // 红羽织
    g.line(15, U(26), 13, U(44), gold); g.line(30, U(26), 32, U(44), gold); g.rect(13, U(45), 5, 1, gold); g.rect(28, U(45), 5, 1, gold);
    for (const [x, y] of [[15, 34], [29, 38], [16, 41], [30, 31], [14, 30]]) g.px(x, U(y), '#e6b850');
    g.rect(19, U(27), 8, 10, armor); for (let y = 29; y < 37; y += 2) g.rect(19, U(y), 8, 1, '#40404c');  // 胸甲
    g.px(20, U(30), '#c83030'); g.px(25, U(32), '#c83030'); g.px(21, U(34), gold);
    g.poly([[20, U(25)], [26, U(25)], [23, U(29)]], '#f2efe6');                                          // 白衬领
    g.rect(18, U(37), 10, 2, red); g.rect(18, U(38), 10, 1, redD);
    g.rect(12, U(25), 5, 4, armor); g.rect(12, U(28), 5, 1, gold); g.px(14, U(26), '#c83030');          // 后肩甲
    g.line(11, U(40), 33, U(35), '#2a1810'); g.px(33, U(35), gold); g.px(11, U(40), gold);              // 刀鞘
    headBase(g, S, skin, '#4a3020');
    g.rect(16, U(10), 14, 4, hair); g.rect(16, U(12), 5, 9, hair); g.rect(28, U(13), 2, 4, hair);
    for (const [x, y] of [[25, 14], [26, 15], [23, 14], [27, 16], [22, 15], [24, 15]]) g.px(x, U(y), hair);
    g.px(19, U(10), hairH); g.px(24, U(10), hairH); g.px(27, U(11), hairH);
    g.rect(18, U(7), 4, 4, hair); g.rect(18, U(9), 4, 1, '#d02a2a'); g.px(17, U(10), '#d02a2a');      // 顶髻红绳
    const [hx, hy] = arm(g, S, true, red, blk);
    g.rect(27, U(25), 5, 4, armor); g.rect(27, U(28), 5, 1, gold); g.px(29, U(26), '#c83030');          // 前肩甲
    weapon(g, S, S.wp || 'sword', hx, hy, { guard: '#2a2018' });
  },
  // 舞娘 爱格妮娅：棕色波浪长卷发，头侧红花绿叶和红丝带，金耳环；露肩白荷叶边上衣，绿色胸衣金色系带，红色花纹腰巾，绿色裙配白色荷叶裙边，棕色系带短靴，金手镯
  agnea(g, S) {
    const U = S.U, hair = '#8a5226', hairH = '#b8783e', skin = '#f6d3b2', grn = '#2c7448', grnD = '#1c5232', wht = '#f6f1e6', red = '#c8342c', gold = '#d8a838', boot = '#6a4224';
    g.poly([[16, U(11)], [12, U(16)], [11, U(24)], [13, U(30)], [11, U(34)], [16, U(34)], [17, U(26)], [19, U(17)]], hair);
    for (const [x, y] of [[12, 20], [13, 26], [14, 31], [12, 29], [15, 23]]) g.px(x, U(y), hairH);
    arm(g, S, false, skin, skin, { band: gold });
    legs(g, S, skin, boot);
    if (!S.kneel) { g.rect(18, 52, 4, 7, boot); g.rect(23, 52, 4, 7, boot); for (let y = 53; y < 58; y += 2) { g.px(20, y, '#c8a070'); g.px(25, y, '#c8a070'); } }
    // 裙子：白色荷叶裙边在下，绿裙在上，前短后长
    g.poly([[13, U(42)], [34, U(41)], [34, U(46)], [31, U(48)], [15, U(51)], [11, U(49)]], wht);
    for (let x = 12; x < 34; x += 2) g.px(x, U(51) - Math.round((x - 12) * 0.14), wht);
    g.poly([[17, U(36)], [28, U(36)], [33, U(44)], [30, U(46)], [15, U(49)], [12, U(46)]], grn);
    for (const [x, y] of [[16, 44], [20, 41], [25, 43], [29, 40], [22, 46], [18, 39]]) g.px(x, U(y), gold);
    g.line(14, U(46), 30, U(43), grnD);
    g.rect(16, U(35), 14, 2, red); g.line(16, U(37), 13, U(45), red); g.line(17, U(37), 15, U(45), '#a8241c');   // 红腰巾和垂下的一角
    g.px(13, U(46), gold); g.px(15, U(46), gold);
    g.rect(17, U(28), 11, 8, grn); for (let y = 29; y < 35; y += 2) { g.px(22, U(y), gold); g.px(23, U(y + 1), gold); }  // 绿胸衣+系带
    g.rect(16, U(26), 14, 2, wht); for (let x = 16; x < 30; x += 2) g.px(x, U(28), wht);                // 露肩荷叶边
    g.rect(20, U(25), 6, 1, skin); g.px(22, U(26), gold); g.px(23, U(26), '#e0a030');                   // 项链
    g.rect(12, U(25), 5, 3, wht);                                                                      // 后侧泡泡袖
    headBase(g, S, skin, '#7a4a2a');
    g.rect(16, U(9), 14, 5, hair); g.rect(16, U(12), 4, 12, hair); g.rect(28, U(13), 2, 10, hair); g.px(30, U(18), hair); g.px(30, U(21), hair);
    for (const [x, y] of [[22, 14], [24, 14], [25, 15], [21, 15], [27, 14]]) g.px(x, U(y), hair);
    for (const [x, y] of [[18, 10], [22, 9], [26, 10], [17, 16], [29, 15]]) g.px(x, U(y), hairH);
    g.rect(15, U(9), 4, 4, red); g.px(16, U(10), '#ff8a80'); g.px(17, U(11), '#e8c040'); g.px(14, U(12), '#3a8a3a'); g.px(19, U(12), '#3a8a3a'); // 红花绿叶
    g.line(15, U(13), 14, U(19), red); g.px(14, U(20), gold);                                          // 红丝带、珠串
    g.px(20, U(22), gold); g.px(20, U(23), '#2a9aa0');                                                 // 耳环
    const [hx, hy] = arm(g, S, true, skin, skin, { band: gold });
    g.rect(26, U(25), 5, 3, wht);                                                                      // 前侧泡泡袖
    weapon(g, S, S.wp || 'dagger', hx, hy);
  },
  // 商人 帕特提欧：黄色宽檐帽配深棕帽带和黑羽毛，棕色乱发、胡茬；敞开的黄色长风衣（立领），白衬衫红领巾，棕马甲，斜挎皮带和腰包，棕皮裤长靴，棕手套
  partitio(g, S) {
    const U = S.U, yel = '#e6b62a', yelD = '#b08418', skin = '#e2b088', hair = '#5a3a20', brn = '#6a4428', brnD = '#45291a';
    g.poly([[14, U(26)], [31, U(26)], [33, U(50)], [12, U(50)]], yelD);                                // 风衣后摆
    arm(g, S, false, yel, brn);
    legs(g, S, '#5a3c26', '#3a2414');
    if (!S.kneel) { g.rect(17, 50, 6, 9, brnD); g.rect(23, 50, 6, 9, brnD); g.rect(17, 50, 6, 1, brn); g.rect(23, 50, 6, 1, brn); }
    g.rect(17, U(26), 11, 13, brn); for (let y = 29; y < 37; y += 3) g.px(23, U(y), '#d8b048');         // 棕马甲
    g.rect(20, U(25), 5, 5, '#f4f0e8'); g.rect(20, U(25), 5, 2, '#c8302a'); g.px(22, U(27), '#c8302a'); g.px(23, U(28), '#a02020'); // 白衬衫红领巾
    g.line(17, U(27), 27, U(38), '#3a2414');                                                            // 斜挎皮带
    g.rect(16, U(38), 13, 2, '#3a2414'); g.px(22, U(38), '#d8b048');
    g.rect(11, U(38), 6, 6, '#7a5030'); g.rect(11, U(38), 6, 1, '#5a3420'); g.px(13, U(40), '#d8b048'); // 腰包
    g.poly([[14, U(24)], [18, U(24)], [19, U(40)], [17, U(50)], [13, U(50)]], yel);                    // 敞开的黄风衣
    g.poly([[27, U(24)], [31, U(24)], [33, U(50)], [29, U(50)], [27, U(40)]], yel);
    g.line(18, U(26), 18, U(48), yelD); g.line(28, U(26), 29, U(48), yelD);
    g.rect(14, U(23), 4, 3, yel); g.rect(28, U(23), 4, 3, yel);                                         // 立领
    headBase(g, S, skin, '#5a3a20');
    g.rect(16, U(12), 4, 9, hair); g.rect(27, U(13), 3, 4, hair); g.px(25, U(14), hair); g.px(29, U(18), hair);
    for (let x = 22; x < 29; x += 2) g.px(x, U(23), '#8a6040'); g.px(25, U(24), '#8a6040');             // 胡茬
    g.rect(17, U(5), 12, 6, yel); g.rect(19, U(4), 8, 1, yel); g.rect(21, U(5), 4, 1, yelD); g.px(23, U(6), yelD); // 黄色宽檐帽
    g.rect(17, U(9), 12, 2, '#3a2a1c');
    g.poly([[11, U(11)], [35, U(11)], [33, U(13)], [13, U(13)]], yel); g.line(13, U(12), 33, U(12), yelD);
    g.line(16, U(9), 12, U(2), '#2a3036'); g.line(15, U(9), 11, U(3), '#5a6a78'); g.px(12, U(1), '#2a3036'); // 黑羽毛
    const [hx, hy] = arm(g, S, true, yel, brn);
    weapon(g, S, S.wp || 'polearm', hx, hy);
  },
  // 学者 奥兹巴尔多：灰褐色及肩乱发、灰白络腮胡、圆框眼镜；厚重的棕色长大衣（翻领）到脚踝，灰马甲，深色领巾，棕裤皮鞋
  osvald(g, S) {
    const U = S.U, hair = '#7c7266', hairH = '#a89c8e', coat = '#5c4a3a', coatD = '#3c3024', skin = '#dcb492';
    g.poly([[16, U(11)], [12, U(16)], [11, U(28)], [14, U(31)], [18, U(26)], [19, U(16)]], hair);
    g.line(12, U(18), 12, U(27), hairH); g.line(15, U(20), 16, U(29), hairH);
    arm(g, S, false, coat, skin);
    legs(g, S, '#3a322a', '#2a1e14');
    const hemY = S.kneel ? GROUND : GROUND - 4;
    g.poly([[15, U(25)], [30, U(25)], [33, hemY], [12, hemY]], coat);
    g.rect(19, U(26), 7, 13, '#6c6c74'); for (let y = 28; y < 38; y += 3) g.px(22, U(y), '#c8b070');      // 灰马甲
    g.rect(20, U(25), 5, 3, '#34343e');                                                                 // 领巾
    g.poly([[15, U(24)], [19, U(24)], [19, U(40)], [17, hemY], [12, hemY]], coat);
    g.poly([[26, U(24)], [30, U(24)], [33, hemY], [28, hemY], [26, U(40)]], coat);
    g.line(19, U(26), 17, hemY - 1, coatD); g.line(26, U(26), 28, hemY - 1, coatD);
    g.rect(14, U(24), 5, 3, coatD); g.rect(26, U(24), 5, 3, coatD);                                     // 翻领
    for (const [x, y] of [[14, 33], [30, 41], [16, 47], [31, 50], [13, 52], [29, 35]]) g.px(x, U(y), coatD);
    headBase(g, S, skin, '#3a4a5a');
    g.rect(15, U(10), 15, 4, hair); g.rect(15, U(12), 5, 12, hair); g.rect(27, U(13), 3, 3, hair); g.px(29, U(16), hair);
    for (const [x, y] of [[14, 13], [13, 17], [30, 11], [25, 9], [20, 9], [17, 9]]) g.px(x, U(y), hair);
    g.px(19, U(11), hairH); g.px(23, U(10), hairH); g.px(16, U(16), hairH);
    g.rect(22, U(21), 8, 4, '#8e867c'); g.px(29, U(24), null); g.rect(25, U(22), 2, 1, shade(skin, -0.3));    // 灰白络腮胡
    for (const ex of [24, 27]) for (const [dx, dy] of [[-1, 18], [1, 18], [-1, 20], [1, 20], [0, 17], [0, 21]]) g.px(ex + dx, U(dy), '#d0b878'); // 圆框眼镜
    const [hx, hy] = arm(g, S, true, coat, skin);
    weapon(g, S, S.wp || 'staff', hx, hy, { orb: '#a0c0ff' });
  },
  // 神官 提米诺斯：银白短发、蓝眼；白色兜帽斗篷（金边、蓝色刺绣），蓝色内衬配金十字，白色长袍蓝金下摆，皮带小包，金色太阳杖
  temenos(g, S) {
    const U = S.U, wht = '#f2f0ea', whtD = '#c8c4bc', blue = '#3a78b8', blueL = '#8ac0e8', gold = '#d8b048', hair = '#e4e6ee', hairH = '#b4b8c6', skin = '#f6dcc6';
    g.poly([[14, U(24)], [18, U(23)], [17, U(52)], [11, U(54)], [12, U(36)]], whtD);                  // 斗篷后摆
    arm(g, S, false, wht, skin);
    legs(g, S, '#e8e4dc', '#4a3220');
    const hemY = S.kneel ? GROUND : GROUND - 3;
    g.poly([[16, U(30)], [29, U(30)], [31, hemY], [14, hemY]], wht);
    g.rect(14, hemY - 2, 18, 2, blue); g.rect(14, hemY - 3, 18, 1, gold);
    for (let y = U(40), k = 0; y < hemY - 4; y += 3, k++) { g.px(19 + (k % 2), y, gold); g.px(25, y + 1, blueL); }
    g.rect(22, U(30), 1, hemY - U(30) - 3, blue);
    g.rect(18, U(26), 10, 10, blue); g.rect(18, U(26), 10, 1, blueL);                                  // 蓝内衬
    g.rect(22, U(27), 2, 6, gold); g.rect(20, U(29), 6, 2, gold);                                      // 金十字
    g.rect(17, U(36), 12, 2, '#6a4428'); g.rect(26, U(37), 3, 4, '#7a5232'); g.px(27, U(38), gold);   // 皮带小包
    g.poly([[15, U(24)], [19, U(24)], [19, U(40)], [16, U(47)], [14, U(40)]], wht); g.line(19, U(25), 19, U(40), gold);
    g.poly([[26, U(24)], [30, U(24)], [31, U(40)], [29, U(47)], [27, U(40)]], wht); g.line(27, U(25), 27, U(40), gold);
    for (const [x, y] of [[16, 30], [17, 36], [29, 33], [28, 42], [16, 43]]) g.px(x, U(y), blueL);
    g.rect(15, U(22), 15, 4, wht); g.rect(15, U(25), 15, 1, whtD); g.rect(13, U(21), 4, 5, wht);        // 放下的兜帽
    headBase(g, S, skin, '#3a6ad0');
    g.rect(16, U(9), 14, 5, hair); g.rect(16, U(12), 4, 10, hair); g.rect(22, U(13), 8, 2, hair); g.px(26, U(15), hair); g.px(28, U(15), hair); g.px(29, U(16), hair);
    g.px(18, U(10), hairH); g.px(24, U(10), hairH); g.px(20, U(13), hairH); g.px(27, U(14), hairH);
    const [hx, hy] = arm(g, S, true, wht, skin);
    weapon(g, S, S.wp || 'staff', hx, hy, { shaft: '#3a2a1e', orb: '#4a8ae0', sun: gold });
  },
  // 盗贼 斯洛妮：黑紫色乱短发、紫眼、金耳环、黑颈环；无肩带黑色束身裙（金扣），紫色破边披帛绕在臂间，黑色长手套，侧开衩短裙，黑色过膝高跟长靴
  throne(g, S) {
    const U = S.U, hair = '#2a2236', hairH = '#5a4a7c', blk = '#1e1a24', pur = '#5e3a86', purD = '#3e2460', skin = '#f2d2bc', gold = '#c8a040';
    g.poly([[13, U(25)], [17, U(25)], [16, U(44)], [14, U(49)], [12, U(45)], [9, U(48)], [10, U(36)]], pur); // 背后的紫披帛
    g.px(11, U(47), purD); g.px(13, U(42), purD);
    arm(g, S, false, blk, blk);
    legs(g, S, blk, '#100c14');
    if (!S.kneel) { const ty = 41 + S.sh; g.rect(18, ty, 4, 3, skin); g.rect(23, ty, 4, 3, skin); g.rect(18, ty + 3, 4, 1, '#3a3044'); g.rect(23, ty + 3, 4, 1, '#3a3044'); g.px(20, ty + 1, gold); }
    g.poly([[17, U(36)], [28, U(36)], [31, U(43)], [28, U(42)], [26, U(45)], [24, U(41)], [21, U(44)], [19, U(41)], [16, U(43)]], blk); // 破边短裙
    g.poly([[16, U(36)], [19, U(36)], [18, U(49)], [14, U(47)]], pur);
    g.rect(18, U(25), 9, 2, skin);
    g.rect(17, U(27), 11, 10, blk); g.rect(17, U(27), 11, 1, purD);                                     // 黑色束身裙
    for (let y = 29; y < 36; y += 2) { g.px(21, U(y), pur); g.px(24, U(y), pur); }
    g.px(19, U(33), gold); g.px(26, U(33), gold); g.rect(17, U(35), 11, 1, '#3a2a40');
    g.rect(21, U(24), 5, 1, '#100c14');                                                                 // 颈环
    headBase(g, S, skin, '#9a5ac8');
    g.rect(15, U(9), 15, 5, hair); g.rect(15, U(12), 5, 11, hair); g.rect(24, U(13), 6, 3, hair); g.px(28, U(16), hair); g.px(29, U(17), hair);
    for (const [x, y] of [[14, 14], [14, 18], [15, 22], [30, 12], [22, 13], [26, 8]]) g.px(x, U(y), hair);
    for (const [x, y] of [[18, 10], [23, 10], [27, 11], [16, 17], [25, 14]]) g.px(x, U(y), hairH);
    g.px(20, U(22), gold); g.px(20, U(23), gold);                                                      // 金耳环
    const [hx, hy] = arm(g, S, true, blk, blk);
    g.rect(26, U(25), 5, 4, pur); g.px(30, U(29), pur); g.px(27, U(29), purD);                          // 前臂上的披帛
    weapon(g, S, S.wp || 'dagger', hx, hy);
  },
  // 猎人 欧修缇：个子小，橙色蓬乱头发插羽毛，狐耳（白色内毛）和大狐尾，琥珀色眼睛，褐色皮肤；橙色毛边抹胸、牙齿项链，露腰，毛边短裙挂彩色羽毛，毛皮护腕，毛边皮靴，背后箭筒
  ochette(g, S) {
    const U = S.U, hair = '#e8923a', hairH = '#f8c474', skin = '#b8784a', fur = '#f4ece0', org = '#e2602a', brn = '#7a4a2a', teal = '#2a9aa0';
    // 伙伴（豺）
    g.rect(2, 52, 9, 6, '#c8945a'); g.rect(1, 48, 5, 5, '#c8945a'); g.px(1, 47, '#c8945a'); g.px(4, 46, '#c8945a');
    g.px(3, 50, '#1a1220'); g.rect(2, 58, 2, 3, '#a87444'); g.rect(8, 58, 2, 3, '#a87444'); g.line(11, 53, 13, 50, '#e8c08a');
    g.poly([[17, U(37)], [12, U(39)], [7, U(37)], [3, U(31)], [4, U(26)], [8, U(28)], [11, U(33)], [17, U(34)]], hair); // 大狐尾
    g.poly([[4, U(26)], [3, U(31)], [5, U(32)], [7, U(28)]], fur); g.line(9, U(34), 14, U(36), hairH);
    g.rect(12, U(24), 3, 9, '#6a4428'); g.px(12, U(23), '#e8e0d0'); g.px(14, U(22), '#e8e0d0'); g.px(13, U(22), org); // 箭筒
    arm(g, S, false, skin, skin, { band: fur });
    legs(g, S, skin, brn);
    if (!S.kneel) { g.rect(17, 52, 6, 7, brn); g.rect(23, 52, 6, 7, brn); g.rect(16, 51, 7, 2, fur); g.rect(22, 51, 8, 2, fur); g.px(20, 55, teal); }
    g.poly([[16, U(35)], [29, U(35)], [31, U(42)], [14, U(42)]], '#8a5a34');                            // 毛边短裙
    g.poly([[22, U(35)], [29, U(35)], [31, U(42)], [24, U(42)]], org);
    g.rect(14, U(42), 18, 1, fur); for (let x = 14; x < 32; x += 2) g.px(x, U(43), fur);
    g.line(16, U(42), 15, U(46), teal); g.line(29, U(42), 30, U(46), org); g.line(26, U(42), 26, U(45), '#d84868'); // 挂着的羽毛
    g.rect(16, U(34), 14, 1, '#5a3420');
    g.rect(17, U(26), 11, 4, org); g.rect(17, U(26), 11, 1, fur); g.rect(17, U(29), 11, 1, fur);       // 毛边抹胸
    g.px(21, U(25), '#f6f2e6'); g.px(23, U(25), teal); g.px(25, U(25), '#f6f2e6');                    // 牙齿项链
    headBase(g, S, skin, '#e09a20');
    g.rect(15, U(9), 15, 5, hair); g.rect(15, U(12), 5, 11, hair); g.rect(22, U(13), 8, 2, hair); g.rect(28, U(14), 2, 5, hair);
    for (const [x, y] of [[14, 12], [13, 16], [14, 21], [30, 12], [26, 15], [23, 15], [21, 8]]) g.px(x, U(y), hair);
    for (const [x, y] of [[17, 10], [24, 10], [19, 14], [27, 12]]) g.px(x, U(y), hairH);
    g.poly([[15, U(11)], [16, U(2)], [22, U(10)]], hair); g.poly([[16, U(9)], [17, U(5)], [20, U(9)]], fur); // 狐耳
    g.poly([[23, U(10)], [28, U(1)], [30, U(10)]], hair); g.poly([[25, U(9)], [27, U(4)], [28, U(9)]], fur);
    g.line(15, U(14), 13, U(22), teal); g.line(16, U(15), 15, U(23), org); g.px(13, U(23), '#d84868');  // 发间羽毛
    const [hx, hy] = arm(g, S, true, skin, skin, { band: fur });
    weapon(g, S, S.wp || 'bow', hx, hy);
  },
  // 药师 卡斯蒂：青蓝色短发，白色贝雷帽配蓝色帽圈和金徽章；蓝色高领长裙，白色泡泡袖，白围裙，斜挎皮带、腰带和大皮包（插着药瓶），棕手套，棕色系带靴
  castti(g, S) {
    const U = S.U, hair = '#2e6a82', hairH = '#5a9ab2', blue = '#2a4c9a', blueD = '#1c3470', wht = '#f2eee4', skin = '#f4d2b4', brn = '#7a4a28', glove = '#5a3a22';
    arm(g, S, false, blue, glove);
    legs(g, S, '#2a2a34', '#5a3a22');
    const hemY = S.kneel ? GROUND : GROUND - 5;
    g.poly([[16, U(36)], [29, U(36)], [32, hemY], [13, hemY]], blue); g.rect(13, hemY - 1, 20, 1, wht); g.rect(13, hemY - 3, 20, 1, '#d8c890');
    if (!S.kneel) { g.rect(18, GROUND - 5, 4, 4, '#6a4224'); g.rect(23, GROUND - 5, 4, 4, '#6a4224'); }
    g.poly([[18, U(30)], [28, U(30)], [29, hemY - 3], [17, hemY - 3]], wht);                            // 白围裙
    g.line(18, U(38), 17, hemY - 4, '#d8d2c4');
    g.rect(17, U(25), 11, 11, blue); g.rect(20, U(24), 5, 2, blueD); for (let y = 27; y < 31; y += 2) g.px(22, U(y), '#d8b048');
    g.rect(18, U(30), 10, 6, wht);
    g.rect(16, U(35), 14, 2, brn); g.px(22, U(35), '#d8b048');
    g.line(17, U(26), 28, U(36), brn);
    g.rect(10, U(35), 7, 7, brn); g.rect(10, U(35), 7, 1, '#5a3418'); g.px(13, U(37), '#d8b048');    // 大皮包
    g.px(11, U(34), '#48c060'); g.px(13, U(33), '#e04848'); g.px(15, U(34), '#48a0e0'); g.px(12, U(33), '#3a8a3a');
    g.rect(12, U(25), 5, 3, wht);                                                                      // 后侧泡泡袖
    headBase(g, S, skin, '#3a6a9a');
    g.rect(16, U(10), 14, 4, hair); g.rect(15, U(12), 5, 11, hair); g.rect(22, U(13), 8, 2, hair); g.rect(28, U(15), 2, 6, hair); g.px(26, U(15), hair);
    for (const [x, y] of [[18, 13], [24, 13], [16, 18], [29, 19]]) g.px(x, U(y), hairH);
    g.rect(15, U(6), 16, 4, wht); g.rect(17, U(5), 11, 1, wht); g.rect(15, U(9), 15, 2, '#2a4c9a'); g.px(26, U(9), '#d8b048'); g.px(31, U(7), wht); // 白贝雷帽
    const [hx, hy] = arm(g, S, true, blue, glove);
    g.rect(26, U(25), 5, 3, wht);                                                                      // 前侧泡泡袖
    weapon(g, S, S.wp || 'axe', hx, hy);
  },
};

function buildSprite(key, pose, f, wp) {
  const g = new Grid(SPR_W, SPR_H, SPR_PAD);
  DRAW[key](g, poseCtx(pose, f, key === 'ochette' ? 5 : 0, wp));
  const c = mk(SPR_W, SPR_H), x = c.getContext('2d');
  for (let yy = 0; yy < SPR_H; yy++) for (let xx = 0; xx < SPR_W; xx++) {
    let col = g.get(xx, yy);
    if (!col) {
      if (g.get(xx - 1, yy) || g.get(xx + 1, yy) || g.get(xx, yy - 1) || g.get(xx, yy + 1)) col = OUTLINE;
    } else {
      // 简单光照：左上受光，右侧和下沿背光
      if (!g.get(xx + 1, yy) || !g.get(xx, yy + 1)) col = shade(col, -0.22);
      else if (!g.get(xx - 1, yy) || !g.get(xx, yy - 1)) col = shade(col, 0.14);
      else if (g.get(xx + 1, yy) !== col && g.get(xx + 1, yy)) col = shade(col, -0.08);
    }
    if (col) { x.fillStyle = col; x.fillRect(xx, yy, 1, 1); }
  }
  return c;
}
const sprCache = {};
function sprite(key, pose, f, flip, tint, wp) {
  const k = key + pose + f + flip + (tint || '') + (wp || '');
  if (sprCache[k]) return sprCache[k];
  let c = buildSprite(key, pose, f, wp);
  if (flip) { const d = mk(SPR_W, SPR_H), x = d.getContext('2d'); x.translate(SPR_W, 0); x.scale(-1, 1); x.drawImage(c, 0, 0); c = d; }
  if (tint) { const d = mk(SPR_W, SPR_H), x = d.getContext('2d'); x.drawImage(c, 0, 0); x.globalCompositeOperation = 'source-atop'; x.fillStyle = tint; x.fillRect(0, 0, SPR_W, SPR_H); c = d; }
  return (sprCache[k] = c);
}
// 头像：优先用设计图裁出来的头像，图片还没解码好时先用像素头像顶上
const PORTRAIT_IMG = {};
for (const [k, src] of Object.entries(typeof PORTRAIT_SRC === 'object' ? PORTRAIT_SRC : {})) { const im = new Image(); im.src = src; PORTRAIT_IMG[k] = im; }
function face(key, flip) {
  const im = PORTRAIT_IMG[key];
  return im && im.complete && im.naturalWidth ? im : portrait(key, flip);
}
function drawFace(key, flip, x, y, s) {
  const im = face(key, flip);
  ctx.save(); ctx.imageSmoothingEnabled = im instanceof HTMLImageElement; ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(im, x, y, s, s); ctx.restore();
}
// 技能特写：全身立绘（用户设计图裁出，透明底）
const CUTIN_IMG = {};
for (const [k, src] of Object.entries(typeof CUTIN_SRC === 'object' ? CUTIN_SRC : {})) { const im = new Image(); im.src = src; CUTIN_IMG[k] = im; }
let cutin = null, CUT_ON = true;
try { CUT_ON = localStorage.getItem('op_cutin') !== '0'; } catch (e) {}
// [暗色, 亮色, 描边/文字]：A 队蓝、B 队红，神技和潜力技用金色
const CUT_COL = { 0: ['6,16,44', '36,96,190', '#9fd0ff'], 1: ['46,6,14', '196,40,58', '#ffb0a8'], gold: ['40,22,2', '214,150,36', '#ffe596'] };
function cutPath(cy, bh, rot) {
  ctx.beginPath();
  const c = Math.cos(rot), s = Math.sin(rot), pts = [[-W, -bh / 2], [W, -bh / 2], [W, bh / 2], [-W, bh / 2]];
  pts.forEach(([x, y], i) => { const X = W / 2 + x * c - y * s, Y = cy + x * s + y * c; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
  ctx.closePath();
}
function drawCutin() {
  const c = cutin; if (!c) return;
  const p = c.p, L = c.team === 0, dir = L ? 1 : -1, big = c.lv === 2;
  const ein = Math.min(1, p / 0.16), e = 1 - Math.pow(1 - ein, 3);
  const out = p > 0.84 ? (p - 0.84) / 0.16 : 0, env = Math.min(1, ein * 1.6) * (1 - out);
  const col = CUT_COL[big ? 'gold' : c.team];
  let cy = H * 0.53; const bh = (big ? 340 : 280) * (0.35 + 0.65 * e) * (1 - out * out), rot = -0.07 * dir;
  ctx.save();
  // 场景压暗
  const V = VR, port = V.w < V.h;
  ctx.fillStyle = `rgba(4,2,10,${(big ? 0.66 : 0.52) * env})`; ctx.fillRect(V.x, V.y, V.w, V.h);
  // 斜向色带 + 速度线
  ctx.save(); ctx.globalAlpha = env;
  cutPath(cy, bh, rot);
  const g = ctx.createLinearGradient(L ? 0 : W, 0, L ? W : 0, 0);
  g.addColorStop(0, `rgba(${col[1]},.97)`); g.addColorStop(0.45, `rgba(${col[0]},.96)`); g.addColorStop(1, `rgba(${col[0]},.93)`);
  ctx.fillStyle = g; ctx.fill();
  ctx.save(); ctx.clip();
  const span = W + 900;
  for (let i = 0; i < (big ? 60 : 44); i++) {
    const y = cy - bh / 2 + rnd(i * 3 + 1) * bh + (rnd(i) - 0.5) * 40, len = 120 + rnd(i * 5 + 2) * 460, v = 1.4 + rnd(i * 7 + 3) * 2.6;
    let x = (rnd(i * 11 + 4) * span + now * v) % span - 450; if (L) x = W - x;
    const th = 1 + rnd(i * 13 + 5) * 3.5, a = 0.08 + rnd(i * 17 + 6) * (big ? 0.42 : 0.3);
    const lg = ctx.createLinearGradient(x, 0, x + len * dir, 0);
    lg.addColorStop(0, `rgba(255,255,255,${a})`); lg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = lg; ctx.fillRect(Math.min(x, x + len * dir), y - th / 2, len, th);
  }
  // 立绘身后的光晕
  const hx = port ? W / 2 - dir * V.w * 0.1 : L ? V.x + V.w * 0.236 : V.x + V.w * 0.764, rg = ctx.createRadialGradient(hx, cy, 10, hx, cy, 420);
  rg.addColorStop(0, `rgba(${col[1]},.55)`); rg.addColorStop(1, `rgba(${col[1]},0)`);
  ctx.fillStyle = rg; ctx.fillRect(V.x, V.y, V.w, V.h);
  if (p < 0.1) { ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = `rgba(255,255,255,${0.7 * (1 - p / 0.1)})`; ctx.fillRect(V.x, V.y, V.w, V.h); }
  ctx.restore();
  // 色带上下的描边
  ctx.strokeStyle = col[2]; ctx.lineWidth = 4; cutPath(cy, bh, rot); ctx.stroke();
  ctx.globalAlpha = env * 0.5; ctx.lineWidth = 1.5; cutPath(cy, bh + 22, rot); ctx.stroke();
  ctx.restore();
  // 闪光粒子（神技/潜力技、2 档以上增幅）
  if (big || c.boost >= 2) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 46; i++) {
      const x = V.x + rnd(i * 19 + 8) * V.w, y = cy + bh / 2 + 40 - ((now * (0.05 + rnd(i * 23) * 0.12) + rnd(i * 29 + 9) * (bh + 80)) % (bh + 80));
      const tw = 0.5 + 0.5 * Math.sin(now * 0.012 + i), r = 1.5 + rnd(i * 31) * 2.5;
      ctx.fillStyle = big ? `rgba(255,226,140,${0.8 * tw * env})` : `rgba(255,190,110,${0.7 * tw * env})`;
      ctx.fillRect(x - r, y - r / 3, r * 2, r / 1.5); ctx.fillRect(x - r / 3, y - r, r / 1.5, r * 2);
    }
    ctx.restore();
  }
  // 全身立绘：从行动者一侧冲入，停顿时缓慢推进，退场时继续向前滑出
  const im = CUTIN_IMG[c.key];
  if (im && im.complete && im.naturalWidth) {
    // 立绘按原设计图的身高比例缩放（563 像素 ≈ 最高的角色），矮个子的角色画出来也矮一些
    const ih = (big ? 780 : 720) * (port ? 1.25 : 1) * Math.min(1, im.naturalHeight / 563), iw = ih * im.naturalWidth / im.naturalHeight;
    const fx = hx - dir * (1 - e) * 760 + dir * 40 * p + dir * out * 260, top = cy + (big ? 368 : 356) - ih;
    const drawIm = (x, a, blur) => {
      ctx.save(); ctx.globalAlpha = a;
      if (blur) { ctx.shadowColor = col[2]; ctx.shadowBlur = blur; }
      ctx.translate(x, top); if (!L) ctx.scale(-1, 1);
      ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(im, -iw / 2, 0, iw, ih); ctx.restore();
    };
    const trail = Math.max(0, 1 - p / 0.45);
    if (trail > 0) { drawIm(fx - dir * 110 * (0.4 + trail), 0.16 * trail * env, 0); drawIm(fx - dir * 55 * (0.4 + trail), 0.28 * trail * env, 0); }
    drawIm(fx, (1 - out), big ? 34 : 22);
  } else {
    const s = 300, fx = hx - dir * (1 - e) * 600;
    ctx.save(); ctx.globalAlpha = env; drawFace(c.key, !L, fx - s / 2, cy - s / 2, s); ctx.restore();
  }
  // 技能名：从另一侧滑入
  const e2 = 1 - Math.pow(1 - Math.min(1, Math.max(0, (p - 0.06) / 0.16)), 3);
  const tx = (port ? W / 2 : L ? V.x + V.w * 0.667 : V.x + V.w * 0.333) + dir * (1 - e2) * 500 + dir * 24 * p;
  cy += port ? 470 : 0; // 竖屏时技能名放在立绘下方
  ctx.save(); ctx.globalAlpha = Math.min(e2, 1 - out);
  const tag = big ? (c.lv2 === 1 ? '神技' : '潜力技') : c.boost ? `增幅 ×${c.boost}` : c.job;
  ctx.font = `700 22px ${FONT}`; const tw = ctx.measureText(tag).width + 36;
  ctx.fillStyle = `rgba(${col[1]},.92)`; ctx.beginPath();
  ctx.moveTo(tx - tw / 2 + 8, cy - 98); ctx.lineTo(tx + tw / 2 + 8, cy - 98); ctx.lineTo(tx + tw / 2 - 8, cy - 66); ctx.lineTo(tx - tw / 2 - 8, cy - 66); ctx.closePath(); ctx.fill();
  txt(tag, tx, cy - 82, 22, '#fffaf0', 'center', true, false);
  ctx.font = `700 100px ${FONT}`; const ns = Math.min(big ? 80 : 66, (port ? V.w * 0.9 : 820 * V.w / W) / ctx.measureText(c.zh).width * 100); // 长技能名缩小字号，避免压到立绘
  ctx.shadowColor = col[2]; ctx.shadowBlur = big ? 30 : 18;
  txt(c.zh, tx, cy - 14, ns * (1.15 - 0.15 * e2), '#fff6dc', 'center');
  ctx.shadowBlur = 0;
  ctx.font = `700 ${ns}px ${FONT}`; const lw = Math.min(760, ctx.measureText(c.zh).width + 80);
  const ug = ctx.createLinearGradient(tx - lw / 2, 0, tx + lw / 2, 0);
  ug.addColorStop(0, 'rgba(255,255,255,0)'); ug.addColorStop(0.5, col[2]); ug.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = ug; ctx.fillRect(tx - lw / 2, cy + ns * 0.42, lw, 3);
  txt(c.who, tx, cy + ns * 0.42 + 34, 28, TEAM_COL[c.team], 'center');
  ctx.restore();
  ctx.restore();
}
// ------------------------------------------------------------------ 战斗角色
// 首选用户提供的素材包（ref/kit/，build_kit.py 压成 ref/kit.json 注入为 KIT_SRC）：每人 8 个关键姿态，
// 帧已缩放到 1 像素 = 1/ART_SCALE 个场景单位，带脚底锚点；没有素材包时退回 battle.json 的单张立绘（姿态用变换做），再退回程序像素小人
const KIT = typeof KIT_SRC === 'object' ? KIT_SRC : { chars: {}, fx: {}, sfx: {} };
const KIT_CHAR = {}, KIT_FX = {};
function tinted(c, col) {
  const a = mk(c.width, c.height), ax = a.getContext('2d'); ax.drawImage(c, 0, 0);
  ax.globalCompositeOperation = 'source-atop'; ax.fillStyle = col; ax.fillRect(0, 0, c.width, c.height); return a;
}
function loadCanvas(src) {
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => { const c = mk(im.naturalWidth, im.naturalHeight); c.getContext('2d').drawImage(im, 0, 0); res(c); };
    im.onerror = () => rej(new Error('decode'));
    im.src = src;
  });
}
const BATTLE_ART = {}, BATTLE_FLASH = {}, BATTLE_DIM = {};
let BATTLE_LOADED = false, BATTLE_ERROR = null;
const BATTLE_READY = Promise.all([
  ...Object.entries(KIT.chars || {}).map(([key, { src, f }]) => loadCanvas(src).then(c => {
    KIT_CHAR[key] = { image: c, flash: tinted(c, '#fff5dc'), dim: tinted(c, '#3c304e'), f, w: f.idle[2] / ART_SCALE };
  }, () => { BATTLE_ERROR = `${key} 的素材包角色图解码失败`; })),
  ...Object.entries(KIT.fx || {}).map(([key, fx]) => loadCanvas(fx.src).then(c => { KIT_FX[key] = { ...fx, image: c }; }, () => {})),
  ...Object.entries(typeof BATTLE_SRC === 'object' ? BATTLE_SRC : {}).map(([key, { src, h }]) => loadCanvas(src).then(c => {
    BATTLE_ART[key] = { image: c, height: h, width: h * c.width / c.height };
    BATTLE_FLASH[key] = tinted(c, '#fff5dc'); BATTLE_DIM[key] = tinted(c, '#3c304e');
  }, () => { BATTLE_ERROR = `${key} 的角色图解码失败`; })),
]).then(() => { BATTLE_LOADED = Object.keys(KIT_CHAR).length + Object.keys(BATTLE_ART).length > 0; });

// 当前该显示哪个关键姿态：出招 = 蓄力 → 攻击（停住到命中结束）→ 收招；倒下 = 受击 → 破防 → 倒地；复活倒着放
function kitFrame(a, u, time) {
  const age = Math.max(0, time - (a.motionAt ?? time));
  if (!u.alive) { const d = (time - (a.koAt ?? (time - 600))) / 600; return d < 0.3 ? 'hurt' : d < 0.65 ? 'break' : 'ko'; }
  if (a.reviveAt != null) { const r = (time - a.reviveAt) / 700; if (r < 1) return r < 0.3 ? 'ko' : r < 0.65 ? 'break' : 'idle'; }
  if (a.pose === 'hurt' && age < 320) return 'hurt';
  if (u.brk) return 'break';
  if (a.pose === 'atk') return age < 280 ? 'anticipation' : age < 1150 ? 'attack' : 'recovery';
  if (a.pose === 'cast') return 'cast';
  if (a.pose === 'guard') return 'recovery';
  return 'idle';
}
function drawBattleActor(key, x, y, team, time, a = {}, u = { alive: 1, brk: 0 }, slot = 0) {
  const kit = KIT_CHAR[key];
  if (kit) {
    const dir = team === 0 ? 1 : -1, phase = time * 0.003 + slot * 1.27 + team * 0.6;
    const name = kitFrame(a, u, time), [fx0, fy0, fw, fh, ox, oy] = kit.f[name] || kit.f.idle;
    const age = Math.max(0, time - (a.motionAt ?? time));
    let bob = name === 'idle' || name === 'cast' ? Math.sin(phase) * 0.45 : 0, lean = 0;
    if (name === 'attack') bob = -Math.max(0, Math.sin(Math.min(1, (age - 280) / 300) * Math.PI)) * 1.2;
    if (name === 'hurt' && u.alive) lean = -0.06 * Math.max(0, 1 - age / 320);
    lx.save(); lx.translate(x, y);
    lx.fillStyle = 'rgba(12,7,20,.48)'; lx.beginPath(); lx.ellipse(0, 0, name === 'ko' ? kit.w * 0.42 : kit.w * 0.3, 2.5, 0, 0, Math.PI * 2); lx.fill();
    if (u.alive && a.glow > 0.1) { lx.strokeStyle = TEAM_COL[team]; lx.globalAlpha = 0.7 * a.glow; lx.lineWidth = 0.6; lx.beginPath(); lx.ellipse(0, 0, kit.w * 0.34, 3.5, 0, 0, Math.PI * 2); lx.stroke(); }
    lx.globalAlpha = u.alive ? (a.alpha ?? 1) : 0.85;
    lx.translate(0, bob); lx.scale(dir, 1); lx.rotate(lean);
    lx.imageSmoothingEnabled = true; lx.imageSmoothingQuality = 'high';
    const K = 1 / ART_SCALE, dx = -ox * K, dy = -oy * K, dw = fw * K, dh = fh * K;
    lx.drawImage(kit.image, fx0, fy0, fw, fh, dx, dy, dw, dh);
    if (a.flash > 0) { lx.globalAlpha = Math.min(0.85, a.flash * 0.8); lx.drawImage(kit.flash, fx0, fy0, fw, fh, dx, dy, dw, dh); }
    if (!u.alive) { lx.globalAlpha = 0.42; lx.drawImage(kit.dim, fx0, fy0, fw, fh, dx, dy, dw, dh); }
    lx.restore(); lx.imageSmoothingEnabled = false;
    return;
  }
  drawBattleArt(key, x, y, team, time, a, u, slot);
}
// 素材包特效：12 帧横排，flip 时朝左；先正常叠一层，再用 lighter 叠一层淡的当辉光
// 带地面光圈的（圣光、复活、潜力）底边贴着脚下，其余以中心对准角色身体（脚下往上 lift）
const KIT_GROUND = { light: 1, revive: 1, latent: 1 };
function drawKitFx(name, x, feetY, age, flip, scale = 1, lift = 24) {
  const f = KIT_FX[name]; if (!f || age < 0 || age >= f.dur) return false;
  const i = Math.min(f.n - 1, Math.floor(age / f.dur * f.n)), K = scale / ART_SCALE;
  const dx = -f.ox * K, dy = KIT_GROUND[name] ? -f.h * K : -f.oy * K;
  lx.save(); lx.translate(x, KIT_GROUND[name] ? feetY + 3 : feetY - lift); if (flip) lx.scale(-1, 1);
  lx.imageSmoothingEnabled = true; lx.imageSmoothingQuality = 'high';
  lx.drawImage(f.image, i * f.w, 0, f.w, f.h, dx, dy, f.w * K, f.h * K);
  lx.globalCompositeOperation = 'lighter'; lx.globalAlpha = 0.3;
  lx.drawImage(f.image, i * f.w, 0, f.w, f.h, dx, dy, f.w * K, f.h * K);
  lx.restore(); lx.imageSmoothingEnabled = false;
  return true;
}
function drawBattleArt(key, x, y, team, time, a = {}, u = { alive: 1, brk: 0 }, slot = 0) {
  const art = BATTLE_ART[key];
  if (!art) { lx.drawImage(sprite(key, 'idle', 0, team === 1, null, a.wp), x - SPR_W / 2, y - SPR_H + 2); return; }
  const dir = team === 0 ? 1 : -1, phase = time * 0.003 + slot * 1.27 + team * 0.6;
  const age = Math.max(0, time - (a.motionAt ?? time));
  let bob = Math.sin(phase) * 0.55, lean = 0, sx = 1, sy = 1, dy = 0;
  const pose = u.brk ? 'kneel' : a.pose;
  if (pose === 'atk') {
    const p = Math.min(1, age / 450);
    lean = p < 0.24 ? -0.09 * Math.sin(p / 0.24 * Math.PI) : 0.12 * Math.sin((p - 0.24) / 0.76 * Math.PI);
    dy = -Math.sin(Math.PI * p) * 1.8; sx = 1 + 0.025 * Math.sin(p * Math.PI); bob = 0;
  } else if (pose === 'cast') {
    bob = Math.sin(phase * 1.5) * 1.0 - 1; lean = -0.035; sy = 1.015;
  } else if (pose === 'hurt') {
    const h = Math.max(0, 1 - age / 360); lean = -0.13 * h; sy = 1 - 0.04 * h; bob = 0;
  } else if (pose === 'guard') { lean = -0.07; sy = 0.94; bob = 0; }
  if (u.brk) { lean = 0.16; sy = 0.83; bob = Math.sin(phase) * 0.2; }
  const death = u.alive ? 0 : Math.min(1, Math.max(0, (time - (a.koAt ?? (time - 600))) / 600));
  if (!u.alive) { lean = 0.22 * death; sy = 1 - 0.28 * death; bob = 0; }
  if (a.reviveAt != null) { const p = Math.min(1, Math.max(0, (time - a.reviveAt) / 700)); sy *= 0.72 + 0.28 * p; }
  lx.save(); lx.translate(x, y);
  lx.fillStyle = 'rgba(12,7,20,.48)'; lx.beginPath(); lx.ellipse(0, 0, art.width * 0.28, 2.5, 0, 0, Math.PI * 2); lx.fill();
  if (u.alive && a.glow > 0.1) { lx.strokeStyle = TEAM_COL[team]; lx.globalAlpha = 0.7 * a.glow; lx.lineWidth = 0.6; lx.beginPath(); lx.ellipse(0, 0, art.width * 0.32, 3.5, 0, 0, Math.PI * 2); lx.stroke(); }
  lx.globalAlpha = u.alive ? (a.alpha ?? 1) : 0.64 - 0.2 * death;
  lx.translate(0, bob + dy); lx.scale(dir, 1); lx.rotate(lean); lx.scale(sx, sy);
  lx.imageSmoothingEnabled = false;
  lx.drawImage(art.image, -art.width / 2, -art.height, art.width, art.height);
  if (a.flash > 0) { lx.globalAlpha = Math.min(0.85, a.flash * 0.8); lx.drawImage(BATTLE_FLASH[key], -art.width / 2, -art.height, art.width, art.height); }
  if (!u.alive) { lx.globalAlpha = 0.48; lx.drawImage(BATTLE_DIM[key], -art.width / 2, -art.height, art.width, art.height); }
  lx.restore();
}

function portrait(key, flip) {
  const k = 'P' + key + flip;
  if (sprCache[k]) return sprCache[k];
  const s = sprite(key, 'idle', 0, flip), c = mk(22, 22), x = c.getContext('2d');
  const sh = key === 'ochette' ? 4 : 0;
  x.drawImage(s, flip ? SPR_W - 34 - SPR_PAD : 12 + SPR_PAD, 5 + sh, 22, 22, 0, 0, 22, 22);
  return (sprCache[k] = c);
}

// ------------------------------------------------------------------ 场景（立体布景）
const VP = { x: 240, y: 30 };
function drawFar() {
  const c = mk(LW, LH), x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, 130);
  g.addColorStop(0, '#1b2350'); g.addColorStop(0.45, '#5a4a7a'); g.addColorStop(0.8, '#e08a5a'); g.addColorStop(1, '#ffc68a');
  x.fillStyle = g; x.fillRect(0, 0, LW, 140);
  // 星星
  for (let i = 0; i < 70; i++) { x.fillStyle = `rgba(255,255,240,${0.3 + rnd(i) * 0.6})`; x.fillRect(rnd(i + 99) * LW | 0, rnd(i + 7) * 50 | 0, 1, 1); }
  // 太阳
  const sg = x.createRadialGradient(330, 112, 2, 330, 112, 60); sg.addColorStop(0, 'rgba(255,240,200,1)'); sg.addColorStop(0.2, 'rgba(255,200,140,.8)'); sg.addColorStop(1, 'rgba(255,160,100,0)');
  x.fillStyle = sg; x.fillRect(240, 40, 180, 120);
  // 云
  x.fillStyle = 'rgba(255,190,170,.55)';
  for (let i = 0; i < 9; i++) { const cx = rnd(i * 3) * LW, cy = 35 + rnd(i * 5) * 50, w = 30 + rnd(i * 11) * 50; x.fillRect(cx | 0, cy | 0, w | 0, 2); x.fillRect(cx + 6 | 0, cy - 2 | 0, w * 0.6 | 0, 2); }
  // 远山
  function ridge(y0, amp, col, seed) {
    x.fillStyle = col; x.beginPath(); x.moveTo(0, 140);
    for (let i = 0; i <= LW; i += 4) x.lineTo(i, y0 - amp * (0.5 + 0.5 * Math.sin(i * 0.02 + seed) * Math.cos(i * 0.007 + seed * 2)) - rnd(i + seed * 100) * 3);
    x.lineTo(LW, 140); x.fill();
  }
  ridge(108, 34, '#6a5a88', 1); ridge(116, 22, '#4c4470', 4);
  // 远处城堡剪影
  x.fillStyle = '#3a3460';
  x.fillRect(70, 78, 30, 40); x.fillRect(64, 70, 8, 48); x.fillRect(98, 66, 8, 52); x.fillRect(80, 60, 10, 20);
  for (const [tx, ty] of [[64, 70], [98, 66], [80, 60]]) { x.beginPath(); x.moveTo(tx - 1, ty); x.lineTo(tx + 4 + (tx === 80 ? 1 : 0), ty - 10); x.lineTo(tx + 9 + (tx === 80 ? 2 : 0), ty); x.fill(); }
  x.fillStyle = '#ffd27a'; for (const [wx, wy] of [[67, 80], [101, 74], [84, 66], [76, 92], [90, 96]]) x.fillRect(wx, wy, 1, 2);
  ridge(124, 12, '#3b3658', 7);
  // 远处树林
  for (let i = 0; i < 60; i++) { const tx = i * 8 + rnd(i) * 6, th = 10 + rnd(i + 3) * 10; x.fillStyle = i % 2 ? '#2e2a48' : '#332e50'; x.beginPath(); x.moveTo(tx, 132); x.lineTo(tx + 4, 132 - th); x.lineTo(tx + 8, 132); x.fill(); }
  return c;
}

function floorPt(u, v) { // u: -1..1 横向, v: 0(远)..1(近)
  const y = 108 + v * v * 0 + v * 170;
  const half = 140 + v * 330;
  return [VP.x + u * half, y];
}
function drawMid() {
  const c = mk(LW, LH), x = c.getContext('2d');
  // 后墙（废墟竞技场）
  x.fillStyle = '#4a4058'; x.fillRect(0, 70, LW, 42);
  for (let r = 0; r < 7; r++) for (let i = 0; i < 40; i++) {
    const bx = i * 13 + (r % 2) * 6, by = 70 + r * 6;
    x.fillStyle = mix('#5a4e6a', '#6e6078', rnd(i * 7 + r * 131)); x.fillRect(bx, by, 12, 5);
  }
  // 拱门
  for (let i = 0; i < 6; i++) {
    const ax = 24 + i * 80; x.fillStyle = '#231c30';
    x.fillRect(ax, 84, 30, 28); x.beginPath(); x.arc(ax + 15, 84, 15, Math.PI, 0); x.fill();
    x.fillStyle = 'rgba(255,170,110,.18)'; x.fillRect(ax + 2, 96, 26, 16);
  }
  // 墙顶残缺
  x.fillStyle = '#3a3048'; for (let i = 0; i < LW; i += 6) { const h = 2 + rnd(i) * 9; x.fillRect(i, 70 - h, 6, h); }
  // 石柱
  for (const px of [20, 140, 330, 455]) {
    const hgt = 70 + rnd(px) * 25;
    x.fillStyle = '#7b6e86'; x.fillRect(px, 112 - hgt, 16, hgt);
    x.fillStyle = '#958aa0'; x.fillRect(px, 112 - hgt, 3, hgt);
    x.fillStyle = '#5a4e66'; x.fillRect(px + 12, 112 - hgt, 4, hgt);
    x.fillStyle = '#8c809a'; x.fillRect(px - 3, 112 - hgt - 4, 22, 5); x.fillRect(px - 3, 108, 22, 5);
    // 藤蔓
    x.fillStyle = '#3e6a3a'; for (let k = 0; k < 14; k++) x.fillRect(px + (rnd(px + k) * 16 | 0), 112 - hgt + k * 4, 2, 3);
  }
  // 旗帜
  for (const [bx, col] of [[90, '#2f5fb0'], [380, '#b0302f']]) {
    x.fillStyle = col; x.fillRect(bx, 64, 14, 30); x.fillStyle = shade(col, -0.3); x.fillRect(bx + 11, 64, 3, 30);
    x.beginPath(); x.moveTo(bx, 94); x.lineTo(bx + 7, 88); x.lineTo(bx + 14, 94); x.fillStyle = '#4a4058'; x.fill();
    x.fillStyle = '#e8c860'; x.fillRect(bx + 5, 72, 4, 4); x.fillRect(bx, 64, 14, 1);
  }
  // 地面石板（透视）
  const rows = 12, cols = 18;
  for (let r = 0; r < rows; r++) for (let q = 0; q < cols; q++) {
    const v0 = r / rows, v1 = (r + 1) / rows, u0 = -1 + 2 * q / cols, u1 = -1 + 2 * (q + 1) / cols;
    const p = [floorPt(u0, v0), floorPt(u1, v0), floorPt(u1, v1), floorPt(u0, v1)];
    const n = rnd(r * 37 + q * 11);
    let base = mix('#8a7a74', '#a4928a', n);
    const dc = Math.abs(u0 + 1 / cols) * 0.9 + 0.1;
    if (dc > 0.75 && n > 0.5) base = mix(base, '#5f7a46', 0.6);
    base = mix(base, '#3a3044', 0.35 * (1 - v0));
    x.fillStyle = base; x.beginPath(); x.moveTo(...p[0]); for (const pp of p.slice(1)) x.lineTo(...pp); x.closePath(); x.fill();
    x.strokeStyle = 'rgba(40,28,40,.55)'; x.lineWidth = 1; x.stroke();
    if (n > 0.85) { x.fillStyle = 'rgba(40,30,40,.35)'; const cx = (p[0][0] + p[2][0]) / 2, cy = (p[0][1] + p[2][1]) / 2; x.fillRect(cx | 0, cy | 0, 3, 1); x.fillRect(cx + 2 | 0, cy + 1 | 0, 2, 1); }
  }
  // 中央纹章圆环
  x.strokeStyle = 'rgba(230,200,140,.35)'; x.lineWidth = 2;
  x.beginPath(); x.ellipse(240, 168, 120, 30, 0, 0, Math.PI * 2); x.stroke();
  x.beginPath(); x.ellipse(240, 168, 80, 20, 0, 0, Math.PI * 2); x.stroke();
  for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; x.fillStyle = 'rgba(230,200,140,.4)'; x.fillRect(240 + Math.cos(a) * 100 | 0, 168 + Math.sin(a) * 25 | 0, 3, 2); }
  // 草丛边缘
  for (let i = 0; i < 160; i++) {
    const side = i % 2, gx = side ? LW - rnd(i) * 70 : rnd(i) * 70, gy = 112 + rnd(i + 50) * 150;
    x.fillStyle = ['#3d6b34', '#4f8a3e', '#2f5228'][i % 3]; x.fillRect(gx | 0, gy | 0, 2, 3); x.fillRect(gx + 1 | 0, gy - 2 | 0, 1, 2);
  }
  // 火把柱
  for (const [tx, ty] of TORCHES) { x.fillStyle = '#3a2c2a'; x.fillRect(tx - 1, ty, 3, 30); x.fillStyle = '#6a5040'; x.fillRect(tx - 3, ty - 2, 7, 3); }
  return c;
}
const TORCHES = [[60, 96], [420, 96], [196, 82], [284, 82]];

function drawFore() {
  const c = mk(LW, LH), x = c.getContext('2d');
  function bush(cx, cy, r, col) { x.fillStyle = col; for (let i = 0; i < 40; i++) { const a = rnd(cx + i) * Math.PI, d = rnd(cy + i * 3) * r; x.fillRect(cx + Math.cos(a) * d * 1.6 | 0, cy - Math.sin(a) * d | 0, 6, 5); } }
  bush(18, 272, 40, '#1d3320'); bush(40, 278, 30, '#2a4a2a'); bush(462, 272, 42, '#1d3320'); bush(440, 280, 28, '#2a4a2a');
  // 顶部垂下的枝叶
  x.fillStyle = '#1a2a1e';
  for (let i = 0; i < 30; i++) { const bx = rnd(i * 9) * 120, len = 6 + rnd(i) * 26; x.fillRect(bx | 0, 0, 3, len | 0); x.fillRect(LW - bx | 0, 0, 3, len * 0.8 | 0); }
  return c;
}

// 预渲染：远景模糊（景深），近景模糊，中景清晰
const farC = drawFar(), midC = drawMid(), foreC = drawFore();
function blurred(src, px) {
  const c = mk(W, H), x = c.getContext('2d'); x.imageSmoothingEnabled = false;
  x.filter = `blur(${px}px)`; x.drawImage(src, -6, -6, W + 12, H + 12); return c;
}
const farBlur = blurred(farC, 5), foreBlur = blurred(foreC, 7);
const grade = (() => {
  const c = mk(W, H), x = c.getContext('2d');
  // 光束
  x.globalCompositeOperation = 'screen';
  for (let i = 0; i < 4; i++) {
    const g = x.createLinearGradient(0, 0, W * 0.5, H);
    g.addColorStop(0, 'rgba(255,210,150,0.10)'); g.addColorStop(1, 'rgba(255,210,150,0)');
    x.fillStyle = g; x.beginPath(); const s = 200 + i * 230;
    x.moveTo(s, 0); x.lineTo(s + 90, 0); x.lineTo(s - 260 + 90, H); x.lineTo(s - 330, H); x.fill();
  }
  x.globalCompositeOperation = 'source-over';
  // 暗角
  const v = x.createRadialGradient(W / 2, H * 0.48, H * 0.35, W / 2, H / 2, H * 0.95);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(10,5,20,0.65)');
  x.fillStyle = v; x.fillRect(0, 0, W, H);
  return c;
})();

// ------------------------------------------------------------------ 战斗状态
const NT = [M.picks[0].length || 4, M.picks[1].length || 4];
function homePos(team, i) {
  const n = NT[team], step = n > 1 ? Math.min(35, 105 / (n - 1)) : 0;
  // 两侧要留给状态栏，角色站在中间偏下，前后错开
  const y = 128 + i * step;
  const x = team === 0 ? 195 - i * step * 0.47 : 285 + i * step * 0.47;
  return [x, y];
}
let D = null;           // 当前显示状态
let A = null;           // 每个单位的动画状态
let order = [], acted = new Set(), roundNo = 0, BAG = [{}, {}];
let banner = null, bigText = null, effects = [], texts = [], loCard = null;
let shakeFx = null, flashFx = null;
// 增幅档位配色：[文字/火花, 核心, 外焰]，1 档金白、2 档橙、3 档赤金
const BOOST_COL = { 1: ['#fff4b8', '#ffe27a', '#ffc860'], 2: ['#ffd890', '#ffa83a', '#ff7a24'], 3: ['#ffc8a0', '#ff7a2e', '#ff3a1a'] };
let pickShown = [[], []];

const WEAPON_SET = { sword: 1, polearm: 1, dagger: 1, axe: 1, bow: 1, staff: 1 };
// 这次行动用的武器：普通攻击看所选武器，技能看它打出的伤害类型；魔法等不用武器的行动返回 null，手上武器保持不变
function actWeapon(evs, k, e) {
  const ws = TR[M.picks[e.u[0]][e.u[1]]].weapons;
  let ty = e.s === 'attack' ? e.w : null;
  if (!ty) for (let j = k + 1; j < evs.length && evs[j].e !== 'skill'; j++) if (evs[j].e === 'hit' && evs[j].ty in WEAPON_SET) { ty = evs[j].ty; break; }
  return ty && ws.includes(ty) ? ty : null;
}
// 增益/减益/状态：{名字: 剩余回合}（旧回放只有名字，回合记 0 不显示）
const kv = a => Object.fromEntries((a || []).map(s => Array.isArray(s) ? s : [s, 0]));
function snapState(fi) {
  // 找到 fi 及之前最近的战斗帧
  let f = null;
  for (let i = fi; i >= 0; i--) if (F[i].u) { f = F[i]; break; }
  if (!f) { D = null; return; }
  D = f.u.map((team, t) => team.map((u, i) => ({
    key: M.picks[t][i], hp: u[0], sp: u[1], bp: u[2], sh: u[3], brk: u[4], alive: u[5], lat: u[6],
    up: kv(u[7]), down: kv(u[8]), st: kv(u[9]), tier: u[10], mat: u[11],
  })));
  if (!A) A = D.map((team, t) => team.map(() => ({ dx: 0, dy: 0, pose: 'idle', flash: 0, shake: 0, alpha: 1, glow: 0, bl: 0, ba: 0 })));
  for (const team of A) for (const a of team) { delete a.motionAt; delete a.koAt; delete a.reviveAt; }
  for (const team of A) for (const a of team) Object.assign(a, { dx: 0, dy: 0, pose: 'idle', flash: 0, shake: 0, glow: 0, bl: 0, ba: 0 });
  // 手上的武器 = 截至这一帧最后一次用武器的行动
  A.forEach((team, t) => team.forEach((a, i) => { a.wp = TR[D[t][i].key].weapons[0]; }));
  for (let i = 0; i <= fi && i < F.length; i++) F[i].ev.forEach((e, k) => { if (e.e === 'skill' && e.u) { const w = actWeapon(F[i].ev, k, e); if (w) A[e.u[0]][e.u[1]].wp = w; } });
  BAG = (f.bag || BAGS).map(b => ({ ...b }));
  roundNo = f.r;
  // 本回合顺序：往回找最近的 order 事件
  order = []; acted = new Set();
  outer: for (let i = fi; i >= 0; i--) {
    const evs = F[i].ev;
    for (let k = evs.length - 1; k >= 0; k--) {
      if (evs[k].e === 'order') { order = evs[k].o; break outer; }
    }
  }
  // 已行动 = 不在剩余队列里的
  const q = new Set((f.q || []).map(r => r.join()));
  for (const r of order) if (!q.has(r.join())) acted.add(r.join());
  if (f.cur) acted.delete(f.cur.join());
}

// ------------------------------------------------------------------ 音效（全部用 WebAudio 现场合成，原创，不含原作音频）
const SFX = (() => {
  let ac = null, out = null, nbuf = null, on = true, last = {};
  const bufs = {}, BUF_GAIN = { heal: 1.9, light: 1.9, revive: 1.9 };
  try { on = localStorage.getItem('op_sfx') !== '0'; } catch (e) {}
  function init() {
    if (!ac) {
      try {
        ac = new (window.AudioContext || window.webkitAudioContext)();
        const comp = ac.createDynamicsCompressor(); comp.connect(ac.destination);
        out = ac.createGain(); out.gain.value = 0.55; out.connect(comp);
        // 简单混响：两路反馈延迟，给魔法和钟声一点空间感
        const send = ac.createGain(); send.gain.value = 0.22; out.connect(send);
        for (const [t, g] of [[0.083, 0.42], [0.127, 0.36]]) {
          const d = ac.createDelay(1); d.delayTime.value = t; const fb = ac.createGain(); fb.gain.value = g;
          const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2600;
          send.connect(d); d.connect(lp); lp.connect(fb); fb.connect(d); lp.connect(comp);
        }
        nbuf = ac.createBuffer(1, ac.sampleRate * 1.5, ac.sampleRate);
        const ch = nbuf.getChannelData(0); for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
        // 素材包里的录制音效（武器、属性、治疗、复活、破防、潜力），解码好之前先用合成音
        for (const [k, src] of Object.entries(KIT.sfx || {})) {
          try {
            const bin = atob(src.slice(src.indexOf(',') + 1)), u8 = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
            ac.decodeAudioData(u8.buffer, b => { bufs[k] = b; }, () => {});
          } catch (e) {}
        }
      } catch (e) { ac = null; }
    }
    if (!ac) return;
    // iOS Safari 只在 touchend/click 这类手势里允许解锁音频：解锁时恢复上下文并播一段静音，状态变化时刷新按钮
    if (!ac.onstatechange) ac.onstatechange = () => onState && onState();
    if (ac.state !== 'running') { try { const p = ac.resume(); if (p && p.then) p.then(() => onState && onState(), () => {}); } catch (e) {} }
    try { const b = ac.createBufferSource(); b.buffer = ac.createBuffer(1, 1, 22050); b.connect(ac.destination); b.start(0); } catch (e) {}
  }
  let onState = null;
  const T = () => ac.currentTime;
  function env(g, t, a, d, v) { g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d); }
  // 振荡器：f 起始频率，f2 结束频率
  function tone(f, d, o = {}) {
    const t = T() + (o.at || 0), osc = ac.createOscillator(), g = ac.createGain();
    osc.type = o.type || 'sine'; osc.frequency.setValueAtTime(f, t);
    if (o.f2) osc.frequency.exponentialRampToValueAtTime(o.f2, t + d);
    if (o.det) osc.detune.value = o.det;
    env(g, t, o.a || 0.005, d, o.v || 0.2); osc.connect(g); g.connect(out); osc.start(t); osc.stop(t + d + 0.05);
  }
  // 噪声：经过滤波器，频率从 f 扫到 f2
  function noise(d, o = {}) {
    const t = T() + (o.at || 0), src = ac.createBufferSource(), flt = ac.createBiquadFilter(), g = ac.createGain();
    src.buffer = nbuf; flt.type = o.ft || 'bandpass'; flt.Q.value = o.q || 1;
    flt.frequency.setValueAtTime(o.f || 1500, t); if (o.f2) flt.frequency.exponentialRampToValueAtTime(o.f2, t + d);
    env(g, t, o.a || 0.004, d, o.v || 0.3); src.connect(flt); flt.connect(g); g.connect(out);
    src.start(t, Math.random() * 0.5); src.stop(t + d + 0.05);
  }
  // FM 钟声：调制比不取整数，得到金属/水晶质感的泛音，index 随时间衰减
  function bell(f, d, o = {}) {
    const t = T() + (o.at || 0), car = ac.createOscillator(), mod = ac.createOscillator(), mg = ac.createGain(), g = ac.createGain();
    car.frequency.value = f; mod.frequency.value = f * (o.ratio || 1.4);
    mg.gain.setValueAtTime(f * (o.index || 3), t); mg.gain.exponentialRampToValueAtTime(f * 0.05, t + d * 0.8);
    mod.connect(mg); mg.connect(car.frequency); env(g, t, 0.002, d, o.v || 0.1); car.connect(g); g.connect(out);
    car.start(t); mod.start(t); car.stop(t + d + 0.05); mod.stop(t + d + 0.05);
  }
  const arp = (notes, step, d, o = {}) => notes.forEach((f, i) => tone(f, d, { ...o, at: (o.at || 0) + i * step }));
  const LIB = {
    // 武器
    sword() { noise(0.16, { f: 5200, f2: 1400, q: 2.5, v: 0.32 }); tone(1900, 0.12, { type: 'triangle', f2: 1300, v: 0.05, at: 0.02 }); },
    polearm() { noise(0.1, { f: 900, f2: 3200, q: 3, v: 0.3 }); tone(220, 0.1, { type: 'square', f2: 110, v: 0.06, at: 0.06 }); },
    dagger() { noise(0.07, { f: 6500, f2: 3000, q: 4, v: 0.26 }); noise(0.06, { f: 7000, f2: 3500, q: 4, v: 0.18, at: 0.07 }); },
    axe() { noise(0.2, { f: 700, f2: 250, q: 1.2, v: 0.42 }); tone(95, 0.22, { type: 'sine', f2: 45, v: 0.4 }); },
    bow() { tone(1300, 0.06, { type: 'triangle', f2: 600, v: 0.08 }); noise(0.18, { f: 2500, f2: 6000, q: 6, v: 0.18, at: 0.02 }); noise(0.05, { f: 1200, q: 1, v: 0.3, at: 0.18 }); },
    staff() { tone(160, 0.14, { type: 'triangle', f2: 70, v: 0.32 }); noise(0.08, { f: 800, q: 1, v: 0.22 }); },
    // 属性
    fire() { noise(0.55, { ft: 'lowpass', f: 300, f2: 2200, v: 0.38, a: 0.05 }); noise(0.4, { f: 600, f2: 150, q: 0.8, v: 0.3, at: 0.15 }); tone(70, 0.4, { f2: 40, v: 0.3, at: 0.05 }); },
    ice() { arp([2093, 2637, 3136, 3951], 0.045, 0.35, { type: 'sine', v: 0.08 }); noise(0.3, { ft: 'highpass', f: 5000, v: 0.12, a: 0.02 }); tone(1046, 0.4, { type: 'triangle', v: 0.05, det: 7 }); },
    lightning() { noise(0.08, { ft: 'highpass', f: 2500, v: 0.5 }); tone(1400, 0.25, { type: 'sawtooth', f2: 90, v: 0.12 }); noise(0.6, { ft: 'lowpass', f: 400, f2: 80, v: 0.45, at: 0.06 }); },
    wind() { noise(0.6, { f: 400, f2: 2600, q: 5, v: 0.32, a: 0.12 }); noise(0.5, { f: 2000, f2: 600, q: 6, v: 0.18, at: 0.15, a: 0.1 }); },
    light() { arp([1318, 1760, 2217, 2637], 0.05, 0.6, { type: 'sine', v: 0.08 }); tone(659, 0.8, { type: 'triangle', v: 0.06, a: 0.05 }); noise(0.4, { ft: 'highpass', f: 6000, v: 0.08, a: 0.1 }); },
    dark() { tone(110, 0.7, { type: 'sawtooth', f2: 55, v: 0.12, a: 0.06 }); tone(116, 0.7, { type: 'sawtooth', f2: 52, v: 0.1, a: 0.06 }); noise(0.6, { ft: 'lowpass', f: 900, f2: 200, v: 0.25, a: 0.08 }); },
    // 系统
    cast() { arp([523, 784, 1046], 0.06, 0.4, { type: 'triangle', v: 0.06 }); noise(0.5, { f: 1500, f2: 4000, q: 8, v: 0.06, a: 0.2 }); },
    item() { tone(380, 0.06, { type: 'square', f2: 900, v: 0.05 }); noise(0.05, { f: 1800, q: 2, v: 0.12 }); arp([988, 1319, 1976], 0.07, 0.35, { type: 'triangle', v: 0.07, at: 0.12 }); bell(2637, 0.4, { ratio: 2, index: 1, v: 0.03, at: 0.3 }); },
    weak() { tone(1760, 0.18, { type: 'square', v: 0.035 }); tone(2637, 0.22, { type: 'sine', v: 0.06, at: 0.03 }); },
    crit() { tone(80, 0.25, { f2: 40, v: 0.45 }); noise(0.12, { ft: 'highpass', f: 3000, v: 0.3 }); },
    miss() { noise(0.22, { f: 900, f2: 2400, q: 3, v: 0.16, a: 0.04 }); },
    chip() { tone(2400, 0.07, { type: 'square', v: 0.03 }); tone(3200, 0.08, { type: 'sine', v: 0.05, at: 0.02 }); },
    break() {
      tone(55, 0.6, { f2: 30, v: 0.6 }); noise(0.5, { ft: 'highpass', f: 2500, f2: 6000, v: 0.4 });
      for (let i = 0; i < 7; i++) tone(2000 + Math.random() * 3000, 0.12 + Math.random() * 0.2, { type: 'triangle', v: 0.04, at: 0.02 + i * 0.03 });
      tone(392, 0.4, { type: 'square', v: 0.05, at: 0.08 }); tone(196, 0.5, { type: 'square', v: 0.05, at: 0.08 });
    },
    boostTick(i) { // 每花 1 BP 一声水晶"叮"，一档比一档高、一档比一档亮
      const F = [1318.5, 1760, 2349.3][Math.min(i, 2)];
      bell(F, 0.6 + i * 0.15, { ratio: 1.41, index: 2.2 + i * 0.6, v: 0.11 + i * 0.015 });
      bell(F * 2, 0.3, { ratio: 2.76, index: 1.2, v: 0.03 + i * 0.01, at: 0.005 });
      tone(F / 2, 0.4, { type: 'triangle', v: 0.05 });
      noise(0.12 + i * 0.03, { f: 2500 + i * 800, f2: 9500, q: 3, v: 0.13 + i * 0.03, a: 0.02 });
    },
    boostBurst(n) { // 增幅完成时按档位释放：1 档轻、2 档带低音冲击、3 档是整套爆发
      noise(0.3 + n * 0.12, { f: 700, f2: 5200 + n * 800, q: 1.6, v: 0.12 + n * 0.05, a: 0.08 });
      arp([2637, 3520, 4434].slice(0, n), 0.05, 0.5 + n * 0.15, { type: 'sine', v: 0.035 + n * 0.01, at: 0.05 });
      if (n >= 2) {
        tone(130, 0.4 + n * 0.1, { f2: 55, v: 0.32 + (n - 2) * 0.15 });
        tone(196, 0.55, { type: 'sawtooth', f2: 392 + n * 120, v: 0.03, a: 0.15 });
        noise(0.35, { ft: 'lowpass', f: 300, f2: 1600, v: 0.18, a: 0.05 });
      }
      if (n >= 3) {
        tone(62, 0.9, { f2: 32, v: 0.5 });
        noise(0.9, { ft: 'lowpass', f: 180, f2: 3800, v: 0.32, a: 0.25 });
        tone(110, 0.8, { type: 'sawtooth', f2: 440, v: 0.05, a: 0.3 }); tone(165, 0.8, { type: 'sawtooth', f2: 660, v: 0.04, a: 0.3 });
        for (const [f, at] of [[880, 0.28], [1318.5, 0.32], [1760, 0.36], [2217, 0.4]]) bell(f, 1.2, { at, ratio: 1.41, index: 1.6, v: 0.05 });
        for (let k = 0; k < 10; k++) noise(0.03, { ft: 'highpass', f: 4000 + Math.random() * 3000, v: 0.12, at: 0.1 + Math.random() * 0.6 });
      }
    },
    cutin(lv, n) { // 特写切入："唰"的一下风切 + 金属光；神技/潜力技再叠一层上扬和弦和钟声
      noise(0.42, { f: 500, f2: 5200, q: 1.3, v: 0.26, a: 0.14 });
      noise(0.18, { ft: 'highpass', f: 6000, v: 0.12, at: 0.12 });
      tone(96, 0.32, { f2: 48, v: 0.28, at: 0.12 });
      bell(2637, 0.6, { ratio: 2.01, index: 1.4, v: 0.045, at: 0.14 });
      if (n >= 2 || lv === 2) tone(147, 0.7, { type: 'sawtooth', f2: 294, v: 0.04, a: 0.2, at: 0.1 });
      if (lv === 2) {
        tone(73, 1.1, { f2: 36, v: 0.4, at: 0.12 });
        for (const [f, at] of [[784, 0.2], [1046.5, 0.26], [1318.5, 0.32], [1568, 0.38], [2093, 0.46]]) bell(f, 1.3, { at, ratio: 1.41, index: 1.8, v: 0.05 });
        noise(1.0, { ft: 'lowpass', f: 250, f2: 4200, v: 0.22, a: 0.3, at: 0.15 });
      }
    },
    latent() { tone(110, 1.0, { type: 'sawtooth', f2: 440, v: 0.1, a: 0.3 }); tone(165, 1.0, { type: 'sawtooth', f2: 660, v: 0.07, a: 0.3 }); noise(0.9, { f: 300, f2: 6000, q: 1.5, v: 0.2, a: 0.4 }); arp([880, 1318, 1760], 0.07, 0.5, { type: 'triangle', v: 0.06, at: 0.75 }); },
    heal() { arp([784, 988, 1175, 1568], 0.07, 0.5, { type: 'sine', v: 0.09 }); noise(0.5, { ft: 'highpass', f: 5000, v: 0.05, a: 0.15 }); },
    revive() { arp([523, 659, 784, 1046, 1318, 1568], 0.08, 0.8, { type: 'triangle', v: 0.07 }); tone(262, 1.2, { type: 'sine', v: 0.08, a: 0.2 }); },
    up() { tone(500, 0.3, { type: 'triangle', f2: 1200, v: 0.07 }); tone(750, 0.3, { type: 'sine', f2: 1800, v: 0.04, at: 0.05 }); },
    down() { tone(900, 0.35, { type: 'triangle', f2: 300, v: 0.07 }); tone(600, 0.35, { type: 'sawtooth', f2: 200, v: 0.025 }); },
    status() { arp([660, 990], 0.06, 0.25, { type: 'triangle', v: 0.06 }); },
    poison() { for (let i = 0; i < 4; i++) tone(300 + Math.random() * 300, 0.08, { type: 'sine', f2: 700 + Math.random() * 300, v: 0.07, at: i * 0.06 }); },
    defend() { tone(180, 0.2, { type: 'triangle', f2: 140, v: 0.2 }); tone(1200, 0.3, { type: 'sine', v: 0.04, at: 0.03 }); },
    ko() { tone(440, 0.6, { type: 'triangle', f2: 110, v: 0.12 }); noise(0.4, { ft: 'lowpass', f: 500, f2: 100, v: 0.25, at: 0.2 }); },
    turn() { tone(1568, 0.05, { type: 'square', v: 0.02 }); },
    round() { arp([392, 523], 0.08, 0.35, { type: 'triangle', v: 0.07 }); },
    pick() { arp([660, 880], 0.05, 0.12, { type: 'square', v: 0.03 }); },
    recover() { arp([1046, 1318, 1568], 0.04, 0.3, { type: 'sine', v: 0.05 }); },
    victory() { // 原创的短号角：大调分解和弦 + 收尾和弦
      const N = [392, 523, 659, 784, 659, 784]; const D = [0.12, 0.12, 0.12, 0.3, 0.12, 0.9];
      let t = 0; N.forEach((f, i) => { tone(f, D[i], { type: 'square', v: 0.05, at: t }); tone(f / 2, D[i], { type: 'triangle', v: 0.07, at: t }); t += D[i] * (i === 3 ? 0.9 : 1); });
      for (const f of [523, 659, 784, 1046]) tone(f, 1.3, { type: 'triangle', v: 0.045, at: t - 0.9, a: 0.02 });
    },
  };
  function play(name, ...args) {
    if (CAP.on || !on || !ac || ac.state !== 'running') return;
    if (!LIB[name]) name = 'staff';
    const k = name, n = performance.now();
    if (last[k] && n - last[k] < 45) return; // 多段攻击时避免同一音效叠爆
    last[k] = n;
    try {
      if (bufs[name]) { const src = ac.createBufferSource(), g = ac.createGain(); src.buffer = bufs[name]; g.gain.value = 0.75 * (BUF_GAIN[name] || 1); src.connect(g); g.connect(out); src.start(); }
      else LIB[name](...args);
    } catch (e) {}
  }
  function toggle() { on = !on; try { localStorage.setItem('op_sfx', on ? '1' : '0'); } catch (e) {} if (on) init(); return on; }
  for (const ev of ['pointerdown', 'touchstart', 'touchend', 'mousedown', 'click', 'keydown']) window.addEventListener(ev, () => { if (on) init(); }, true);
  // 切回页面时音频可能被系统挂起（iOS 显示为 interrupted），下一次点击会重新解锁
  document.addEventListener('visibilitychange', () => { if (!document.hidden && on && ac && ac.state !== 'running') { try { ac.resume(); } catch (e) {} } });
  return { play, toggle, init, get on() { return on; }, get ready() { return !!ac && ac.state === 'running'; }, set onState(f) { onState = f; } };
})();

// ------------------------------------------------------------------ 时间线
let cur = 0, steps = [], si = 0, st = 0, playing = false, speed = 1;
const seek = document.getElementById('seek'); seek.max = F.length - 1;

function nm(ref) { return TR[M.picks[ref[0]][ref[1]]].name; }
function skillName(s) { const k = SKN[s]; return k ? k : { name: s, zh: s }; }
function U(ref) { return D[ref[0]][ref[1]]; }
function An(ref) { return A[ref[0]][ref[1]]; }
function scrPos(ref, dy = 0) { const [x, y] = homePos(ref[0], ref[1]); const a = An(ref); return toScr(x + a.dx, y + a.dy + dy); }

function addText(ref, text, color, size = 34, dy = -30, dur = 1100) {
  const [x, y] = scrPos(ref, dy);
  texts.push({ x: x + (rng() - 0.5) * 30, y, text, color, size, t0: now, dur });
}
function fx(type, ref, extra = {}) {
  const [x, y] = homePos(ref[0], ref[1]); const a = An(ref);
  effects.push({ type, x: x + a.dx, y: y + a.dy, t0: now, dur: extra.dur || 500, ...extra });
}

function plan(fi) {
  const fr = F[fi], L = [];
  const add = (d, on, upd) => L.push({ d, on, upd });
  let actor = null, skill = null;
  const evs = fr.ev;
  for (let k = 0; k < evs.length; k++) {
    const e = evs[k];
    switch (e.e) {
      case 'pick':
        add(900, () => { pickShown[e.team] = pickShown[e.team].concat(e.picks); SFX.play('pick'); });
        break;
      case 'loadout':
        // 盲配结束：双方配置同时公开（两条事件只展示一次）
        if (e.team === 0 && !CLEAN) add(5200, () => { loCard = { t0: now, dur: 5200 }; SFX.play('pick'); });
        break;
      case 'sup': {
        const s = SUPN[e.k];
        if (s) add(e.k === 'rise_again' ? 500 : 260, () => { addText(e.u, '支援·' + s.zh, '#ffd98a', 22, -84, 1300); An(e.u).glow = 1; });
        break;
      }
      case 'round':
        add(700, () => { if (!D) snapState(fi); roundNo = e.r; acted = new Set(); bigText = { text: `第 ${e.r} 回合`, t0: now, dur: 700 * 1.0, col: '#f4e2b0', ui: 1 }; SFX.play('round'); });
        break;
      case 'order':
        add(10, () => { order = e.o; acted = new Set(); });
        break;
      case 'recover':
        add(350, () => { const u = U(e.t); u.brk = 0; u.sh = TR[u.key].shields; addText(e.t, '护盾恢复', '#bfe0ff', 26, -52); SFX.play('recover'); });
        break;
      case 'turn':
        actor = e.t || e.u;
        add(260, () => { acted.add(e.u.join()); banner = null; const a = An(e.u); a.glow = 1; SFX.play('turn'); }, p => { An(e.u).dx = (e.u[0] === 0 ? 1 : -1) * 10 * p; });
        break;
      case 'latent':
        add(1000, () => { const u = U(e.u); u.lat = 0; bigText = { text: M.latent[e.name] || '潜力', sub: '潜力发动', t0: now, dur: 1000, col: '#ffb86b' }; fx('aura', e.u, { dur: 1000, col: '#ffb040', kit: 'latent', kitS: 1.5 }); SFX.play('latent'); });
        break;
      case 'boost': {
        // 原作式增幅：每花 1 BP 一声"叮"、一圈光、一颗 BP 熄灭；最后按档位爆发，档位越高光焰越大
        const n = e.n; let fired = 0, burst = false, bp0 = null;
        add(380 + n * 240, () => { bp0 = U(e.u).bp; addText(e.u, `增幅 ×${n}`, BOOST_COL[n][0], 26 + n * 4, -62, 700 + n * 220); }, p => {
          const u = U(e.u), a = An(e.u);
          if (bp0 === null) bp0 = u.bp;
          while (fired < n && p >= fired * 0.17) {
            fired++; u.bp = Math.max(0, bp0 - fired); a.bl = fired; a.ba = 1;
            fx('boostTick', e.u, { dur: 420, lv: fired }); SFX.play('boostTick', fired - 1);
          }
          if (!burst && p >= n * 0.17 + 0.05) {
            burst = true; a.bl = n; a.ba = 1;
            fx('boost', e.u, { dur: 650 + n * 260, lv: n }); SFX.play('boostBurst', n);
            if (n >= 2) shakeFx = { t0: now, dur: 220 + n * 120, amp: n === 3 ? 7 : 3 };
            if (n === 3) flashFx = { t0: now, dur: 420, col: '255,180,90' };
          }
        });
        break;
      }
      case 'skill': {
        skill = e;
        const sn = e.s === 'attack' ? { name: '攻击', zh: `攻击（${TYPE_ZH[e.w]}）` } : e.s === 'concoct' ? { name: '调合', zh: `调合：${M.recipes[e.r]}` }
          : e.s === 'item' ? { name: '道具', zh: `道具：${(ITN[e.it] || {}).zh || e.it}` } : skillName(e.s);
        const physical = e.s === 'attack' || (evs.slice(k + 1).find(x => x.e === 'hit') || {}).ty in { sword: 1, polearm: 1, dagger: 1, axe: 1, bow: 1, staff: 1 };
        if (CUT_ON && e.s !== 'attack' && e.s !== 'defend' && e.s !== 'item') {
          // 技能特写：立绘 + 技能名切入，画面停住；神技、潜力技更长更华丽
          const lv2 = (SKN[e.s] || {}).x || 0, n = (fr.a && fr.a.boost) || 0, ck = M.picks[e.u[0]][e.u[1]];
          const c = { key: ck, team: e.u[0], zh: sn.zh, who: TR[ck].name, job: TR[ck].job, lv: lv2 ? 2 : 1, lv2, boost: n, p: 0 };
          add(lv2 ? 1500 : 900 + n * 120, () => { cutin = c; banner = null; SFX.play('cutin', c.lv, n); }, p => { c.p = p; });
        }
        add(e.s === 'defend' ? 600 : e.s === 'item' ? 700 : 450, () => {
          cutin = null;
          banner = { zh: sn.zh, who: nm(e.u), job: TR[M.picks[e.u[0]][e.u[1]]].job, team: e.u[0], t0: now };
          const a = An(e.u); a.motionAt = now;
          const w = actWeapon(evs, k, e); if (w) a.wp = w; // 换成这次要用的武器
          if (e.s === 'defend') { a.pose = 'guard'; fx('shield', e.u, { dur: 600 }); SFX.play('defend'); return; }
          if (e.s === 'item') { const bg = BAG[e.u[0]]; if (bg && bg[e.it] > 0) bg[e.it]--; a.pose = 'cast'; const [kd, col] = itemKind(e.it); fx('item', e.u, { dur: 900, kind: kd, col }); SFX.play('item'); return; }
          a.pose = physical ? 'atk' : 'cast';
          if (!physical) { fx('circle', e.u, { dur: 900 }); SFX.play('cast'); }
        }, p => { if (physical) { const a = An(e.u); a.dx = (e.u[0] === 0 ? 1 : -1) * (10 + 18 * Math.sin(p * Math.PI / 2)); } });
        break;
      }
      case 'hit': {
        const multi = evs.filter(x => x.e === 'hit').length > 3;
        add(multi ? 170 : 260, () => {
          const u = U(e.t), a = An(e.t);
          if (e.miss) { addText(e.t, e.dodge ? '闪避' : '未命中', '#d0d0e0', 28); SFX.play('miss'); return; }
          u.hp = Math.max(0, u.hp - e.d);
          a.flash = 1; a.shake = 1; a.motionAt = now; a.pose = a.pose === 'kneel' ? 'kneel' : 'hurt';
          fx('hit', e.t, { ty: e.ty, dur: 380, kit: e.ty, flip: e.t[0] === 0 }); SFX.play(e.ty); if (e.w) SFX.play('weak'); if (e.c) SFX.play('crit');
          let col = '#ffffff';
          if (e.w) col = '#ffd84a';
          addText(e.t, String(e.d), col, e.c ? 44 : 36);
          if (e.w) { addText(e.t, '弱点', '#ffb030', 22, -48, 800); u.wkTy = e.ty; u.wkT = now; }
          if (e.c) addText(e.t, '暴击', '#ff7a5a', 22, -58, 800);
        });
        break;
      }
      case 'shield':
        add(60, () => { const u = U(e.t); u.sh = e.v; fx('shieldchip', e.t, { dur: 400 }); SFX.play('chip'); });
        break;
      case 'break':
        add(900, () => { const u = U(e.t); u.brk = 1; u.sh = 0; An(e.t).pose = 'kneel'; fx('break', e.t, { dur: 900, kit: 'break', flip: e.t[0] === 0, kitS: 1.5 }); bigText = { text: '破防', sub: nm(e.t), t0: now, dur: 900, col: '#ffef8a', small: 1 }; SFX.play('break'); });
        break;
      case 'ko':
        add(600, () => { const u = U(e.t); u.alive = 0; u.hp = 0; u.brk = 0; An(e.t).koAt = now; addText(e.t, '倒下', '#ff8a8a', 28, -50); SFX.play('ko'); }, p => { An(e.t).alpha = 1 - 0.6 * p; });
        break;
      case 'heal':
        add(220, () => { const u = U(e.t); u.hp = Math.min(MAXHS(e.t[0], e.t[1])[0], u.hp + e.v); fx('heal', e.t, { dur: 700, kit: 'heal' }); addText(e.t, '+' + e.v, '#8affa0', 32); SFX.play('heal'); });
        break;
      case 'revive':
        add(700, () => { const u = U(e.t); u.alive = 1; u.hp = e.v; u.sh = TR[u.key].shields; u.brk = 0; An(e.t).alpha = 1; An(e.t).reviveAt = now; fx('pillar', e.t, { dur: 900, kit: 'revive' }); addText(e.t, '复活', '#fff3a0', 30, -50); SFX.play('revive'); });
        break;
      case 'sp':
        add(120, () => { const u = U(e.t); u.sp += e.v; if (e.v) addText(e.t, `SP +${e.v}`, '#8fd0ff', 24, -40); });
        break;
      case 'bp':
        add(250, () => { U(e.t).bp = e.v; addText(e.t, `BP ${e.v}`, '#ffe680', 24, -40); });
        break;
      case 'buff':
        add(180, () => { const u = U(e.t); const o = e.up ? u.up : u.down; o[e.st] = Math.max(o[e.st] || 0, e.r || 0); u.icT = now; fx(e.up ? 'up' : 'down', e.t, { dur: 600 }); addText(e.t, `${STAT_ZH[e.st]}${e.up ? '↑' : '↓'}`, e.up ? '#9fd8ff' : '#ff9fb0', 24, -44); SFX.play(e.up ? 'up' : 'down'); });
        break;
      case 'status':
        add(200, () => { if (STATUS_ZH[e.k] && e.r) { const u = U(e.t); u.st[e.k] = Math.max(u.st[e.k] || 0, e.r); u.icT = now; } const label = STATUS_ZH[e.k] || ({ tier2: '魔法强化·二段', tier3: '魔法强化·三段', stimulate: '行动提前' })[e.k] || e.k; addText(e.t, label, '#e0c8ff', 24, -44); SFX.play('status'); });
        break;
      case 'dispel':
        add(220, () => { const u = U(e.t); u.up = {}; for (const k of POSITIVE_ST) delete u.st[k]; u.icT = now; addText(e.t, '增益解除', '#c8c8ff', 24, -44); SFX.play('down'); });
        break;
      case 'poison':
        add(300, () => { const u = U(e.t); u.hp = Math.max(0, u.hp - e.d); An(e.t).flash = 1; addText(e.t, String(e.d), '#c88aff', 30); fx('poison', e.t, { dur: 500 }); SFX.play('poison'); });
        break;
      case 'counter':
        add(300, () => { An(e.u).motionAt = now; An(e.u).pose = 'atk'; addText(e.u, '反击', '#ffd0a0', 26, -50); SFX.play('sword'); });
        break;
      case 'cure':
        add(220, () => { const u = U(e.t); delete u.st.poison; delete u.st.poison_weak; u.icT = now; fx('heal', e.t, { dur: 600 }); addText(e.t, '解毒', '#b8ffcf', 24, -44); SFX.play('up'); });
        break;
      case 'grace':
        add(300, () => { addText(e.u, '迷惑之舞！', '#ffb0e0', 24, -60); fx('aura', e.u, { dur: 500, col: '#ff8fd0' }); SFX.play('status'); });
        break;
      case 'end':
        add(1500, () => { bigText = { text: e.winner === -1 ? '平局' : '胜利', sub: e.winner === -1 ? '双方剩余 HP 相同' : `${R.bots[e.winner]} 获胜`, t0: now, dur: 1e9, col: e.winner === -1 ? '#ddd' : '#ffe08a', team: e.winner }; SFX.play('victory'); });
        break;
    }
  }
  if (actor || skill) add(350, null, p => {
    for (const team of A || []) for (const a of team) { a.dx *= (1 - p); if (a.pose !== 'kneel') a.pose = 'idle'; a.glow *= (1 - p); a.ba *= (1 - p); }
  });
  return L;
}

function gotoFrame(fi) {
  cur = Math.max(0, Math.min(F.length - 1, fi));
  steps = []; si = 0; st = 0;
  pickShown = [[], []];
  loCard = F[cur].ev.some(e => e.e === 'loadout') && !CLEAN ? { t0: -1e9, dur: 1e12 } : null;
  for (let i = 0; i <= cur; i++) for (const e of F[i].ev) if (e.e === 'pick') pickShown[e.team] = pickShown[e.team].concat(e.picks);
  snapState(cur);
  banner = null; cutin = null; effects = []; texts = [];
  const last = F[cur];
  bigText = last.win !== undefined ? { text: last.win === -1 ? '平局' : '胜利', sub: last.win === -1 ? '双方剩余 HP 相同' : `${R.bots[last.win]} 获胜`, t0: -1e9, dur: 1e12, col: '#ffe08a', team: last.win } : null;
  if (A && D) for (let t = 0; t < 2; t++) for (let i = 0; i < A[t].length; i++) {
    const u = D[t][i], a = A[t][i]; a.alpha = u.alive ? 1 : 0.4; a.pose = u.brk ? 'kneel' : 'idle';
  }
  seek.value = cur; updateInfo(); highlightLog();
}

function startNext() {
  if (cur >= F.length - 1) { playing = false; updatePlay(); return false; }
  cur++;
  loCard = null;
  steps = plan(cur); si = 0; st = 0;
  seek.value = cur; updateInfo(); highlightLog();
  if (steps.length && steps[0].on) steps[0].on();
  return true;
}
function finishFrame() {
  // 帧结束：与权威状态对齐
  const keepBig = bigText;
  const f = F[cur];
  if (f.u) {
    const prevOrder = order, prevActed = acted;
    snapState(cur); order = prevOrder; acted = prevActed;
    for (let t = 0; t < 2; t++) for (let i = 0; i < A[t].length; i++) { const u = D[t][i], a = A[t][i]; a.alpha = u.alive ? 1 : 0.4; a.pose = u.brk ? 'kneel' : 'idle'; }
  }
  bigText = keepBig;
}

let now = 0, lastT = 0;
function tickTimeline(dt) {
  if (!playing) return;
  let budget = dt * speed;
  let guard = 0;
  while (budget > 0 && guard++ < 200) {
    if (si >= steps.length) {
      if (steps.length) finishFrame();
      if (!startNext()) return;
      if (!steps.length) continue;
    }
    const s = steps[si];
    const rem = s.d - st;
    if (budget < rem) { st += budget; if (s.upd) s.upd(st / s.d); budget = 0; }
    else {
      budget -= rem; if (s.upd) s.upd(1); si++; st = 0;
      if (si < steps.length && steps[si].on) steps[si].on();
    }
  }
}

// ------------------------------------------------------------------ 绘制
function drawUnitLow(t, i, time) {
  const u = D[t][i], a = A[t][i], [hx, hy] = homePos(t, i);
  let x = hx + a.dx, y = hy + a.dy;
  if (a.shake > 0) x += Math.sin(time * 0.09) * 2 * a.shake;
  if (a.ba > 0.02 && a.bl) drawBoostAura(x, y, a.bl, a.ba, time, t * 10 + i);
  drawBattleActor(u.key, x, y, t, time, a, u, i);
  if (u.alive) drawUnitStatusFx(u, x, y, time, t * 10 + i);
}
// 角色身上的持续状态：中毒冒紫色气泡，破防时头顶转星星，再生飘绿色光点
function drawUnitStatusFx(u, x, y, time, seed) {
  const kit = KIT_CHAR[u.key], h = kit ? kit.f.idle[3] / ART_SCALE : 40;
  lx.save();
  if (u.st.poison) for (let k = 0; k < 4; k++) {
    const ph = (time / 1400 + k / 4 + rnd(seed + k) * 0.3) % 1;
    lx.globalAlpha = Math.sin(ph * Math.PI) * 0.85; lx.fillStyle = k % 2 ? '#c27af0' : '#9a4ad8';
    lx.beginPath(); lx.arc(x + (rnd(seed * 7 + k) - 0.5) * 18 + Math.sin(ph * 6 + k) * 2, y - h * 0.35 - ph * h * 0.55, 1 + ph * 1.4, 0, 6.28); lx.fill();
  }
  if (u.st.regen) for (let k = 0; k < 3; k++) {
    const ph = (time / 1600 + k / 3) % 1;
    lx.globalAlpha = Math.sin(ph * Math.PI) * 0.8; lx.fillStyle = '#9affb0';
    const px = x + (rnd(seed * 3 + k) - 0.5) * 20, py = y - ph * h * 0.8;
    lx.fillRect(px - 0.4, py - 1.6, 0.8, 3.2); lx.fillRect(px - 1.6, py - 0.4, 3.2, 0.8);
  }
  if (u.brk) {
    const hy = y - h * 0.72;
    for (let k = 0; k < 3; k++) {
      const an = time / 380 + k / 3 * 6.28, sx = x + Math.cos(an) * 8, sy = hy + Math.sin(an) * 2.2;
      lx.globalAlpha = Math.sin(an) > 0 ? 1 : 0.55; lx.fillStyle = '#ffe680';
      lx.beginPath(); for (let j = 0; j < 10; j++) { const r = j % 2 ? 0.9 : 2.2, aa = j / 10 * 6.28 - Math.PI / 2; lx.lineTo(sx + Math.cos(aa) * r, sy + Math.sin(aa) * r); } lx.closePath(); lx.fill();
    }
  }
  lx.restore();
}
function animDecay(dt) { // 60fps 下每帧 -0.06 / -0.08
  if (A) for (const team of A) for (const a of team) { a.shake = Math.max(0, a.shake - 0.0036 * dt); a.flash = Math.max(0, a.flash - 0.0048 * dt); }
}

function drawBoostAura(x, y, lv, al, time, seed) {
  const C = BOOST_COL[lv], n = 8 + lv * 8, w = 9 + lv * 3, hMax = 16 + lv * 13;
  lx.save(); lx.globalCompositeOperation = 'lighter';
  for (let k = 0; k < n; k++) {
    const ph = (time * (0.0011 + lv * 0.00045) + rnd(k + seed * 7)) % 1;
    const xx = x + (rnd(k * 3 + seed) - 0.5) * 2 * w * (1 - ph * 0.6);
    const yy = y - 3 - ph * hMax;
    lx.globalAlpha = al * (1 - ph) * 0.95;
    lx.fillStyle = ph < 0.3 ? C[0] : ph < 0.6 ? C[1] : C[2];
    lx.fillRect(xx | 0, yy | 0, 1 + (lv >= 2 && k % 3 === 0), 2 + lv);
  }
  lx.globalAlpha = al * (0.4 + 0.2 * Math.sin(time * 0.012));
  lx.strokeStyle = C[1]; lx.beginPath(); lx.ellipse(x, y, 10 + lv * 3, 3 + lv * 0.6, 0, 0, 6.28); lx.stroke();
  if (lv === 3) { lx.globalAlpha = al * 0.3; lx.strokeStyle = C[2]; lx.beginPath(); lx.ellipse(x, y, 16 + Math.sin(time * 0.02) * 2, 5, 0, 0, 6.28); lx.stroke(); }
  lx.restore();
}

function drawEffectsLow(time) {
  effects = effects.filter(e => now - e.t0 < Math.max(e.dur, e.kit && KIT_FX[e.kit] ? KIT_FX[e.kit].dur : 0));
  for (const e of effects) {
    const p = (now - e.t0) / e.dur;
    const cx = e.x, cy = e.y - 18;
    // 素材包特效（命中时的武器/属性特效，破防、治疗、复活、潜力）；命中特效有素材时替换程序绘制，其余叠加在程序特效上
    const kitDrawn = e.kit && drawKitFx(e.kit, e.x, e.y, now - e.t0, e.flip, e.kitS || 1);
    if (p >= 1 || (kitDrawn && e.type === 'hit')) continue;
    lx.save();
    if (e.type === 'hit') {
      const col = TYPE_COL[e.ty] || '#ffffff';
      lx.fillStyle = col;
      if (['fire'].includes(e.ty)) for (let k = 0; k < 14; k++) { const r = p * 16; lx.fillRect(cx + Math.cos(k) * r * rnd(k) | 0, cy - p * 14 - rnd(k + 3) * 10 | 0, 2, 2); }
      else if (e.ty === 'ice') for (let k = 0; k < 8; k++) { const a = k / 8 * 6.28; lx.fillRect(cx + Math.cos(a) * (4 + p * 12) | 0, cy + Math.sin(a) * (4 + p * 12) | 0, 2, 3); }
      else if (e.ty === 'lightning') { lx.strokeStyle = col; lx.lineWidth = 2; lx.beginPath(); let yy = cy - 60, xx = cx; lx.moveTo(xx, yy); while (yy < cy) { yy += 8; xx += (rnd(yy + time) - 0.5) * 10; lx.lineTo(xx, yy); } lx.globalAlpha = 1 - p; lx.stroke(); }
      else if (e.ty === 'wind') { lx.strokeStyle = col; lx.globalAlpha = 1 - p; lx.beginPath(); lx.arc(cx, cy, 6 + p * 14, p * 6, p * 6 + 4); lx.stroke(); }
      else if (e.ty === 'light') { lx.globalAlpha = 1 - p; lx.fillRect(cx - 4, cy - 70, 8, 80); }
      else if (e.ty === 'dark') { for (let k = 0; k < 10; k++) { const a = k * 0.63 + p * 3; lx.fillRect(cx + Math.cos(a) * (14 - p * 12) | 0, cy + Math.sin(a) * (14 - p * 12) | 0, 3, 3); } }
      else { // 物理斩击
        lx.strokeStyle = '#ffffff'; lx.lineWidth = 2; lx.globalAlpha = 1 - p;
        lx.beginPath(); lx.moveTo(cx - 12 + p * 4, cy - 12); lx.lineTo(cx + 12, cy + 10 - p * 4); lx.stroke();
        lx.fillStyle = col; for (let k = 0; k < 6; k++) lx.fillRect(cx + (rnd(k + 5) - 0.5) * 24 * p | 0, cy + (rnd(k + 9) - 0.5) * 24 * p | 0, 2, 2);
      }
    } else if (e.type === 'break') {
      lx.fillStyle = '#ffe9a0';
      for (let k = 0; k < 18; k++) { const a = k / 18 * 6.28; const r = 4 + p * 30; lx.globalAlpha = 1 - p; lx.fillRect(cx + Math.cos(a) * r | 0, cy - 14 + Math.sin(a) * r * 0.7 | 0, 3, 2); }
    } else if (e.type === 'heal') {
      lx.fillStyle = '#9affb0'; for (let k = 0; k < 8; k++) { lx.globalAlpha = 1 - p; lx.fillRect(cx - 10 + rnd(k) * 20 | 0, cy + 10 - p * 30 - rnd(k + 1) * 10 | 0, 1, 3); lx.fillRect(cx - 11 + rnd(k) * 20 | 0, cy + 11 - p * 30 - rnd(k + 1) * 10 | 0, 3, 1); }
    } else if (e.type === 'pillar') {
      const g = lx.createLinearGradient(0, cy - 80, 0, cy + 20); g.addColorStop(0, 'rgba(255,250,200,0)'); g.addColorStop(1, 'rgba(255,250,200,.8)');
      lx.globalAlpha = Math.sin(p * Math.PI); lx.fillStyle = g; lx.fillRect(cx - 9, cy - 80, 18, 100);
    } else if (e.type === 'circle') {
      lx.strokeStyle = '#9fe8ff'; lx.globalAlpha = Math.sin(p * Math.PI);
      lx.beginPath(); lx.ellipse(cx, e.y, 16, 5, 0, 0, 6.28); lx.stroke();
      lx.beginPath(); lx.ellipse(cx, e.y, 11, 3, 0, p * 6, p * 6 + 5); lx.stroke();
    } else if (e.type === 'aura') {
      lx.fillStyle = e.col || '#ffd84a';
      for (let k = 0; k < 12; k++) { lx.globalAlpha = 1 - p; lx.fillRect(cx - 12 + rnd(k * 3) * 24 | 0, e.y - (p * 40 + rnd(k) * 20) | 0, 1, 3); }
    } else if (e.type === 'boostTick') {
      const C = BOOST_COL[e.lv]; lx.globalCompositeOperation = 'lighter';
      lx.strokeStyle = C[1]; lx.globalAlpha = 1 - p; lx.beginPath(); lx.ellipse(e.x, e.y, 6 + p * (12 + e.lv * 4), 2 + p * 4, 0, 0, 6.28); lx.stroke();
      lx.fillStyle = C[0]; for (let k = 0; k < 6 + e.lv * 2; k++) { const an = k / (6 + e.lv * 2) * 6.28; lx.fillRect(cx + Math.cos(an) * p * 16 | 0, cy + Math.sin(an) * p * 12 | 0, 2, 2); }
    } else if (e.type === 'boost') {
      const lv = e.lv, C = BOOST_COL[lv]; lx.globalCompositeOperation = 'lighter';
      for (let r = 0; r < lv; r++) { const q = Math.min(1, p * (1.7 - r * 0.3)); lx.globalAlpha = (1 - q) * 0.9; lx.strokeStyle = r ? C[2] : C[1]; lx.lineWidth = lv === 3 ? 2 : 1; lx.beginPath(); lx.ellipse(e.x, e.y, 8 + q * (16 + lv * 10), 2 + q * (4 + lv * 2), 0, 0, 6.28); lx.stroke(); }
      const nS = 10 + lv * 14;
      for (let k = 0; k < nS; k++) {
        const sp = 0.6 + rnd(k * 5) * 0.8, an = -Math.PI / 2 + (rnd(k * 7) - 0.5) * (0.6 + lv * 0.4), d = p * sp * (24 + lv * 16);
        lx.globalAlpha = 1 - p; lx.fillStyle = k % 3 ? C[0] : C[2];
        lx.fillRect(e.x + Math.cos(an) * d | 0, e.y - 6 + Math.sin(an) * d + p * p * 12 | 0, 1 + (k % 4 === 0), 2);
      }
      if (lv >= 2) {
        const hh = lv === 3 ? 96 : 48, ww = (lv === 3 ? 18 : 9) * (1 - p * 0.5);
        const g = lx.createLinearGradient(0, e.y - hh, 0, e.y); g.addColorStop(0, 'rgba(255,200,120,0)'); g.addColorStop(1, lv === 3 ? 'rgba(255,150,70,.9)' : 'rgba(255,200,110,.6)');
        lx.globalAlpha = Math.sin(Math.min(1, p * 1.4) * Math.PI); lx.fillStyle = g; lx.fillRect(e.x - ww / 2, e.y - hh, ww, hh);
      }
    } else if (e.type === 'up' || e.type === 'down') {
      lx.fillStyle = e.type === 'up' ? '#8fd0ff' : '#ff8fa0'; lx.globalAlpha = 1 - p;
      for (let k = 0; k < 3; k++) { const yy = e.type === 'up' ? cy + 6 - p * 20 - k * 6 : cy - 16 + p * 20 + k * 6; lx.fillRect(cx - 8 + k * 7, yy | 0, 2, 4); }
    } else if (e.type === 'poison') {
      lx.fillStyle = '#b070ff'; for (let k = 0; k < 6; k++) { lx.globalAlpha = 1 - p; lx.fillRect(cx - 8 + rnd(k) * 16 | 0, cy - p * 20 - rnd(k + 2) * 8 | 0, 2, 2); }
    } else if (e.type === 'item') {
      // 道具：从手里举过头顶、发光，最后化成一圈亮点
      const q = Math.min(1, p / 0.6), yy = cy - 16 - q * 14;
      lx.globalAlpha = p < 0.7 ? 1 : (1 - p) / 0.3;
      const g = lx.createRadialGradient(cx, yy, 0, cx, yy, 12); g.addColorStop(0, 'rgba(255,250,220,.55)'); g.addColorStop(1, 'rgba(255,250,220,0)');
      lx.fillStyle = g; lx.fillRect(cx - 12, yy - 12, 24, 24);
      itemPix(lx, cx, yy | 0, e.kind, e.col);
      if (p > 0.55) { const r = (p - 0.55) * 50; lx.fillStyle = '#fff6c8'; for (let k = 0; k < 10; k++) { const an = k / 10 * 6.28; lx.fillRect(cx + Math.cos(an) * r | 0, yy + Math.sin(an) * r * 0.8 | 0, 1, 1); } }
    } else if (e.type === 'shield') {
      lx.strokeStyle = '#a8d8ff'; lx.globalAlpha = 1 - p; lx.lineWidth = 1; lx.beginPath(); lx.arc(cx, cy, 16, 0, 6.28); lx.stroke();
    }
    lx.restore();
  }
}

// 道具小图标（像素画，约 9×10）：葡萄、果子、橄榄、草药、石榴、魂石、药瓶
function itemKind(id) {
  const it = ITN[id] || {}, f = it.fx || {};
  if (f.dmg) return ['stone', TYPE_COL[f.type] || '#e0e0e0'];
  if (f.revive) return ['olive', '#9acb4a'];
  if (f.bp) return ['fruit', '#e0403a'];
  if (f.cure && !f.hp && !f.hp_pct) return ['herb', '#5fc860'];
  if ((f.sp || f.sp_pct) && !(f.hp || f.hp_pct)) return ['fruit', '#c060e0'];
  if (f.hp || f.hp_pct) return [it.target === 'allies' ? 'grapes' : 'grape', '#7fd060'];
  return ['bottle', '#ffd070'];
}
function itemPix(g, x, y, kind, col) {
  const P = (dx, dy, w, h, c) => { g.fillStyle = c; g.fillRect(x + dx, y + dy, w, h); };
  const dk = shade(col, -0.45), lt = shade(col, 0.5);
  if (kind === 'stone') { P(-3, -4, 6, 8, dk); P(-4, -2, 8, 4, dk); P(-2, -3, 4, 6, col); P(-3, -1, 6, 2, col); P(-1, -3, 1, 2, lt); return; }
  if (kind === 'herb') { P(0, -1, 1, 6, '#3c7a30'); P(-4, -5, 3, 3, col); P(1, -6, 3, 3, col); P(-2, -2, 3, 2, dk); P(1, -3, 3, 2, dk); return; }
  if (kind === 'olive') { P(0, -6, 1, 2, '#6a4a20'); P(1, -6, 3, 1, '#5aa040'); P(-2, -4, 5, 8, dk); P(-3, -3, 7, 6, col); P(-1, -3, 1, 2, lt); return; }
  if (kind === 'fruit') { P(0, -6, 1, 2, '#6a4a20'); P(1, -6, 2, 1, '#5aa040'); P(-3, -4, 7, 8, dk); P(-4, -3, 9, 6, col); P(-2, -3, 2, 2, lt); return; }
  if (kind === 'grape' || kind === 'grapes') {
    P(0, -7, 1, 2, '#6a4a20'); P(1, -7, 3, 1, '#5aa040');
    const balls = kind === 'grapes' ? [[-4, -5], [-1, -5], [2, -5], [-3, -2], [0, -2], [3, -2], [-2, 1], [1, 1], [-1, 4]] : [[-3, -5], [0, -5], [-2, -2], [1, -2], [-1, 1]];
    for (const [bx, by] of balls) { P(bx, by, 3, 3, dk); P(bx, by, 2, 2, col); }
    return;
  }
  P(-1, -6, 3, 2, '#c8b080'); P(-3, -4, 7, 8, dk); P(-2, -3, 5, 6, col); P(-1, -3, 1, 3, lt);
}

function drawGlow(time) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  for (const [tx, ty] of TORCHES) {
    const fl = 0.85 + 0.15 * Math.sin(time * 0.013 + tx) + 0.08 * Math.sin(time * 0.031 + ty);
    const [gx, gy] = toScr(tx, ty - 4);
    const g = ctx.createRadialGradient(gx, gy, 2, gx, gy, 80 * fl);
    g.addColorStop(0, 'rgba(255,200,120,0.85)'); g.addColorStop(0.3, 'rgba(255,140,60,0.35)'); g.addColorStop(1, 'rgba(255,100,40,0)');
    ctx.fillStyle = g; ctx.fillRect(gx - 90, gy - 90, 180, 180);
  }
  for (const e of effects) {
    const p = (now - e.t0) / e.dur, a = Math.max(0, 1 - p);
    let col = null, r = 40;
    if (e.type === 'hit') { col = TYPE_COL[e.ty] || '#ffffff'; r = 60; }
    else if (e.type === 'break') { col = '#ffe08a'; r = 120; }
    else if (e.type === 'heal' || e.type === 'pillar') { col = '#b0ffc0'; r = 70; }
    else if (e.type === 'aura') { col = e.col; r = 60; }
    else if (e.type === 'boost') { col = BOOST_COL[e.lv][1]; r = 70 + e.lv * 45; }
    else if (e.type === 'boostTick') { col = BOOST_COL[e.lv][0]; r = 46 + e.lv * 6; }
    else if (e.type === 'circle') { col = '#80e0ff'; r = 50; }
    if (!col) continue;
    const [rr, gg, bb] = hex2rgb(col);
    const [x, y] = toScr(e.x, e.y - 18);
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rr},${gg},${bb},${0.55 * a})`); g.addColorStop(1, `rgba(${rr},${gg},${bb},0)`);
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }
  // 增幅后持续的光焰（直到这次行动结束）
  if (A && D) for (let t = 0; t < 2; t++) for (let i = 0; i < A[t].length; i++) {
    const a = A[t][i]; if (!(a.ba > 0.02 && a.bl)) continue;
    const [hx, hy] = homePos(t, i), [x, y] = toScr(hx + a.dx, hy - 20);
    const r = (46 + a.bl * 30) * (0.92 + 0.08 * Math.sin(now * 0.01 + i));
    const [rr, gg, bb] = hex2rgb(BOOST_COL[a.bl][1]);
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rr},${gg},${bb},${0.4 * a.ba})`); g.addColorStop(1, `rgba(${rr},${gg},${bb},0)`);
    ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2);
  }
  // 漂浮的火星/尘埃
  // 位置只由时间决定，逐帧录制时结果固定
  for (let k = 0; k < 70; k++) {
    const v = (0.2 + rnd(k * 5 + 1) * 0.5) * 0.06, sz = 1 + rnd(k * 5 + 2) * 2.5, ph = rnd(k * 5 + 3) * 6, span = H + 20;
    const y = H + 10 - ((time * v + rnd(k * 5 + 4) * span) % span), x = rnd(k * 5) * W - Math.cos(time * 0.001 + ph) * 18;
    const a = 0.25 + 0.25 * Math.sin(time * 0.003 + ph);
    ctx.fillStyle = `rgba(255,210,150,${a})`; ctx.fillRect(x, y, sz, sz);
  }
  ctx.restore();
}

// ---------- UI（全分辨率）
const FONT = '"Replay CJK","Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif';
// 内嵌字体（viewer.py 注入）：先加载好再开始画字，避免先用系统字体再跳变
const FONT_READY = document.fonts ? document.fonts.load('700 16px "Replay CJK"').catch(() => {}) : Promise.resolve();
function txt(s, x, y, size, col, align = 'left', bold = true, stroke = true) {
  ctx.font = `${bold ? '700 ' : ''}${size}px ${FONT}`; ctx.textAlign = align; ctx.textBaseline = 'middle';
  if (stroke) { ctx.lineWidth = Math.max(3, size / 6); ctx.strokeStyle = 'rgba(10,6,18,.9)'; ctx.lineJoin = 'round'; ctx.strokeText(s, x, y); }
  ctx.fillStyle = col; ctx.fillText(s, x, y);
}
function panelBox(x, y, w, h, alpha = 0.72) {
  const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, `rgba(18,14,30,${alpha})`); g.addColorStop(1, `rgba(8,6,16,${alpha + 0.1})`);
  ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = 'rgba(214,190,130,.75)'; ctx.lineWidth = 2; ctx.strokeRect(x + 3, y + 3, w - 6, h - 6);
  ctx.strokeStyle = 'rgba(214,190,130,.25)'; ctx.lineWidth = 1; ctx.strokeRect(x + 7, y + 7, w - 14, h - 14);
}
function bar(x, y, w, h, frac, c1, c2) {
  ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillRect(x, y, w, h);
  const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, c1); g.addColorStop(1, c2);
  ctx.fillStyle = g; ctx.fillRect(x + 1, y + 1, Math.max(0, (w - 2) * Math.max(0, Math.min(1, frac))), h - 2);
}
// 弱点图标：仿原作的深色小方框 + 白色剪影图标（武器 6 种、属性 6 种），全部用路径现场绘制
const ICON_CACHE = {};
function iconGlyph(c, ty) { // 在 [-0.5, 0.5] 的单位坐标里画剪影，调用方负责缩放
  const P = pts => { c.beginPath(); pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.closePath(); c.fill(); };
  const R = (x, y, w, h) => c.fillRect(x, y, w, h);
  const rot = a => c.rotate(a * Math.PI / 180);
  switch (ty) {
    case 'sword': rot(45); P([[0, -0.5], [0.065, -0.38], [0.065, 0.14], [-0.065, 0.14], [-0.065, -0.38]]); R(-0.2, 0.14, 0.4, 0.07); R(-0.035, 0.21, 0.07, 0.17); c.beginPath(); c.arc(0, 0.42, 0.055, 0, 7); c.fill(); break;
    case 'dagger': rot(45); P([[0.02, -0.4], [0.1, -0.2], [0.08, 0.1], [-0.08, 0.1], [-0.06, -0.25]]); R(-0.17, 0.1, 0.34, 0.07); R(-0.04, 0.17, 0.08, 0.2); R(-0.07, 0.36, 0.14, 0.06); break;
    case 'polearm': rot(45); P([[0, -0.52], [0.1, -0.33], [0.035, -0.2], [-0.035, -0.2], [-0.1, -0.33]]); R(-0.1, -0.22, 0.2, 0.05); R(-0.03, -0.2, 0.06, 0.7); break;
    case 'axe': rot(35); R(-0.035, -0.42, 0.07, 0.92);
      c.beginPath(); c.moveTo(0.02, -0.36); c.quadraticCurveTo(0.3, -0.42, 0.4, -0.52); c.quadraticCurveTo(0.3, -0.24, 0.4, 0.02); c.quadraticCurveTo(0.3, -0.08, 0.02, -0.12); c.closePath(); c.fill();
      P([[-0.02, -0.33], [-0.18, -0.3], [-0.18, -0.18], [-0.02, -0.15]]); break;
    case 'bow': rot(45);
      c.lineWidth = 0.075; c.beginPath(); c.moveTo(-0.08, -0.46); c.quadraticCurveTo(0.42, 0, -0.08, 0.46); c.stroke();
      c.lineWidth = 0.025; c.beginPath(); c.moveTo(-0.08, -0.46); c.lineTo(-0.08, 0.46); c.stroke();
      R(-0.36, -0.018, 0.62, 0.036); P([[0.36, 0], [0.22, -0.07], [0.22, 0.07]]); P([[-0.36, 0], [-0.44, -0.07], [-0.3, -0.02]]); P([[-0.36, 0], [-0.44, 0.07], [-0.3, 0.02]]); break;
    case 'staff': rot(45); R(-0.035, -0.2, 0.07, 0.7);
      c.beginPath(); c.arc(0, -0.33, 0.13, 0, 7); c.fill();
      c.lineWidth = 0.05; c.beginPath(); c.arc(0, -0.33, 0.2, Math.PI * 0.65, Math.PI * 2.35); c.stroke(); break;
    case 'fire':
      c.beginPath(); c.moveTo(0, -0.48); c.bezierCurveTo(0.12, -0.24, 0.38, -0.12, 0.33, 0.16); c.bezierCurveTo(0.3, 0.38, 0.14, 0.46, 0, 0.46);
      c.bezierCurveTo(-0.14, 0.46, -0.32, 0.38, -0.33, 0.16); c.bezierCurveTo(-0.34, -0.02, -0.2, -0.1, -0.16, -0.26); c.bezierCurveTo(-0.08, -0.14, -0.04, -0.2, 0, -0.48); c.fill();
      c.globalCompositeOperation = 'destination-out';
      c.beginPath(); c.moveTo(0.02, -0.08); c.bezierCurveTo(0.08, 0.06, 0.18, 0.14, 0.15, 0.27); c.bezierCurveTo(0.12, 0.36, -0.12, 0.36, -0.15, 0.27); c.bezierCurveTo(-0.17, 0.17, -0.06, 0.08, 0.02, -0.08); c.fill();
      c.globalCompositeOperation = 'source-over'; break;
    case 'ice':
      c.lineWidth = 0.075; c.lineCap = 'round';
      for (let k = 0; k < 6; k++) { c.save(); c.rotate(k * Math.PI / 3); c.beginPath(); c.moveTo(0, 0); c.lineTo(0, -0.44); c.moveTo(0, -0.26); c.lineTo(0.12, -0.36); c.moveTo(0, -0.26); c.lineTo(-0.12, -0.36); c.stroke(); c.restore(); }
      break;
    case 'lightning': P([[0.12, -0.5], [-0.24, 0.06], [-0.02, 0.06], [-0.14, 0.5], [0.26, -0.1], [0.04, -0.1], [0.2, -0.5]]); break;
    case 'wind':
      c.lineWidth = 0.075; c.lineCap = 'round';
      c.beginPath(); c.moveTo(-0.44, -0.18); c.lineTo(0.18, -0.18); c.arc(0.18, -0.3, 0.12, Math.PI / 2, -Math.PI * 0.9, true); c.stroke();
      c.beginPath(); c.moveTo(-0.44, 0.02); c.lineTo(0.3, 0.02); c.stroke();
      c.beginPath(); c.moveTo(-0.3, 0.2); c.lineTo(0.08, 0.2); c.arc(0.08, 0.31, 0.11, -Math.PI / 2, Math.PI * 0.9, false); c.stroke(); break;
    case 'light':
      c.beginPath(); c.arc(0, 0, 0.17, 0, 7); c.fill();
      for (let k = 0; k < 8; k++) { c.save(); c.rotate(k * Math.PI / 4); P(k % 2 ? [[0, -0.36], [0.05, -0.25], [-0.05, -0.25]] : [[0, -0.5], [0.07, -0.26], [-0.07, -0.26]]); c.restore(); }
      break;
    case 'dark':
      c.beginPath(); c.arc(0, 0, 0.4, 0, 7); c.fill();
      c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.arc(0.13, -0.1, 0.33, 0, 7); c.fill(); c.globalCompositeOperation = 'source-over';
      for (const [x, y, r] of [[0.2, 0.22, 0.05], [0.32, -0.3, 0.035], [-0.02, -0.36, 0.03]]) { c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); }
      break;
  }
}
// 属性图标颜色：[剪影顶部, 剪影底部, 方框内衬光]
const ELEM_ICON = {
  fire: ['#ffd25a', '#ff4a1c', 'rgba(255,90,30,.35)'],
  ice: ['#e8fbff', '#5cc8ff', 'rgba(80,190,255,.32)'],
  lightning: ['#fff7a0', '#ffc81e', 'rgba(255,210,40,.32)'],
  wind: ['#d8ffb8', '#46d06a', 'rgba(70,210,110,.3)'],
  light: ['#ffffff', '#ffe88a', 'rgba(255,240,170,.35)'],
  dark: ['#e2b4ff', '#8a3cdc', 'rgba(150,70,230,.38)'],
};
function iconCanvas(ty, s) {
  const key = ty + s;
  if (ICON_CACHE[key]) return ICON_CACHE[key];
  const k = 2, cv2 = document.createElement('canvas'); cv2.width = cv2.height = s * k;
  const c = cv2.getContext('2d'), S = s * k;
  // 底框：深色、细银边、顶部略亮，接近原作敌人弱点栏的小方块
  const g = c.createLinearGradient(0, 0, 0, S); g.addColorStop(0, '#3a3644'); g.addColorStop(1, '#15121c');
  c.fillStyle = g; c.fillRect(0, 0, S, S);
  c.strokeStyle = '#8c8698'; c.lineWidth = k; c.strokeRect(k / 2, k / 2, S - k, S - k);
  c.strokeStyle = 'rgba(0,0,0,.8)'; c.strokeRect(k * 1.5, k * 1.5, S - k * 3, S - k * 3);
  // 剪影：先画深色描边层，再画白色本体
  const tmp = document.createElement('canvas'); tmp.width = tmp.height = S; const tc = tmp.getContext('2d');
  tc.translate(S / 2, S / 2); tc.scale(S * 0.88, S * 0.88); const EC = ELEM_ICON[ty];
  if (EC) { // 属性图标按原作配色：剪影用渐变上色，方框内衬一层同色微光
    const gg = tc.createLinearGradient(0, -0.5, 0, 0.5); gg.addColorStop(0, EC[0]); gg.addColorStop(1, EC[1]);
    tc.fillStyle = tc.strokeStyle = gg;
    const rg = c.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S * 0.6); rg.addColorStop(0, EC[2]); rg.addColorStop(1, 'rgba(0,0,0,0)');
    c.fillStyle = rg; c.fillRect(k * 2, k * 2, S - k * 4, S - k * 4);
  } else tc.fillStyle = tc.strokeStyle = '#f4efe2';
  iconGlyph(tc, ty);
  c.save(); c.filter = 'drop-shadow(0 0 1px #000) drop-shadow(0 0 1px #000)'; c.drawImage(tmp, 0, 0); c.restore();
  c.drawImage(tmp, 0, 0);
  return (ICON_CACHE[key] = cv2);
}
function typeIcon(x, y, ty, s = 22, flash = 0) {
  ctx.save(); ctx.imageSmoothingEnabled = true;
  ctx.drawImage(iconCanvas(ty, s), x, y, s, s);
  if (flash > 0) { // 打中弱点时图标闪光，和原作一样
    ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = flash;
    ctx.fillStyle = TYPE_COL[ty] || '#fff'; ctx.fillRect(x - 2, y - 2, s + 4, s + 4);
    ctx.strokeStyle = '#fff6c0'; ctx.lineWidth = 2; ctx.strokeRect(x - 3, y - 3, s + 6, s + 6);
  }
  ctx.restore();
}
function shieldBadge(x, y, n, broken) {
  ctx.save(); ctx.translate(x, y);
  ctx.beginPath(); ctx.moveTo(0, -16); ctx.lineTo(14, -10); ctx.lineTo(12, 8); ctx.lineTo(0, 17); ctx.lineTo(-12, 8); ctx.lineTo(-14, -10); ctx.closePath();
  const g = ctx.createLinearGradient(0, -16, 0, 17);
  if (broken) { g.addColorStop(0, '#7a2a2a'); g.addColorStop(1, '#3a1010'); } else { g.addColorStop(0, '#c9d4e4'); g.addColorStop(1, '#5a6880'); }
  ctx.fillStyle = g; ctx.fill(); ctx.strokeStyle = '#1a1222'; ctx.lineWidth = 2; ctx.stroke();
  ctx.restore();
  txt(broken ? '×' : String(n), x, y + 1, 20, broken ? '#ffb0a0' : '#ffffff', 'center');
}

function drawFieldUI(time) {
  for (let t = 0; t < 2; t++) for (let i = 0; i < D[t].length; i++) {
    const u = D[t][i]; if (!u.alive) continue;
    const [hx, hy] = homePos(t, i); const a = A[t][i];
    // 护盾和弱点显示在脚边、朝向场地中央一侧（原作敌人的护盾也在脚下）；
    // 前排角色站得更低更靠外，图标条往场内偏，免得压在前排角色身上
    const [x, y] = toScr(hx + a.dx, hy + 4);
    const w = TR[u.key].weak;
    const total = 34 + w.length * 26;
    const sx = t === 0 ? x + 32 : x - 32 - total;
    shieldBadge(sx + 14, y, u.sh, u.brk);
    w.forEach((ty, k) => typeIcon(sx + 31 + k * 26, y - 12, ty, 24, u.wkTy === ty ? Math.max(0, 1 - (now - u.wkT) / 650) : 0));
    if (u.brk) txt('破防', sx + 14, y - 26, 18, '#ffd060', 'center');
    // 当前行动者箭头
    if (curRef && curRef[0] === t && curRef[1] === i) {
      const [ax, ay] = toScr(hx + a.dx, hy - 60);
      const bob = Math.sin(time * 0.008) * 4;
      ctx.fillStyle = TEAM_COL[t]; ctx.beginPath(); ctx.moveTo(ax - 9, ay + bob); ctx.lineTo(ax + 9, ay + bob); ctx.lineTo(ax, ay + 12 + bob); ctx.fill();
    }
  }
}

let curRef = null;
function drawPanels() {
  // 仿原作：队伍状态竖排在画面两侧，每人一条斜切的半透明条，当前行动者的条向场内滑出
  const pw = 270, rh = 112, top = 200;
  for (let t = 0; t < 2; t++) {
    const L = t === 0, px = L ? 0 : W - pw;
    const X = d => L ? px + d : px + pw - d;            // 从外侧量起的横坐标
    const AL = L ? 'left' : 'right', AR = L ? 'right' : 'left';
    // 队名牌
    const hg = ctx.createLinearGradient(X(0), 0, X(220), 0); hg.addColorStop(0, 'rgba(8,6,16,.85)'); hg.addColorStop(1, 'rgba(8,6,16,0)');
    ctx.fillStyle = hg; ctx.fillRect(L ? px : W - 220, top - 40, 220, 30);
    txt(R.bots[t], X(18), top - 25, 19, TEAM_COL[t], AL);
    D[t].forEach((u, i) => {
      const tr = TR[u.key], y = top + i * rh;
      const isCur = curRef && curRef[0] === t && curRef[1] === i;
      const off = isCur ? 18 : 0, Xo = d => X(d + off);
      // 斜切底条：外侧不透明、向场内渐隐，底边一道金线
      ctx.save();
      const g = ctx.createLinearGradient(X(0), 0, X(pw + off), 0);
      g.addColorStop(0, isCur ? 'rgba(46,36,20,.92)' : 'rgba(10,8,20,.86)'); g.addColorStop(0.75, isCur ? 'rgba(46,36,20,.7)' : 'rgba(10,8,20,.6)'); g.addColorStop(1, 'rgba(10,8,20,0)');
      ctx.fillStyle = g; ctx.beginPath();
      ctx.moveTo(X(0), y + 4); ctx.lineTo(X(pw - 10 + off), y + 4); ctx.lineTo(X(pw - 26 + off), y + rh - 6); ctx.lineTo(X(0), y + rh - 6); ctx.closePath(); ctx.fill();
      const lg = ctx.createLinearGradient(X(0), 0, X(pw + off), 0); lg.addColorStop(0, 'rgba(214,190,130,.9)'); lg.addColorStop(1, 'rgba(214,190,130,0)');
      ctx.fillStyle = lg; ctx.fillRect(L ? X(0) : X(pw - 26 + off), y + rh - 7, pw - 26 + off, 1);
      if (isCur) { ctx.fillStyle = TEAM_COL[t]; ctx.fillRect(L ? X(0) : X(4), y + 4, 4, rh - 10); }
      ctx.restore();
      // 头像
      ctx.save(); ctx.globalAlpha = u.alive ? 1 : 0.4; ctx.imageSmoothingEnabled = false;
      const pxp = L ? Xo(12) : Xo(12) - 42;
      ctx.fillStyle = 'rgba(0,0,0,.5)'; ctx.fillRect(pxp - 1, y + 9, 44, 44);
      drawFace(u.key, !L, pxp, y + 10, 42);
      ctx.strokeStyle = 'rgba(214,190,130,.7)'; ctx.lineWidth = 1; ctx.strokeRect(pxp - 0.5, y + 9.5, 43, 43);
      ctx.restore();
      // 名字、职业
      txt(tr.name, Xo(64), y + 20, tr.name.length >= 5 ? 18 : 20, u.alive ? '#f6ecd4' : '#8a8090', AL);
      const sub = (LOS[t][i] || {}).sub_job;
      txt(u.alive ? tr.job + (sub ? ' / ' + (JOBZ[sub] || sub) : '') : '倒下', Xo(64), y + 42, 14, u.alive ? '#bfae88' : '#ff8a8a', AL, false);
      // BP 球（名字同一行靠场内一侧）
      for (let k = 0; k < 5; k++) {
        const on = k < u.bp, cx = Xo(178 + k * 15), cy = y + 20;
        const gg = ctx.createRadialGradient(cx - 2, cy - 2, 1, cx, cy, 7);
        if (on) { gg.addColorStop(0, '#fff6c0'); gg.addColorStop(0.5, '#ffc040'); gg.addColorStop(1, '#c06a10'); } else { gg.addColorStop(0, '#4a4256'); gg.addColorStop(1, '#1c1726'); }
        ctx.fillStyle = gg; ctx.beginPath(); ctx.arc(cx, cy, 6, 0, 6.28); ctx.fill();
        ctx.strokeStyle = on ? 'rgba(255,230,160,.8)' : 'rgba(120,110,140,.6)'; ctx.lineWidth = 1; ctx.stroke();
      }
      // 潜力槽
      const lw = 70, lxp = L ? Xo(171) : Xo(171) - lw;
      bar(lxp, y + 36, lw, 5, u.lat / 100, u.lat >= 100 ? '#ffe070' : '#ffb060', u.lat >= 100 ? '#ff7a20' : '#a05020');
      if (u.lat >= 100) txt('潜力', L ? lxp + lw + 4 : lxp - 4, y + 39, 13, '#ffd070', AL, true);
      // HP / SP
      const hpw = 116, spw = 104;
      const hx = L ? Xo(14) : Xo(14) - spw - 16 - hpw, sx = L ? Xo(146) : Xo(14) - spw; // 两侧都是 HP 在前、SP 在后
      txt('HP', hx, y + 61, 14, '#cfe6c0', 'left');
      const [mhp, msp] = MAXHS(t, i);
      txt(String(u.hp), hx + hpw, y + 59, 20, u.hp < mhp * 0.25 ? '#ff9a7a' : '#ffffff', 'right');
      bar(hx, y + 70, hpw, 6, u.hp / mhp, '#9cf07a', '#3c9a3a');
      txt('SP', sx, y + 61, 14, '#c0d8f0', 'left');
      txt(String(u.sp), sx + spw, y + 59, 20, '#ffffff', 'right');
      bar(sx, y + 70, spw, 6, u.sp / msp, '#8ad0ff', '#2a68b8');
      // 增益/减益/状态图标：条的下方一行，像原作一样是带箭头的小图标，右下角是剩余回合
      const icons = [];
      for (const [k, n] of Object.entries(u.up)) icons.push(['up', k, n]);
      for (const [k, n] of Object.entries(u.down)) icons.push(['down', k, n]);
      for (const [k, n] of Object.entries(u.st)) if (STATUS_ZH[k]) icons.push(['st', k, n]);
      if (u.tier > 1) icons.push(['st', 'tier' + u.tier, 0]);
      if (u.mat >= 0) icons.push(['st', 'mat', u.mat]);
      const IS = 29, max = Math.floor((pw - 24) / (IS + 3));
      icons.slice(0, max).forEach(([kind, k, n], j) => {
        const bx = L ? Xo(12) + j * (IS + 3) : Xo(12) - IS - j * (IS + 3), by = y + 77;
        ctx.save(); ctx.globalAlpha = u.alive ? 1 : 0.45; ctx.imageSmoothingEnabled = true;
        ctx.drawImage(statusIcon(kind, k), bx, by, IS, IS);
        if (n > 0) txt(String(n), bx + 4, by + IS - 5, 14, '#ffffff', 'left', true, true);
        ctx.restore();
      });
    });
    // 道具袋（全队共用）
    const bag = BAG[t] || {}, by0 = top + D[t].length * rh + 6, nb = Object.values(bag).filter(n => n > 0).length;
    if (Object.keys(BAGS[t] || {}).length) {
      const bh2 = 34 + Math.max(1, Math.min(5, nb)) * 26;
      const g2 = ctx.createLinearGradient(X(0), 0, X(pw), 0); g2.addColorStop(0, 'rgba(10,8,20,.8)'); g2.addColorStop(1, 'rgba(10,8,20,0)');
      ctx.fillStyle = g2; ctx.fillRect(L ? X(0) : X(pw), by0, pw, bh2);
      txt('道具袋', X(14), by0 + 16, 17, '#d8c48e', AL);
      if (!nb) txt('已用完', X(84), by0 + 16, 16, '#9a8f80', AL, false);
      drawBagList(X(14), by0 + 42, pw - 40, bag, L, 1, 17, 26, 5);
    }
  }
}

// 道具袋：像素图标 + 名字 ×个数，按列排；L=false 时从右往左对齐
function drawBagList(x, y, w, bag, L = true, cols = 2, size = 15, rowH = 24, maxRows = 99) {
  const ents = Object.entries(bag || {}).filter(([, n]) => n > 0);
  const cw = w / cols;
  ents.slice(0, cols * maxRows).forEach(([id, n], j) => {
    const c = j % cols, r = Math.floor(j / cols);
    const cx = L ? x + c * cw : x - (c + 1) * cw, cy = y + r * rowH;
    const [kd, col] = itemKind(id);
    ctx.save(); ctx.translate(cx + 9, cy); ctx.scale(2, 2); itemPix(ctx, 0, 0, kd, col); ctx.restore();
    txt(`${(ITN[id] || {}).zh || id}`, cx + 22, cy + 1, size, '#f0e2c0', 'left', false);
    ctx.font = `700 ${size}px ${FONT}`;
    txt(`×${n}`, cx + cw - 10, cy + 1, size, '#ffe08a', 'right', true);
  });
  return Math.ceil(ents.length / cols);
}

// ------------------------------------------------------------------ 状态栏小图标（原创矢量绘制，48×48 缓存，画成 24×24）
// 增益：金框 + 右下红色上箭头；减益：紫框 + 蓝色下箭头；状态：好的金框、坏的紫框
const ST_ICON_CACHE = {};
const BAD_ST = { poison: 1, poison_weak: 1, leghold: 1 };
function statusIcon(kind, key) {
  const id = kind + key; if (ST_ICON_CACHE[id]) return ST_ICON_CACHE[id];
  const c = mk(48, 48), g = c.getContext('2d'), bad = kind === 'down' || BAD_ST[key];
  // 底座
  const bg = g.createLinearGradient(0, 0, 0, 48);
  bg.addColorStop(0, bad ? '#3a2148' : '#3a2e22'); bg.addColorStop(1, bad ? '#170c22' : '#15100a');
  g.fillStyle = bg; rr(g, 2, 2, 44, 44, 8); g.fill();
  g.lineWidth = 2.5; g.strokeStyle = bad ? '#b277d8' : '#e4c278'; rr(g, 2.5, 2.5, 43, 43, 8); g.stroke();
  g.strokeStyle = 'rgba(255,255,255,.18)'; g.lineWidth = 1; rr(g, 5.5, 5.5, 37, 37, 6); g.stroke();
  // 图案
  g.save(); g.translate(kind === 'st' ? 24 : 21, kind === 'st' ? 24 : 23);
  g.lineCap = 'round'; g.lineJoin = 'round';
  const ink = '#f6e8c8', P = (f) => { g.beginPath(); f(); };
  const glyph = {
    pa() { g.rotate(-Math.PI / 4); g.fillStyle = ink; g.fillRect(-2.5, -15, 5, 21); P(() => { g.moveTo(-2.5, -15); g.lineTo(0, -19); g.lineTo(2.5, -15); }); g.fill(); g.fillStyle = '#d8a84a'; g.fillRect(-8, 6, 16, 3.5); g.fillRect(-1.8, 9, 3.6, 7); },
    pd() { g.fillStyle = ink; P(() => { g.moveTo(0, -15); g.lineTo(13, -10); g.lineTo(11, 4); g.quadraticCurveTo(7, 12, 0, 16); g.quadraticCurveTo(-7, 12, -11, 4); g.lineTo(-13, -10); g.closePath(); }); g.fill(); g.fillStyle = '#8a6a3a'; P(() => { g.moveTo(0, -10); g.lineTo(0, 12); g.lineTo(-8, 3); g.lineTo(-8.5, -7); g.closePath(); }); g.fill(); },
    ea() { g.strokeStyle = '#c9a060'; g.lineWidth = 3; P(() => { g.moveTo(-10, 15); g.lineTo(4, -2); }); g.stroke(); const og = g.createRadialGradient(6, -8, 1, 6, -6, 10); og.addColorStop(0, '#ffffff'); og.addColorStop(0.5, '#9fd8ff'); og.addColorStop(1, '#3a70d0'); g.fillStyle = og; P(() => g.arc(6, -6, 8, 0, 6.28)); g.fill(); spark(g, -9, -10, 4, '#fff6c8'); },
    ed() { glyph.pd(); const og = g.createRadialGradient(0, -1, 1, 0, 0, 7); og.addColorStop(0, '#ffffff'); og.addColorStop(1, '#5aa0ff'); g.fillStyle = og; P(() => g.arc(0, 0, 6, 0, 6.28)); g.fill(); },
    spd() { g.strokeStyle = ink; g.lineWidth = 4.5; for (const x of [-8, 4]) { P(() => { g.moveTo(x, -11); g.lineTo(x + 9, 0); g.lineTo(x, 11); }); g.stroke(); } },
    crit() { g.fillStyle = '#ffd860'; P(() => { for (let i = 0; i < 16; i++) { const r = i % 2 ? 6 : 16, an = i / 16 * 6.28 - Math.PI / 2; g.lineTo(Math.cos(an) * r, Math.sin(an) * r); } g.closePath(); }); g.fill(); g.fillStyle = '#fff8e0'; P(() => g.arc(0, 0, 4, 0, 6.28)); g.fill(); },
    acc() { g.strokeStyle = ink; g.lineWidth = 3; P(() => g.arc(0, 0, 11, 0, 6.28)); g.stroke(); P(() => { g.moveTo(0, -17); g.lineTo(0, -6); g.moveTo(0, 6); g.lineTo(0, 17); g.moveTo(-17, 0); g.lineTo(-6, 0); g.moveTo(6, 0); g.lineTo(17, 0); }); g.stroke(); g.fillStyle = '#ff7050'; P(() => g.arc(0, 0, 3, 0, 6.28)); g.fill(); },
    eva() { g.rotate(Math.PI / 5); g.fillStyle = ink; P(() => { g.moveTo(0, -17); g.quadraticCurveTo(11, -4, 0, 15); g.quadraticCurveTo(-11, -4, 0, -17); }); g.fill(); g.strokeStyle = '#8a7a5a'; g.lineWidth = 1.6; P(() => { g.moveTo(0, -12); g.lineTo(0, 18); for (let k = -8; k < 10; k += 5) { g.moveTo(0, k); g.lineTo(5, k - 4); g.moveTo(0, k); g.lineTo(-5, k - 4); } }); g.stroke(); },
    poison() { const dg = g.createLinearGradient(0, -16, 0, 14); dg.addColorStop(0, '#d79bff'); dg.addColorStop(1, '#7a2fb8'); g.fillStyle = dg; P(() => { g.moveTo(0, -16); g.bezierCurveTo(6, -6, 12, 0, 12, 5); g.arc(0, 5, 12, 0, Math.PI); g.bezierCurveTo(-12, 0, -6, -6, 0, -16); }); g.fill(); g.fillStyle = 'rgba(255,255,255,.7)'; P(() => g.arc(-4, 4, 3, 0, 6.28)); g.fill(); P(() => g.arc(4, 9, 2, 0, 6.28)); g.fill(); },
    poison_weak() { glyph.poison(); g.strokeStyle = '#2a0c3a'; g.lineWidth = 2.5; P(() => { g.moveTo(-2, -8); g.lineTo(3, -1); g.lineTo(-3, 5); g.lineTo(2, 12); }); g.stroke(); },
    immune() { glyph.pd(); g.fillStyle = '#5ad070'; g.fillRect(-2.5, -9, 5, 18); g.fillRect(-9, -2.5, 18, 5); },
    taunt() { g.fillStyle = '#ff5a3a'; P(() => g.arc(0, 0, 15, 0, 6.28)); g.fill(); g.fillStyle = '#fff2d8'; g.fillRect(-2.6, -10, 5.2, 13); P(() => g.arc(0, 8, 3, 0, 6.28)); g.fill(); },
    counter() { g.strokeStyle = ink; g.lineWidth = 3.5; P(() => g.arc(0, 0, 12, -Math.PI * 0.15, Math.PI * 1.25)); g.stroke(); g.fillStyle = ink; P(() => { g.moveTo(12, -8); g.lineTo(16, 2); g.lineTo(6, 0); g.closePath(); }); g.fill(); g.rotate(-Math.PI / 4); g.fillStyle = '#ffd070'; g.fillRect(-1.6, -9, 3.2, 14); g.fillRect(-5, 4, 10, 2.5); },
    sidestep() { for (const [x, a] of [[-9, 0.3], [-3, 0.55], [4, 1]]) { g.globalAlpha = a; g.fillStyle = ink; P(() => g.arc(x, -9, 4.5, 0, 6.28)); g.fill(); P(() => { g.moveTo(x - 5, 15); g.lineTo(x - 4, -3); g.lineTo(x + 4, -3); g.lineTo(x + 5, 15); g.closePath(); }); g.fill(); } g.globalAlpha = 1; },
    sacred() { g.strokeStyle = '#ffe48a'; g.lineWidth = 3; P(() => g.ellipse(0, -11, 11, 4, 0, 0, 6.28)); g.stroke(); g.fillStyle = '#fff6d0'; g.fillRect(-2.5, -4, 5, 20); g.fillRect(-8, 1, 16, 5); },
    regen() { g.fillStyle = '#6ae08a'; g.fillRect(-3.5, -13, 7, 26); g.fillRect(-13, -3.5, 26, 7); g.strokeStyle = '#c8ffd0'; g.lineWidth = 2; P(() => g.arc(0, 0, 16, -0.6, 1.2)); g.stroke(); },
    leghold() { g.strokeStyle = '#d0d0d8'; g.lineWidth = 3; P(() => g.arc(0, 2, 13, Math.PI, 0)); g.stroke(); g.fillStyle = '#d0d0d8'; P(() => { for (let k = -12; k <= 8; k += 5) { g.moveTo(k, 2); g.lineTo(k + 2.5, -5); g.lineTo(k + 5, 2); } }); g.fill(); g.fillRect(-15, 3, 30, 4); g.strokeStyle = '#9a8a70'; g.lineWidth = 2; P(() => { g.moveTo(0, 7); g.lineTo(0, 15); }); g.stroke(); },
    extra() { spark(g, 0, 0, 15, '#fff0a0'); spark(g, 9, -9, 5, '#ffffff'); },
    spread() { g.fillStyle = '#ff7ab8'; P(() => { g.moveTo(0, 14); g.bezierCurveTo(-18, 2, -12, -16, 0, -6); g.bezierCurveTo(12, -16, 18, 2, 0, 14); }); g.fill(); g.fillStyle = 'rgba(255,255,255,.6)'; P(() => g.arc(-6, -4, 3, 0, 6.28)); g.fill(); },
    charity() { const cg = g.createRadialGradient(-3, -4, 1, 0, 0, 14); cg.addColorStop(0, '#fff2b0'); cg.addColorStop(1, '#c08a20'); g.fillStyle = cg; P(() => g.arc(0, 0, 13, 0, 6.28)); g.fill(); g.strokeStyle = '#7a5410'; g.lineWidth = 2; P(() => g.arc(0, 0, 9, 0, 6.28)); g.stroke(); g.fillStyle = '#7a5410'; g.fillRect(-1.5, -6, 3, 12); },
    tier2() { glyph.ea(); roman(g, 'II'); },
    tier3() { glyph.ea(); roman(g, 'III'); },
    ward() { g.fillStyle = '#cfe8ff'; P(() => { g.moveTo(-5, -15); g.lineTo(5, -15); g.lineTo(5, -7); g.quadraticCurveTo(14, -2, 13, 6); g.quadraticCurveTo(12, 15, 0, 15); g.quadraticCurveTo(-12, 15, -13, 6); g.quadraticCurveTo(-14, -2, -5, -7); g.closePath(); }); g.fill(); g.fillStyle = '#5ab0ff'; P(() => { g.moveTo(-11, 3); g.lineTo(11, 3); g.quadraticCurveTo(11, 13, 0, 13); g.quadraticCurveTo(-11, 13, -11, 3); }); g.fill(); g.fillStyle = '#8a6a3a'; g.fillRect(-6, -18, 12, 4); g.fillStyle = '#ffffff'; g.fillRect(-1.5, -1, 3, 10); g.fillRect(-5, 2.5, 10, 3); },
    mat() { g.fillStyle = '#b08850'; P(() => { g.moveTo(-12, -4); g.lineTo(12, -4); g.lineTo(10, 14); g.lineTo(-10, 14); g.closePath(); }); g.fill(); g.fillStyle = '#7a5a30'; g.fillRect(-12, -8, 24, 5); g.fillStyle = '#7fe0a0'; P(() => g.arc(-4, -12, 4, 0, 6.28)); g.fill(); g.fillStyle = '#ff9a80'; P(() => g.arc(5, -12, 4, 0, 6.28)); g.fill(); },
  };
  (glyph[key] || glyph.extra)();
  g.restore();
  // 角标箭头
  if (kind !== 'st') {
    const up = kind === 'up';
    g.fillStyle = up ? '#ff4a2a' : '#3a8cff'; g.strokeStyle = '#140a14'; g.lineWidth = 2;
    g.beginPath();
    if (up) { g.moveTo(37, 24); g.lineTo(46, 34); g.lineTo(41, 34); g.lineTo(41, 44); g.lineTo(33, 44); g.lineTo(33, 34); g.lineTo(28, 34); }
    else { g.moveTo(37, 46); g.lineTo(46, 36); g.lineTo(41, 36); g.lineTo(41, 26); g.lineTo(33, 26); g.lineTo(33, 36); g.lineTo(28, 36); }
    g.closePath(); g.stroke(); g.fill();
  }
  return (ST_ICON_CACHE[id] = c);
}
function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function spark(g, x, y, r, col) { g.fillStyle = col; g.beginPath(); for (let i = 0; i < 8; i++) { const rr2 = i % 2 ? r * 0.32 : r, an = i / 8 * 6.28 - Math.PI / 2; g.lineTo(x + Math.cos(an) * rr2, y + Math.sin(an) * rr2); } g.closePath(); g.fill(); }
function roman(g, t) { g.font = `900 15px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineWidth = 3.5; g.strokeStyle = '#10142a'; g.strokeText(t, -6, 10); g.fillStyle = '#ffffff'; g.fillText(t, -6, 10); }

function drawOrder(time) {
  if (!order.length) return;
  const x0 = 18, y0 = 14;
  panelBox(x0, y0, 120 + order.length * 46, 62, 0.6);
  txt(`第 ${roundNo} 回合`, x0 + 18, y0 + 31, 20, '#f0e0b0');
  order.forEach((r, k) => {
    const x = x0 + 112 + k * 46, y = y0 + 12;
    const key = M.picks[r[0]][r[1]], u = D[r[0]][r[1]];
    const done = acted.has(r.join()), isCur = curRef && curRef[0] === r[0] && curRef[1] === r[1];
    ctx.save();
    ctx.globalAlpha = (!u.alive || u.brk) ? 0.25 : done && !isCur ? 0.45 : 1;
    ctx.fillStyle = 'rgba(0,0,0,.6)'; ctx.fillRect(x, y + (isCur ? -6 : 0), 40, 40);
    drawFace(key, r[0] === 1, x + 2, y + 2 + (isCur ? -6 : 0), 36);
    ctx.strokeStyle = TEAM_COL[r[0]]; ctx.lineWidth = isCur ? 3 : 2; ctx.strokeRect(x, y + (isCur ? -6 : 0), 40, 40);
    ctx.restore();
  });
}

function drawBanner() {
  if (!banner) return;
  const p = Math.min(1, (now - banner.t0) / 200);
  const w = 620, h = 64, x = W / 2 - w / 2, y = 90;
  ctx.save(); ctx.globalAlpha = p;
  const g = ctx.createLinearGradient(x, 0, x + w, 0);
  g.addColorStop(0, 'rgba(10,6,20,0)'); g.addColorStop(0.15, 'rgba(10,6,20,.82)'); g.addColorStop(0.85, 'rgba(10,6,20,.82)'); g.addColorStop(1, 'rgba(10,6,20,0)');
  ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
  ctx.fillStyle = 'rgba(214,190,130,.8)'; ctx.fillRect(x + 60, y, w - 120, 1); ctx.fillRect(x + 60, y + h - 1, w - 120, 1);
  txt(banner.zh, W / 2, y + 26, 28, '#fff4d8', 'center');
  txt(`${banner.who}（${banner.job}）`, W / 2, y + 50, 16, TEAM_COL[banner.team], 'center', false);
  ctx.restore();
}

// 赛前配置公开卡：两队各 4 行，头像 + 本职/副职 + 学了几个副职技能 + 4 个支援技能
function drawLoadoutCard() {
  if (!loCard) return;
  const age = now - loCard.t0;
  if (age > loCard.dur) { loCard = null; return; }
  const a = Math.min(1, age / 300, (loCard.dur - age) / 300);
  ctx.save(); ctx.globalAlpha = Math.max(0, a);
  ctx.fillStyle = 'rgba(4,3,10,.62)'; ctx.fillRect(0, 0, W, H);
  const bagRows = Math.min(3, Math.max(...BAGS.map(b => Math.ceil(Object.keys(b || {}).length / 3)))), hasBag = bagRows > 0;
  const bw = 1360, bh = 704 + (hasBag ? 10 + bagRows * 24 : 0), bx = (W - bw) / 2, by = (H - bh) / 2;
  panelBox(bx, by, bw, bh, 0.86);
  txt('赛前配置公开', W / 2, by + 40, 34, '#fff1d0', 'center');
  txt('双方同时提交，互相看不到；战斗开始时公开', W / 2, by + 74, 17, '#cdbb90', 'center', false);
  const cw = bw / 2, rh = 134;
  for (let t = 0; t < 2; t++) {
    const cx = bx + t * cw + 24;
    txt(R.bots[t], cx, by + 112, 24, TEAM_COL[t], 'left');
    M.picks[t].forEach((k, i) => {
      const lo = LOS[t][i] || {}, tr = TR[k], y = by + 128 + i * rh;
      ctx.fillStyle = 'rgba(255,255,255,.04)'; ctx.fillRect(cx - 8, y, cw - 32, rh - 8);
      ctx.save(); ctx.imageSmoothingEnabled = false; drawFace(k, t === 1, cx, y + 10, 64); ctx.restore();
      ctx.strokeStyle = 'rgba(214,190,130,.7)'; ctx.lineWidth = 1; ctx.strokeRect(cx - 0.5, y + 9.5, 65, 65);
      const tx = cx + 82;
      txt(tr.name, tx, y + 26, 26, '#f6ecd4', 'left');
      const sub = lo.sub_job ? (JOBZ[lo.sub_job] || lo.sub_job) : '无';
      const nlearn = lo.sub_job ? 2 + (lo.learn || []).length : 0;
      ctx.font = `700 26px ${FONT}`;
      txt(`${tr.job} ｜ 副职 ${sub}${lo.sub_job ? `（会 ${nlearn}/8 个技能）` : ''}`, tx + ctx.measureText(tr.name).width + 18, y + 27, 19, '#e2cf9c', 'left', false);
      const [mhp, msp] = MAXHS(t, i);
      txt(`HP ${mhp}  SP ${msp}`, tx, y + 56, 18, '#bcd7c0', 'left', false);
      const sups = (lo.supports || []).map(s => (SUPN[s] || {}).zh || s);
      if (!sups.length) txt('支援技能：无', tx, y + 86, 18, '#9a8f80', 'left', false);
      sups.forEach((s, j) => {
        const col = j % 2, row = j >> 1, sx = tx + col * 270, sy = y + 86 + row * 29;
        ctx.fillStyle = 'rgba(228,194,120,.16)'; ctx.fillRect(sx - 4, sy - 13, 262, 26);
        txt('◆ ' + s, sx, sy + 1, 18, '#f3dfae', 'left', false);
      });
    });
    if (hasBag) {
      const y = by + 128 + 4 * rh;
      txt('道具', cx, y + 14, 18, '#e2cf9c', 'left');
      if (!Object.keys(BAGS[t] || {}).length) txt('不带道具', cx + 56, y + 14, 17, '#9a8f80', 'left', false);
      drawBagList(cx + 56, y + 14, cw - 90, BAGS[t], true, 3, 15, 24, 3);
    }
  }
  ctx.restore();
}

function drawBig() {
  if (!bigText || (CLEAN && bigText.ui)) return;
  const age = now - bigText.t0;
  if (age > bigText.dur) { bigText = null; return; }
  const p = Math.min(1, age / 250), fade = bigText.dur < 1e8 ? Math.min(1, (bigText.dur - age) / 250) : 1;
  ctx.save(); ctx.globalAlpha = Math.max(0, Math.min(p, fade));
  const y = bigText.small ? H * 0.36 : H * 0.42;
  if (!bigText.small) { const g = ctx.createLinearGradient(0, y - 60, 0, y + 60); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.5, 'rgba(0,0,0,.55)'); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(0, y - 60, W, 120); }
  const sz = (bigText.small ? 64 : 72) * (1.25 - 0.25 * p);
  ctx.shadowColor = bigText.col; ctx.shadowBlur = 24;
  txt(bigText.text, W / 2, y, sz, bigText.col, 'center');
  ctx.shadowBlur = 0;
  if (bigText.sub) txt(bigText.sub, W / 2, y + sz * 0.62, 22, bigText.team !== undefined && bigText.team >= 0 ? TEAM_COL[bigText.team] : '#f0e6d0', 'center');
  ctx.restore();
}

function drawTexts() {
  texts = texts.filter(t => now - t.t0 < t.dur);
  for (const t of texts) {
    const p = (now - t.t0) / t.dur;
    const y = t.y - 40 * Math.min(1, p * 2.5) + (p > 0.7 ? 0 : 0);
    ctx.save(); ctx.globalAlpha = p > 0.75 ? (1 - p) / 0.25 : 1;
    txt(t.text, t.x, y, t.size * (p < 0.08 ? 1.4 - p * 5 : 1), t.color, 'center');
    ctx.restore();
  }
}

// ---------- 选人界面
function drawPick(time) {
  const keys = Object.keys(TR);
  lx.clearRect(0, 0, LW, LH);
  lx.drawImage(midC, 0, 0);
  keys.forEach((k, i) => {
    const x = 72 + i * 48, y = 175 + (i % 2) * 14;
    lx.fillStyle = 'rgba(20,10,30,0.45)'; lx.beginPath(); lx.ellipse(x, y, 11, 3, 0, 0, 6.28); lx.fill();
    drawBattleActor(k, x, y, 0, time, {}, { alive: 1, brk: 0 }, i);
  });
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(farBlur, 0, 0);
  ctx.drawImage(low, CAM.x * ART_SCALE, CAM.y * ART_SCALE, CAM.w * ART_SCALE, CAM.h * ART_SCALE, 0, 0, W, H);
  ctx.drawImage(foreBlur, 0, 0);
  drawGlow(time);
  ctx.drawImage(grade, 0, 0);
  if (CLEAN) return;
  panelBox(W / 2 - 260, 40, 520, 70);
  txt('选择旅人', W / 2, 66, 30, '#fff1d0', 'center');
  txt(M.pick_mode === 'draft' ? '蛇形轮流选人（不可重复）' : '双方同时盲选（可以选到相同角色）', W / 2, 94, 15, '#cdbb90', 'center', false);
  keys.forEach((k, i) => {
    const [x, y] = toScr(72 + i * 48, 175 + (i % 2) * 14);
    txt(TR[k].name, x, y + 26, 18, '#f4ead2', 'center');
    txt(TR[k].job, x, y + 46, 13, '#cdbb90', 'center', false);
    for (let t = 0; t < 2; t++) {
      const idx = pickShown[t].indexOf(k);
      if (idx >= 0) {
        const bx = x + (t === 0 ? -34 : 4), by = y - 170;
        ctx.fillStyle = TEAM_COL[t]; ctx.fillRect(bx, by, 30, 26);
        txt(`${'AB'[t]}${idx + 1}`, bx + 15, by + 14, 15, '#0a0612', 'center', true, false);
      }
    }
  });
  for (let t = 0; t < 2; t++) txt(`${R.bots[t]}：${pickShown[t].map(k => TR[k].name).join('、') || '……'}`, t === 0 ? 30 : W - 30, H - 120, 20, TEAM_COL[t], t === 0 ? 'left' : 'right');
}

function frame(time) {
  if (!CAP.on) {
    const dt = lastT ? Math.min(100, time - lastT) : 16; lastT = time; now = time;
    tickTimeline(dt); animDecay(dt);
    ctx.save(); renderFrame(time); ctx.restore();
  }
  requestAnimationFrame(frame);
}
function renderFrame(time) {
  outSize();
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, OW, OH); // 每帧从黑底开始，不叠上一帧残留（逐帧录制要求同一帧画出来完全一样）
  curRef = null;
  const f = F[cur];
  if (D && playing && steps.length) { for (const e of f.ev) if (e.e === 'turn') curRef = e.u; }
  if (!curRef && D && !playing && f.cur) curRef = f.cur;
  if (!curRef && D && (!steps.length || si >= steps.length) && f.cur) curRef = f.cur;
  if (!D) {
    ctx.save(); useWorld(); drawPick(time); ctx.restore();
    ctx.save(); useOverlay(); drawBig(); drawLoadoutCard(); ctx.restore();
    return;
  }
  // 低分辨率中景 + 角色
  lx.clearRect(0, 0, LW, LH);
  lx.drawImage(midC, 0, 0);
  // 火把火焰
  for (const [tx, ty] of TORCHES) {
    for (let k = 0; k < 6; k++) { const h = 3 + rnd(k + Math.floor(time / 90)) * 5; lx.fillStyle = k % 2 ? '#ffd060' : '#ff7a2a'; lx.fillRect(tx - 2 + (k % 3), ty - 2 - h | 0, 2, h | 0); }
  }
  const draws = [];
  for (let t = 0; t < 2; t++) for (let i = 0; i < D[t].length; i++) draws.push([homePos(t, i)[1], t, i]);
  draws.sort((a, b) => a[0] - b[0]);
  for (const [, t, i] of draws) drawUnitLow(t, i, time);
  drawEffectsLow(time);
  // 画面比舞台宽或高时（竖屏），先用模糊压暗的场景铺满背景
  const [ws, wx, wy] = worldXf();
  if (wx > 0.5 || wy > 0.5 || wx + W * ws < OW - 0.5 || wy + H * ws < OH - 0.5) {
    ctx.save();
    const cs = Math.max(OW / CAM.w, OH / CAM.h) * 1.1;
    ctx.filter = 'blur(28px) brightness(0.45)'; ctx.imageSmoothingEnabled = true;
    ctx.drawImage(low, CAM.x * ART_SCALE, CAM.y * ART_SCALE, CAM.w * ART_SCALE, CAM.h * ART_SCALE, OW / 2 - CAM.w * cs / 2, OH / 2 - CAM.h * cs / 2, CAM.w * cs, CAM.h * cs);
    ctx.restore();
  }
  ctx.save(); useWorld(); ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  ctx.imageSmoothingEnabled = true; // 景深模糊层放大时要平滑，像素层保持锐利
  ctx.drawImage(farBlur, 0, 0);
  let ox = 0, oy = 0;
  if (shakeFx) { const q = (now - shakeFx.t0) / shakeFx.dur; if (q >= 1) shakeFx = null; else { ox = Math.sin(now * 0.09) * shakeFx.amp * (1 - q); oy = Math.cos(now * 0.13) * shakeFx.amp * 0.6 * (1 - q); } }
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(low, CAM.x * ART_SCALE, CAM.y * ART_SCALE, CAM.w * ART_SCALE, CAM.h * ART_SCALE, ox, oy, W, H);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(foreBlur, 0, 0);
  drawGlow(time);
  ctx.drawImage(grade, 0, 0);
  ctx.imageSmoothingEnabled = false;
  if (!CLEAN) drawFieldUI(time);
  ctx.restore();
  // 竖屏时舞台上下边缘压暗，和模糊背景衔接得柔和一些
  if (wy > 0.5) for (const [y0, y1] of [[wy, wy + 90 * ws], [wy + H * ws, wy + H * ws - 90 * ws]]) {
    const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, 'rgba(0,0,0,.7)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.fillRect(0, Math.min(y0, y1), OW, Math.abs(y1 - y0));
  }
  if (flashFx) { const q = (now - flashFx.t0) / flashFx.dur; if (q >= 1) flashFx = null; else { ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.fillStyle = `rgba(${flashFx.col},${0.38 * (1 - q)})`; ctx.fillRect(0, 0, OW, OH); ctx.restore(); } }
  ctx.save(); useOverlay();
  if (!CLEAN) { drawOrder(time); drawPanels(); }
  drawCutin();
  if (!CLEAN) drawBanner();
  ctx.restore();
  ctx.save(); useWorld(); drawTexts(); ctx.restore();
  ctx.save(); useOverlay(); drawBig(); drawLoadoutCard(); ctx.restore();
}

// ------------------------------------------------------------------ 控件、日志
const playBtn = document.getElementById('play');
function updatePlay() { playBtn.textContent = playing ? '❚❚ 暂停' : '▶ 播放'; }
playBtn.onclick = () => { if (cur >= F.length - 1 && (!steps.length || si >= steps.length)) gotoFrame(0); playing = !playing; updatePlay(); };
document.getElementById('speed').onchange = e => speed = +e.target.value;
seek.oninput = () => { gotoFrame(+seek.value); };
document.getElementById('prev').onclick = () => { playing = false; updatePlay(); gotoFrame(cur - 1); };
document.getElementById('next').onclick = () => { playing = false; updatePlay(); gotoFrame(cur + 1); };
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
  if (e.code === 'ArrowLeft') document.getElementById('prev').click();
  if (e.code === 'ArrowRight') document.getElementById('next').click();
});
function updateInfo() {
  const f = F[cur];
  document.getElementById('info').textContent = `第 ${cur} / ${F.length - 1} 步` + (f.r ? ` · 第 ${f.r} 回合` : ' · 选人');
}

// 文字战报
const logEl = document.getElementById('log');
const logRows = [];
function describe(fi) {
  const fr = F[fi], out = [];
  let line = null;
  for (const e of fr.ev) {
    if (e.e === 'pick') out.push(`<b style="color:${TEAM_COL[e.team]}">${R.bots[e.team]}</b> 选择 ${e.picks.map(k => TR[k].name).join('、')}${e.auto ? '（超时/非法，随机分配）' : ''}`);
    else if (e.e === 'loadout') out.push(`<b style="color:${TEAM_COL[e.team]}">${R.bots[e.team]}</b> 配置：` + M.picks[e.team].map((k, i) => {
      const lo = LOS[e.team][i] || {};
      return `${TR[k].name}（副职 ${lo.sub_job ? JOBZ[lo.sub_job] || lo.sub_job : '无'}${(lo.supports || []).length ? '，支援 ' + lo.supports.map(s => (SUPN[s] || {}).zh || s).join('/') : ''}）`;
    }).join('；') + `；道具 ${Object.entries(BAGS[e.team] || {}).map(([k, n]) => `${(ITN[k] || {}).zh || k}×${n}`).join('、') || '无'}`
      + (e.notes && e.notes.length ? `<span class="ko">（忽略：${e.notes.join('；')}）</span>` : ''));
    else if (e.e === 'sup') { const s = `<span class="lt">${nm(e.u)} 支援技能「${(SUPN[e.k] || {}).zh || e.k}」</span>`; if (line) line.parts.push(s); else out.push(s); }
    else if (e.e === 'round') out.push(`<span class="rd">— 第 ${e.r} 回合 —</span>`);
    else if (e.e === 'latent') out.push(`<span class="lt">${nmT(e.u)} 发动潜力「${M.latent[e.name]}」</span>`);
    else if (e.e === 'skill') {
      const sn = e.s === 'attack' ? `攻击（${TYPE_ZH[e.w]}）` : e.s === 'concoct' ? `调合·${M.recipes[e.r]}` : e.s === 'item' ? `道具·${(ITN[e.it] || {}).zh || e.it}` : (SKN[e.s] || {}).zh || e.s;
      const b = fr.a && fr.a.boost ? ` <span class="bp">增幅×${fr.a.boost}</span>` : '';
      line = { head: `${nmT(e.u)} 使用 <b>${sn}</b>${b}`, parts: [] }; out.push(line);
    }
    else if (e.e === 'hit' && line) line.parts.push(e.miss ? `${nm(e.t)} ${e.dodge ? '闪避' : '未命中'}` : `${nm(e.t)} -${e.d}${e.w ? '<span class="wk">弱</span>' : ''}${e.c ? '<span class="cr">暴</span>' : ''}`);
    else if (e.e === 'heal' && line) line.parts.push(`${nm(e.t)} +${e.v}`);
    else if (e.e === 'revive' && line) line.parts.push(`${nm(e.t)} 复活`);
    else if (e.e === 'cure' && line) line.parts.push(`${nm(e.t)} 解毒`);
    else if (e.e === 'break') { if (line) line.parts.push(`<span class="brk">${nm(e.t)} 破防！</span>`); else out.push(`<span class="brk">${nm(e.t)} 破防！</span>`); }
    else if (e.e === 'ko') { if (line) line.parts.push(`<span class="ko">${nm(e.t)} 倒下</span>`); else out.push(`<span class="ko">${nm(e.t)} 倒下</span>`); }
    else if (e.e === 'end') out.push(`<b class="end">${e.winner === -1 ? '平局' : R.bots[e.winner] + ' 获胜'}${e.reason === 'rounds' ? '（回合数用尽，按剩余 HP 判定）' : ''}</b>`);
  }
  return out.map(o => typeof o === 'string' ? o : o.head + (o.parts.length ? '：' + o.parts.join('，') : '')).join('<br>');
}
function nmT(ref) { return `<span style="color:${TEAM_COL[ref[0]]}">${nm(ref)}</span>`; }
for (let i = 1; i < F.length; i++) {
  const html = describe(i); if (!html) continue;
  const d = document.createElement('div'); d.className = 'row'; d.innerHTML = html; d.dataset.f = i;
  d.onclick = () => { playing = false; updatePlay(); gotoFrame(i - 1); playing = true; updatePlay(); };
  logEl.appendChild(d); logRows.push(d);
}
function highlightLog() {
  for (const d of logRows) d.classList.toggle('on', +d.dataset.f === cur);
}

// 统计表
const stats = document.getElementById('stats');
stats.innerHTML = '<tr><th>队伍</th><th>旅人</th><th>结果</th><th>超时/非法</th><th>平均思考</th><th>最长</th></tr>' +
  R.stats.map((s, i) => `<tr><td style="color:${TEAM_COL[i]}">${s.name}</td><td>${M.picks[i].map(k => TR[k].name).join('、')}</td><td>${R.scores[i]}</td><td>${s.timeouts} / ${M.fallbacks[i]}</td><td>${s.avg_ms ?? '-'} ms</td><td>${s.max_ms} ms</td></tr>`).join('');
document.getElementById('na').textContent = R.bots[0];
document.getElementById('nb').textContent = R.bots[1];
document.getElementById('sc').textContent = `${R.scores[0]} : ${R.scores[1]}`;

gotoFrame(0);
requestAnimationFrame(frame);
const sfxBtn = document.getElementById('sfx');
function updateSfx() { sfxBtn.textContent = !SFX.on ? '🔈 音效关' : SFX.ready ? '🔊 音效开' : '🔇 点一下开声音'; }
// 浏览器要求先有一次点击才能出声：还没解锁时点按钮只负责解锁，不切换开关
sfxBtn.onclick = () => { if (SFX.on && !SFX.ready) SFX.init(); else SFX.toggle(); updateSfx(); };
SFX.onState = updateSfx; updateSfx();
const cutBtn = document.getElementById('cut');
function updateCut() { cutBtn.textContent = CUT_ON ? '🎬 特写开' : '🎬 特写关'; }
cutBtn.onclick = () => {
  CUT_ON = !CUT_ON; try { localStorage.setItem('op_cutin', CUT_ON ? '1' : '0'); } catch (e) {}
  if (!CUT_ON) cutin = null;
  updateCut();
}; updateCut();
Promise.all([BATTLE_READY, FONT_READY]).then(() => setTimeout(() => { if (!CAP.on) { playing = true; updatePlay(); } }, 600));

// ------------------------------------------------------------------ 逐帧录制接口
// tick = 回放的第几步（0..ticks-1，与进度条一致），frac = 这一步动画进行到的比例（0..1）。
// seek 会从前一步开头按 1/fps 的固定步长重新推演到目标时刻，所以同样的 (tick, frac) 每次画出来完全一样，
// 上一步残留的伤害数字等也能接上。录制期间不出声、不自动播放。
if (CLEAN) document.documentElement.classList.add('clean');
const CUM = [0]; // CUM[t] = 第 t 步动画开始的全局时间（毫秒）
const durOf = t => (t >= 1 && t < F.length ? plan(t).reduce((a, x) => a + x.d, 0) : 0);
for (let t = 1; t <= F.length; t++) CUM[t] = CUM[t - 1] + durOf(t - 1);
function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
window.arenaCapture = {
  ticks: F.length,
  fps: CAP.fps,
  get width() { outSize(); return OW; },
  get height() { outSize(); return OH; },
  // 立绘、头像、字体都就绪后再开始截图
  ready: Promise.all([...Object.values(PORTRAIT_IMG), ...Object.values(CUTIN_IMG)].map(im => im.decode ? im.decode().catch(() => {}) : null)
    .concat([BATTLE_READY, FONT_READY], document.fonts ? [document.fonts.ready] : [])).then(() => true),
  artworkStatus() { return { ready: BATTLE_LOADED, error: BATTLE_ERROR, characters: Object.keys(KIT_CHAR).length ? Object.keys(KIT_CHAR) : Object.keys(BATTLE_ART), kit: Object.keys(KIT_CHAR).length > 0, effects: Object.keys(KIT_FX) }; },
  duration(t) { return durOf(t); },                                     // 这一步动画的毫秒数
  frames(t) { return Math.max(1, Math.round(durOf(t) * CAP.fps / 1000)); }, // 按 fps 需要截多少帧
  seek(t, frac = 0) {
    CAP.on = true; speed = 1;
    t = Math.max(0, Math.min(F.length - 1, t | 0));
    const d = durOf(t), target = Math.max(0, Math.min(d - 0.01, frac * d));
    const start = Math.max(0, t - 2);
    rng = mulberry(t * 7919 + 17);
    gotoFrame(start);
    effects = []; texts = []; shakeFx = null; flashFx = null; cutin = null; banner = null;
    now = CUM[start + 1] || 0;
    if (t > start) {
      playing = true;
      let left = CUM[t] - CUM[start + 1] + target;
      startNext();
      const DT = 1000 / CAP.fps;
      while (left > 1e-6) { const s = Math.min(DT, left); now += s; tickTimeline(s); animDecay(s); left -= s; }
      while (cur < t && si >= steps.length) { finishFrame(); if (!startNext()) break; }
      playing = false;
    }
    return { tick: cur, ms: target, time: now };
  },
  render() { ctx.save(); renderFrame(now); ctx.restore(); },
  // 推近：zoom 相对默认取景，(cx, cy) 是 1440×810 舞台坐标；不传则回到默认
  view(zoom = 1, cx = W / 2, cy = H / 2) { VIEW = { z: Math.max(0.2, +zoom || 1), cx: +cx, cy: +cy }; },
  // 某个旅人当前在舞台上的位置（身体中部），给 view 用
  unit(team, idx) { if (!D) return null; const [x, y] = scrPos([team, idx], -22); return { x, y, key: D[team][idx].key, name: TR[D[team][idx].key].name }; },
  find(key) { const r = []; M.picks.forEach((p, t) => p.forEach((k, i) => { if (k === key) r.push([t, i]); })); return r; },
};
