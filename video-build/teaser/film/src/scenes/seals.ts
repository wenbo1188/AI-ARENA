// 0:15–0:18.75 `seals` — the one submission. Three panes of code (one per era's game; the middle one large enough
// to read) are written at once, then fold into crimson lines that fly one per beat and burn in as the three strokes
// of the command seal. “赛前提交策略代码，” / “开战后，不得再改一行。”
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { FSPass, Layer2D, W, H } from '../engine/gl';
import { LineBatch } from '../engine/lines';
import { clamp, ease, frameIdx, keys, lerp, mulberry32, prog, pulse } from '../engine/util';
import { aim, cjk, drawRule, loadCJK, revealText, toScreen } from './_film';
import { makeSeal } from './_seal';

const CODE: { head: string; era: string; lines: string[] }[] = [
  {
    head: '第一道命令', era: '中世纪',
    lines: [
      'def decide(msg):',
      '    me = msg["me"][msg["actor"]]',
      '    foes = [u for u in msg["opponents"] if u["alive"]]',
      '    best = max(plans(me, foes), key=value)',
      '    if best.foe["broken"]:',
      '        best.boost = me["bp"]   # 破防，BP 全压',
      '    return best.to_action()',
    ],
  },
  {
    head: '第二道命令', era: '1987',
    lines: [
      'class MyStrategy:',
      '    def get_action(self, unit, game, debug):',
      '        enemy = min(game.units, key=dist)',
      '        aim = Vec2Double(enemy.position.x - unit.position.x,',
      '                         enemy.position.y - unit.position.y)',
      '        return UnitAction(velocity=v, aim=aim,',
      '                          shoot=True)',
    ],
  },
  {
    head: '第三道命令', era: '2087',
    lines: [
      'class MyStrategy:',
      '    def act(self, me, rules, game, action):',
      '        path = self.predict_ball(rules, game.ball, 120)',
      '        hit = self.intercept(me, path)',
      '        action.target_velocity_x = hit.vx',
      '        action.jump_speed = rules.ROBOT_MAX_JUMP_SPEED',
      '        action.use_nitro = True',
    ],
  },
];
const KW = /\b(def|class|return|if|for|in|and|or|not|True|False|None|self|max|min|key)\b/;
const PW = 980, PH = 560; // pane canvas px
const PANE_W = 470, PANE_H = PANE_W * PH / PW;
/** Where each stroke sits in the seal (seal-plane units, size 1 = the seal width): its centroid. */
const STROKE_AT: [number, number][] = [[-0.3, 0.02], [0.3, 0.05], [0, -0.02]];
const SEAL_SIZE = 560;
const SEAL_Y = 50;
/** On the bar (film 16.875) and the next two beats. */
const BURN_IN = [1.875, 2.34375, 2.8125];

export default class Seals extends Scene {
  cam = new THREE.PerspectiveCamera(40, W / H, 1, 9000);
  bg!: FSPass;
  fx = new THREE.Scene();
  panes: { mesh: THREE.Mesh; cv: HTMLCanvasElement; c: CanvasRenderingContext2D; tex: THREE.CanvasTexture; mat: THREE.MeshBasicMaterial }[] = [];
  seal = makeSeal(SEAL_SIZE);
  lines = new LineBatch(2000, { blend: 'add', screen2D: false });
  dust = new LineBatch(1600, { blend: 'add', screen2D: false });
  text = new Layer2D();
  motes: Float32Array = new Float32Array(0);

  override async init() {
    await loadCJK();
    await document.fonts.load('400 20px "Plex-400"', 'def');
    await document.fonts.load('600 40px "Cormorant-600"', '1987');
    this.bg = new FSPass(/* glsl */ `
      uniform float time, red, gold; uniform vec2 res;
      void main() {
        vec2 p = (vUv - 0.5) * vec2(res.x / res.y, 1.0);
        float sm = fbm(vec3(p * 1.6, time * 0.05), 5);
        float sm2 = fbm(vec3(p * 3.2 + 4.0, time * 0.08), 4);
        vec3 c = C_NIGHT * 0.6 + vec3(0.006, 0.008, 0.016);
        c += vec3(0.016, 0.019, 0.03) * smoothstep(-0.1, 0.6, sm) * (0.6 + 0.4 * sm2);
        // the grail far above and behind: a warm wash from the top
        float top = exp(-length(p - vec2(0.0, 0.75)) * 2.2);
        c += C_GOLD * top * 0.22 * gold * (0.7 + 0.3 * sm);
        // crimson bloom behind the seal
        float mid = exp(-length(p - vec2(0.0, 0.05)) * 2.6);
        c += C_CRIMSON * mid * 0.25 * red * (0.6 + 0.6 * smoothstep(-0.3, 0.5, sm2));
        float vg = smoothstep(1.3, 0.3, length(p));
        fragColor = vec4(c * vg, 1.0);
      }`, { time: { value: 0 }, red: { value: 0 }, gold: { value: 1 }, res: { value: new THREE.Vector2(W, H) } });
    for (let i = 0; i < 3; i++) {
      const cv = document.createElement('canvas');
      cv.width = PW; cv.height = PH;
      const c = cv.getContext('2d')!;
      const tex = new THREE.CanvasTexture(cv);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.minFilter = THREE.LinearMipmapLinearFilter;
      tex.anisotropy = 8;
      const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false, premultipliedAlpha: false, color: new THREE.Color(1.5, 1.45, 1.35) });
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(PANE_W, PANE_H), mat);
      this.fx.add(mesh);
      this.panes.push({ mesh, cv, c, tex, mat });
    }
    this.seal.mesh.position.set(0, SEAL_Y, -60);
    this.fx.add(this.seal.mesh);
    const rnd = mulberry32(3);
    this.motes = new Float32Array(500 * 4);
    for (let i = 0; i < 500; i++) { this.motes[i * 4] = rnd(); this.motes[i * 4 + 1] = rnd(); this.motes[i * 4 + 2] = rnd(); this.motes[i * 4 + 3] = rnd(); }
  }

  /** Draw pane i with `k` (0..1) of its characters typed. */
  private drawPane(i: number, k: number, lt: number) {
    const P = this.panes[i]!, c = P.c, d = CODE[i]!;
    c.clearRect(0, 0, PW, PH);
    // glass
    const g = c.createLinearGradient(0, 0, 0, PH);
    g.addColorStop(0, 'rgba(22,26,40,0.78)'); g.addColorStop(1, 'rgba(8,10,18,0.86)');
    c.fillStyle = g;
    c.fillRect(0, 0, PW, PH);
    c.strokeStyle = 'rgba(232,176,74,0.55)'; c.lineWidth = 2;
    c.strokeRect(1, 1, PW - 2, PH - 2);
    // corner ticks
    c.fillStyle = 'rgba(255,226,160,0.9)';
    for (const [x, y] of [[0, 0], [PW, 0], [0, PH], [PW, PH]] as const) {
      c.fillRect(x === 0 ? 0 : PW - 22, y === 0 ? 0 : PH - 4, 22, 4);
      c.fillRect(x === 0 ? 0 : PW - 4, y === 0 ? 0 : PH - 22, 4, 22);
    }
    // header
    c.fillStyle = 'rgba(232,176,74,0.12)';
    c.fillRect(0, 0, PW, 64);
    c.textBaseline = 'middle';
    c.font = cjk('serif', 700, 30);
    c.fillStyle = '#ffe2a0';
    c.fillText(d.head, 30, 34);
    const hw = c.measureText(d.head).width;
    c.fillStyle = 'rgba(232,176,74,0.6)';
    c.fillRect(30 + hw + 18, 33, 26, 2);
    c.font = /^\d/.test(d.era) ? '600 34px "Cormorant-600"' : cjk('serif', 600, 28);
    c.fillStyle = '#f3ead6';
    c.fillText(d.era, 30 + hw + 60, 34);
    c.font = '500 16px "Plex-500"';
    c.fillStyle = 'rgba(232,176,74,0.7)';
    c.textAlign = 'right';
    c.fillText(['strategy_octopath.py', 'strategy_codeside.py', 'strategy_codeball.py'][i]!, PW - 30, 35);
    c.textAlign = 'left';
    // code, typed
    const total = d.lines.reduce((s, l) => s + l.length, 0);
    let left = Math.floor(total * k);
    c.font = '400 25px "Plex-400", "Noto Sans CJK SC"';
    let cx = 0, cy = 0;
    for (let li = 0; li < d.lines.length; li++) {
      const y = 112 + li * 58;
      c.fillStyle = 'rgba(142,155,184,0.45)';
      c.textAlign = 'right';
      c.fillText(String(li + 1), 58, y);
      c.textAlign = 'left';
      if (left <= 0) break;
      const line = d.lines[li]!.slice(0, left);
      left -= d.lines[li]!.length;
      // tokens: comments, strings, keywords, rest
      let x = 82;
      const toks = line.match(/#.*$|"[^"]*"?|\w+|\s+|[^\w\s"#]/g) ?? [];
      for (const t of toks) {
        c.fillStyle = t.startsWith('#') ? 'rgba(232,176,74,0.75)' : t.startsWith('"') ? '#ff9a7a' : KW.test(t) && /^\w+$/.test(t) ? '#ffcf7a' : /^\d/.test(t) ? '#7fe6f0' : 'rgba(240,234,222,0.92)';
        c.fillText(t, x, y);
        x += c.measureText(t).width;
      }
      cx = x; cy = y;
    }
    // caret
    if (k < 1 && Math.floor(lt * 3) % 2 === 0) { c.fillStyle = '#ffe2a0'; c.fillRect(cx + 2, cy - 14, 12, 28); }
    if (k >= 1) {
      c.font = '500 15px "Plex-500"'; c.fillStyle = 'rgba(232,176,74,0.8)'; c.textAlign = 'right';
      c.fillText('✓ READY', PW - 30, PH - 30); c.textAlign = 'left';
    }
    P.tex.needsUpdate = true;
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    const lt = f.lt, t = f.t;
    // camera: a slow dolly in, then a push into the seal at the end
    const z = keys(lt, [[0, 1240], [1.5, 1150, ease.outCubic], [3.0, 1080, ease.inOutCubic], [3.75, 800, ease.inQuart]]);
    const sway = Math.sin(lt * 0.9) * 14;
    aim(this.cam, [sway, 40 + lt * 6, z], [0, 34, 0], -0.01 + 0.006 * lt, 40);

    this.bg.u.time!.value = t;
    this.bg.u.red!.value = prog(lt, 1.8, 2.7, ease.outCubic) * (1 + 0.6 * pulse(lt, BURN_IN[0]!, 0.2));
    this.bg.u.gold!.value = 1 - 0.6 * prog(lt, 1.5, 2.2);
    this.bg.render(renderer, out);

    // panes: fanned on an arc; fold to a line at SUBMIT, then the line contracts and flies to its stroke
    const fold = prog(lt, 1.38, 1.56, ease.inCubic);
    const lb = this.lines; lb.clear();
    for (let i = 0; i < 3; i++) {
      const P = this.panes[i]!;
      const fly = prog(lt, BURN_IN[i]! - 0.32, BURN_IN[i]!, ease.inOutCubic);
      const typed = prog(lt, 0.08 + i * 0.06, 1.25, ease.inOutQuad);
      if (fold < 1) this.drawPane(i, typed, lt);
      const side = i - 1;
      // the middle pane forward and large, the other two behind it to the sides
      const big = side === 0 ? 1.32 : 1;
      const px = side * 590, pz = side === 0 ? 150 : -140, py = 40 + (side === 0 ? 10 : 30);
      const arrive = prog(lt, 0.0 + i * 0.05, 0.4 + i * 0.05, ease.outCubic);
      P.mesh.position.set(px, py - 30 * (1 - arrive), pz - 120 * (1 - arrive));
      P.mesh.rotation.set(0, -side * 0.3, 0);
      P.mesh.renderOrder = side === 0 ? 2 : 1;
      P.mesh.scale.set(big, big * Math.max(0.002, 1 - fold), 1);
      P.mat.opacity = arrive * (1 - fold * 0.6);
      P.mesh.visible = fold < 1;
      P.mat.color.setRGB(1.5 + fold * 4, 1.45 + fold * 0.3, 1.35);
      // the crimson line
      if (fold > 0.6 && fly < 1) {
        const hw = (PANE_W * big / 2) * (1 - fly);
        const [sx, sy] = STROKE_AT[i]!;
        const tx = sx * SEAL_SIZE, ty = SEAL_Y + sy * SEAL_SIZE, tz = -60;
        const e = ease.inOutCubic(fly);
        const cx = lerp(px, tx, e), cy = lerp(py, ty, e) + Math.sin(e * Math.PI) * 60, cz = lerp(pz, tz, e);
        const a = clamp((fold - 0.6) * 3) * (1 + 2 * fly);
        const ca = Math.cos(-side * 0.28 * (1 - e)), sa = Math.sin(-side * 0.28 * (1 - e));
        for (const [wd, al] of [[3.5, 1.0], [12, 0.25], [30, 0.08]] as const)
          lb.seg(cx - hw * ca, cy, cz + hw * sa, cx + hw * ca, cy, cz - hw * sa, wd, 2.6 * a * al, 0.35 * a * al, 0.25 * a * al, 1);
      }
    }

    // seal strokes burn in, glow, then heat up as the camera pushes in
    const su = this.seal.mat.uniforms;
    (su.reveal!.value as THREE.Vector3).set(...(BURN_IN.map((b) => prog(lt, b, b + 0.4, ease.outCubic)) as [number, number, number]));
    const heat = prog(lt, 3.2, 3.75, ease.inQuad);
    (su.hot3!.value as THREE.Vector3).set(...(BURN_IN.map((b) => pulse(lt, b, 0.18) * 0.6 + heat) as [number, number, number]));
    su.time!.value = t;
    su.amp!.value = 0.8 + 0.06 * Math.sin(lt * 5.0);

    renderer.setRenderTarget(out);
    renderer.render(this.fx, this.cam);
    lb.render(renderer, out, this.cam);

    // embers off the seal once it burns, and motes drifting through the void
    const db = this.dust; db.clear();
    const M = this.motes;
    const burnt = prog(lt, BURN_IN[0]!, BURN_IN[0]! + 0.5);
    for (let i = 0; i < 500; i++) {
      const isEmber = i < 260;
      if (isEmber) {
        if (burnt <= 0) continue;
        const life = (M[i * 4 + 3]! * 2.4 + lt * (0.35 + M[i * 4 + 2]! * 0.4)) % 1;
        const ang = M[i * 4]! * Math.PI * 2, r = (0.12 + 0.36 * M[i * 4 + 1]!) * SEAL_SIZE;
        const x = Math.cos(ang) * r * (1 + life * 0.3), y = SEAL_Y + Math.sin(ang) * r * 0.9 + life * 160, zz = -60 + (M[i * 4 + 2]! - 0.5) * 200;
        const a = burnt * Math.sin(life * Math.PI) * (0.6 + heat);
        db.seg(x, y, zz, x + 0.6, y + 2.5, zz, 2.2, 2.4 * a, 0.5 * a, 0.2 * a, 1);
      } else {
        const x = (M[i * 4]! - 0.5) * 2200, zz = (M[i * 4 + 2]! - 0.5) * 1600 - 200;
        const y = ((M[i * 4 + 1]! * 1400 + lt * 14) % 1400) - 600;
        const a = 0.18 * (0.5 + 0.5 * Math.sin(lt * 2 + i));
        db.seg(x, y, zz, x + 0.5, y + 1.5, zz, 1.6, 1.0 * a, 0.8 * a, 0.55 * a, 1);
      }
    }
    db.render(renderer, out, this.cam);

    // typography
    const L = this.text; L.clear();
    const x2 = L.ctx;
    x2.textBaseline = 'alphabetic';
    const fadeA = 1 - prog(lt, 3.35, 3.65);
    if (lt > 0.15) {
      x2.font = '500 15px "Plex-500"';
      revealText(x2, 'SUBMISSION  1 / 1', 132, 120, { lt: lt - 0.15, stagger: 0.015, dur: 0.3, rise: 0, blur: 0, alpha: 0.75 * fadeA, fill: 'rgba(232,176,74,1)', tracking: 4 });
      x2.font = cjk('sans', 400, 17);
      revealText(x2, '每位御主，只有一次提交', 132, 148, { lt: lt - 0.3, stagger: 0.02, dur: 0.3, rise: 0, blur: 0, alpha: 0.7 * fadeA, fill: 'rgba(238,233,223,1)', tracking: 3 });
    }
    if (lt > 0.12) {
      x2.font = cjk('serif', 600, 52);
      revealText(x2, '赛前提交策略代码，', 126, 930, { lt: lt - 0.12, stagger: 0.05, dur: 0.6, rise: 14, blur: 10, alpha: fadeA, fill: '#f3ead6', tracking: 10, glow: { color: 'rgba(0,0,0,0.9)', blur: 18 } });
    }
    if (lt > BURN_IN[0]! - 0.1) {
      x2.font = cjk('serif', 900, 84);
      revealText(x2, '开战后，不得再改一行。', 120, 1026, {
        lt: lt - BURN_IN[0]! + 0.1, stagger: 0.07, dur: 0.6, rise: 18, blur: 14, alpha: fadeA, tracking: 14,
        fill: (a, y) => { const g = x2.createLinearGradient(0, y - 76, 0, y + 6); g.addColorStop(0, '#fff2cf'); g.addColorStop(1, '#e2a443'); return g; },
        glow: { color: 'rgba(255,150,40,0.4)', blur: 24 },
      });
    }
    // stroke labels
    const labels: [string, number, number, 'left' | 'right' | 'center'][] = [['中世纪', -0.47, 0.16, 'right'], ['1987', 0.5, 0.2, 'left'], ['2087', 0.07, 0.4, 'left']];
    const fadeL = 1 - prog(lt, 3.35, 3.65);
    labels.forEach(([s, sx, sy, al], i) => {
      const k = lt - BURN_IN[i]! - 0.15;
      if (k <= 0) return;
      const p = toScreen(this.cam, sx * SEAL_SIZE, SEAL_Y + sy * SEAL_SIZE, -60);
      if (!p) return;
      x2.font = /^\d/.test(s) ? '600 40px "Cormorant-600"' : cjk('serif', 600, 30);
      revealText(x2, s, p.x, p.y, { lt: k, stagger: 0.05, dur: 0.5, rise: 8, blur: 8, align: al, alpha: fadeL, fill: '#ffd9c8', tracking: 6, glow: { color: 'rgba(255,40,30,0.6)', blur: 16 } });
    });
    this.ctx.comp.draw(renderer, L.upload(), out);

    const hit = Math.max(...BURN_IN.map((b) => pulse(lt, b, 0.08)));
    const fi = frameIdx(t);
    return {
      bloom: 0.85, bloomThreshold: 0.8, halation: 0.45, grain: 0.055, vignette: 0.6, ca: 1.3 + 2.5 * heat,
      flash: hit * 0.06 + pulse(lt, 1.45, 0.05) * 0.05 + heat * heat * 0.1,
      shake: hit > 0.05 ? [Math.sin(fi * 2.3) * 5 * hit, Math.cos(fi * 1.9) * 5 * hit] : [0, 0],
      zoom: 1 + heat * 0.04,
    };
  }
}
