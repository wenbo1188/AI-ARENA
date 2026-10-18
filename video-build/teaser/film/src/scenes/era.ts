// 0:26.25–0:46.875 `era` ×3 — a hard cut straight into each era's real footage (rendered by the arena's own replay
// viewers), the era and the game named large on the first bar while that era's stroke of the command seal burns
// away in the corner, then one action played through to its result, cut on the beats:
//   中世纪｜八方旅人   增幅 → 破防 → 潜能命中
//   1987｜CodeSide     走位 → 交火击杀 → 爆炸
//   2087｜机器人足球    氮气起跳击球 → 撞墙反弹 → 入网 (the ball crosses the line on the bar, film 45.0)
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { Layer2D, W, H } from '../engine/gl';
import * as GL from '../engine/gl';
import { ease, frameIdx, lerp, prog, pulse } from '../engine/util';
import { makeTimeWarp, ERA_COL } from './_timewarp';
import { cjk, drawRule, loadCJK, revealText } from './_film';
import { Footage, makeGrade } from './_footage';
import { GRADES, drawShot, prepareShots, shotAt, type Shot } from './_shots';

const BEAT = 0.46875;
const B = (n: number) => n * BEAT;

interface Era {
  num: string; name: string; latin: string; game: string;
  /** the year the big number rolls up from (time moving on from the last era) */
  from?: number;
  /** the two AIs in this match, left and right, in their team colours */
  vs: [[string, string], [string, string]];
  shots: Shot[];
  end: number;
}

const ERAS: Era[] = [
  {
    num: '第一战', name: '中世纪', latin: 'MEDIEVAL', game: '八方旅人',
    vs: [['OPUS 5.5', '#6fb4ff'], ['GPT6-Astra', '#ff7a6e']],
    shots: [
      // v10 (mrwang: not only 光, and each traveler's own job skills; replay seed 12): 奥兹巴尔多 boosts under the card,
      // the cut-in names his AI, fire magic hits the whole line and breaks one guard
      { clip: 'o10_fire', t0: 0, t1: B(4), frames: [[0, 0], [B(4), 42, ease.linear]], zoom: [[0, 1.0], [B(4), 1.06]] },
      // v10c (mrwang: check the beat sync): every cut on a beat and every impact on a strong beat (beats 1 and 3);
      // the close-ups cut in on the impact itself, then let it ring out in slow motion
      { clip: 'o10_fire', t0: B(4), t1: B(6), frames: [[B(4), 44], [B(6), 108, ease.linear]] },
      { clip: 'o10_fire_hit', t0: B(6), t1: B(8), frames: [[B(6), 47], [B(6) + 0.08, 50, ease.linear], [B(8), 98, ease.outQuad]], tag: '火焰魔法 · 破防' },
      // GPT6-Astra answers: 欧修缇's 瓦解, 5142, down
      { clip: 'o10_break', t0: B(8), t1: B(10), frames: [[B(8), 0], [B(10), 62, ease.linear]] },
      { clip: 'o10_break_hit', t0: B(10), t1: B(12), frames: [[B(10), 44], [B(10) + 0.08, 47, ease.linear], [B(12), 104, ease.outQuad]], tag: '瓦解 · 倒下 5142' },
      // and OPUS 5.5's last one standing: 光, boost ×3, latent 双月闪 across the whole line
      { clip: 'o10_moon', t0: B(12), t1: B(14), frames: [[B(12), 20], [B(14), 104, ease.linear]] },
      { clip: 'o10_moon_hit', t0: B(14), t1: B(16), frames: [[B(14), 70], [B(14) + 0.08, 73, ease.linear], [B(16), 140, ease.outQuad]], zoom: [[B(14), 1.0], [B(16), 1.05]], tag: '潜力技 · 双月闪' },
    ],
    end: B(16),
  },
  {
    num: '第二战', from: 1350, name: '1987', latin: 'THE PIXEL YEARS', game: '枪战对决',
    vs: [['DeepSeek v4.1 Flash', '#ffad82'], ['GLM-5.3-Flash', '#93b8ff']],
    shots: [
      { clip: 'cs9a', t0: 0, t1: B(4), frames: [[0, 0], [B(4), 152, ease.linear]], zoom: [[0, 1.0], [B(4), 1.04]], tag: '走位 · 交火' },
      { clip: 'cs9b', t0: B(4), t1: B(8), frames: [[B(4), 20], [B(6), 80, ease.linear], [B(8), 130, ease.outQuad]], zoom: [[B(4), 1.0], [B(8), 1.05]], tag: '火箭 · 击杀' },
      { clip: 'cs9c', t0: B(8), t1: B(12), frames: [[B(8), 10], [B(10), 74, ease.linear], [B(12), 120, ease.outQuad]], zoom: [[B(8), 1.0], [B(12), 1.06]], tag: '反击 · 击杀' },
    ],
    end: B(12),
  },
  {
    num: '第三战', from: 1987, name: '2087', latin: 'THE ARENA OF MACHINES', game: '机器人足球',
    vs: [['Minimax-M3.1-Flash-Preview', '#8ff0b4'], ['GPT6-Astra', '#ff8f8f']],
    shots: [
      { clip: 'f8_holo', t0: 0, t1: B(4), frames: [[0, 0], [B(4), 119, ease.linear]] },
      { clip: 'f8_strike', t0: B(4), t1: B(8), frames: [[B(4), 18], [B(6), 91, ease.inOutQuad], [B(8), 179, ease.linear]], tag: '氮气 · 起跳击球' },
      { clip: 'f8_goal', t0: B(8), t1: B(12), frames: [[B(8), 22], [B(10), 65, ease.linear], [B(12), 150, ease.linear]], tag: '撞墙 · 反弹' },
      { clip: 'f8_net', t0: B(12), t1: B(16), frames: [[B(12), 116], [B(12) + 0.08, 121, ease.linear], [B(16), 190, ease.outQuad]], tag: '入网' },
    ],
    end: B(16),
  },
];

export default class EraScene extends Scene {
  era!: Era;
  e = 0;
  foot = new Footage(48);
  grade = makeGrade();
  text = new Layer2D();
  scan = makeScan();
  warp = makeTimeWarp();
  rt = GL.makeRT();

  override async init() {
    await loadCJK();
    await document.fonts.load('600 40px "Cormorant-600"', '1987 2087');
    this.e = (this.ctx.params?.era as number) ?? 0;
    this.era = ERAS[this.e]!;
  }

  override async prepare(t0: number, t1: number) {
    await prepareShots(this.foot, this.era.shots, t0 - this.ctx.start, t1 - this.ctx.start);
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    const lt = f.lt, t = f.t, E = this.era, G = GRADES[this.e]!;
    const shot = shotAt(E.shots, lt) ?? E.shots[E.shots.length - 1]!;
    const L = this.text; L.clear();
    const x2 = L.ctx;
    x2.textBaseline = 'alphabetic';

    // the time jump: out of this era on its last beat, into it on its first (no words, mrwang 2026-10-11)
    const kOut = this.e < ERAS.length - 1 ? ease.inCubic(prog(lt, E.end - 0.42, E.end)) : 0;
    const kIn = 1 - ease.outCubic(prog(lt, 0, 0.55));
    const warping = kOut > 0 || kIn > 0;
    const dst = warping ? this.rt : out;
    const first = shot === E.shots[0];
    const punch = drawShot(renderer, dst, this.foot, this.grade, shot, lt, G, { punch: first ? 1.1 : 0.8 });
    if (G.scan) { this.scan.u.k!.value = G.scan; this.scan.render(renderer, dst); }

    // the big card on the first bar: era｜game, then it settles into a corner tag
    const card = 1 - prog(lt, 1.6, 1.85);
    if (card > 0) {
      const band = x2.createLinearGradient(0, H - 420, 0, H);
      band.addColorStop(0, 'rgba(0,0,0,0)'); band.addColorStop(1, `rgba(0,0,0,${0.62 * card})`);
      x2.fillStyle = band; x2.fillRect(0, H - 420, W, 420);
      const latin = /^\d/.test(E.name);
      x2.font = latin ? '600 132px "Cormorant-600"' : cjk('serif', 900, 112);
      const nameW = measure(x2, E.name, latin ? 20 : 26);
      x2.font = cjk('serif', 800, 88);
      const gameW = measure(x2, E.game, 12);
      const sep = 70, total = nameW + sep + gameW, x0 = W / 2 - total / 2, y = H - 150;
      x2.font = latin ? '600 132px "Cormorant-600"' : cjk('serif', 900, 112);
      // the year rolls forward from the last era to this one, then settles
      const roll = E.from !== undefined && lt < 0.75 ? String(Math.round(lerp(E.from, +E.name, ease.outCubic(prog(lt, 0.05, 0.75))))) : E.name;
      revealText(x2, roll, x0, y, {
        lt: lt - 0.05, stagger: 0.05, dur: 0.35, rise: 16, blur: 14, alpha: card, tracking: latin ? 20 : 26,
        fill: (a, yy) => { const g = x2.createLinearGradient(0, yy - 110, 0, yy + 8); g.addColorStop(0, '#fff6e4'); g.addColorStop(1, '#e0a24a'); return g; },
        glow: { color: 'rgba(0,0,0,0.85)', blur: 22 },
      });
      // the bar between
      x2.save(); x2.globalAlpha = card * prog(lt, 0.15, 0.35); x2.fillStyle = '#e8b04a';
      x2.fillRect(x0 + nameW + sep / 2 - 2, y - 92, 4, 104); x2.restore();
      x2.font = cjk('serif', 800, 88);
      revealText(x2, E.game, x0 + nameW + sep, y, { lt: lt - 0.25, stagger: 0.05, dur: 0.35, rise: 12, blur: 12, alpha: card, fill: '#f6efe2', tracking: 12, glow: { color: 'rgba(0,0,0,0.85)', blur: 22 } });
      x2.font = '500 18px "Plex-500"';
      revealText(x2, `${E.latin}`, W / 2, y + 52, { lt: lt - 0.4, stagger: 0.015, dur: 0.3, rise: 0, blur: 0, align: 'center', alpha: 0.8 * card, fill: 'rgba(232,176,74,1)', tracking: 8 });
      x2.font = cjk('serif', 700, 34);
      revealText(x2, E.num, W / 2, H - 340, { lt: lt - 0.0, stagger: 0.05, dur: 0.3, rise: 6, blur: 6, align: 'center', alpha: 0.9 * card, fill: '#f3ead6', tracking: 18, glow: { color: 'rgba(0,0,0,0.9)', blur: 16 } });
      drawRule(x2, W / 2, H - 316, 260, prog(lt, 0.1, 0.5), `rgba(232,176,74,${0.7 * card})`);
    } else {
      const tg = lt - 1.85;
      const fo = 1 - prog(lt, E.end - 0.25, E.end);
      const band = x2.createLinearGradient(0, H - 170, 0, H);
      band.addColorStop(0, 'rgba(0,0,0,0)'); band.addColorStop(1, `rgba(0,0,0,${0.45 * fo})`);
      x2.fillStyle = band; x2.fillRect(0, H - 170, 900, 170);
      const latin = /^\d/.test(E.name);
      x2.font = latin ? '600 46px "Cormorant-600"' : cjk('serif', 700, 36);
      const w = revealText(x2, E.name, 72, H - 70, { lt: tg, stagger: 0.02, dur: 0.25, rise: 6, blur: 6, alpha: fo, fill: '#ffd98e', tracking: 6 });
      x2.font = cjk('serif', 700, 36);
      revealText(x2, `｜${E.game}`, 72 + w + 6, H - 70, { lt: tg - 0.08, stagger: 0.02, dur: 0.25, rise: 6, blur: 6, alpha: fo, fill: '#f3ead6', tracking: 6 });
    }
    // the action caption, bottom right, per shot
    if (shot.tag && lt > 1.85) {
      const k = lt - Math.max(shot.t0, 1.85);
      const fo = 1 - prog(lt, shot.t1 - 0.12, shot.t1);
      x2.font = cjk('sans', 700, 40);
      x2.save(); x2.globalAlpha = fo * prog(k, 0, 0.15);
      const tw = measure(x2, shot.tag, 6);
      const g = x2.createLinearGradient(W - 140 - tw, 0, W, 0);
      g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.3, 'rgba(0,0,0,0.45)'); g.addColorStop(1, 'rgba(0,0,0,0.55)');
      x2.fillStyle = g; x2.fillRect(W - 160 - tw, H - 136, tw + 160, 84);
      x2.fillStyle = '#e8b04a'; x2.fillRect(W - 92 - tw - 20, H - 112, 4, 36);
      x2.restore();
      revealText(x2, shot.tag, W - 80, H - 78, { lt: k, stagger: 0.03, dur: 0.22, rise: 6, blur: 6, align: 'right', alpha: fo, fill: '#fff4dc', tracking: 6, glow: { color: 'rgba(0,0,0,0.85)', blur: 14 } });
    }
    // who is fighting: the two AIs named at the top, in their team colours
    drawVs(x2, E, lt);
    // this era's stroke of the seal burns away at the top right
    drawSealPips(x2, W - 190, 96, this.e, lt);
    this.ctx.comp.draw(renderer, L.upload(), dst);
    if (warping) {
      const u = this.warp.u;
      u.src!.value = this.rt.texture; u.kOut!.value = kOut; u.kIn!.value = kIn; u.time!.value = t;
      u.dir!.value = this.e === 0 && kIn > 0 ? -1 : 1;
      const a = ERA_COL[kOut > 0 ? this.e : Math.max(0, this.e - 1)]!, b = ERA_COL[kOut > 0 ? this.e + 1 : this.e]!;
      (u.colA!.value as THREE.Vector3).set(...a); (u.colB!.value as THREE.Vector3).set(...b);
      this.warp.render(renderer, out);
    }

    const k = lt - shot.t0;
    const fiN = frameIdx(t);
    const hit = pulse(k, 0, 0.1) * (first ? 1 : 0.6);
    const shake: [number, number] = hit > 0.05 ? [Math.sin(fiN * 2.3) * 6 * hit, Math.cos(fiN * 1.7) * 6 * hit] : [0, 0];
    return {
      bloom: 0.35, bloomThreshold: 1.0, halation: 0.2, grain: 0.05, vignette: 0.35,
      ca: 1.0 + 2.5 * punch, flash: first ? 0.3 * pulse(lt, 0, 0.07) : 0.1 * pulse(k, 0, 0.05), shake,
    };
  }
}

/** “AI 对战  OPUS 5.5 VS GPT6-Astra” on one slim dark strip at the top left: these are the AIs playing. (Kept to the top
 *  90 px: the replays draw their own names, numbers and labels just below.) */
function drawVs(c: CanvasRenderingContext2D, E: Era, lt: number) {
  const a = prog(lt, 0.2, 0.45) * (1 - prog(lt, E.end - 0.25, E.end));
  if (a <= 0) return;
  const x = 56, y = 72;
  c.font = cjk('sans', 700, 26);
  const wk = measure(c, 'AI 对战', 4);
  c.font = cjk('sans', 800, 46);
  const w0 = measure(c, E.vs[0][0], 1), w1 = measure(c, E.vs[1][0], 1);
  c.font = 'italic 600 46px "Cormorant-600"';
  const wv = c.measureText('VS').width, gap = 18;
  const nx = x + wk + 34, total = nx - x + w0 + gap + wv + gap + w1;
  c.save(); c.globalAlpha = a;
  const g = c.createLinearGradient(x - 20, 0, x + total + 90, 0);
  g.addColorStop(0, 'rgba(6,6,12,0.8)'); g.addColorStop(0.75, 'rgba(6,6,12,0.72)'); g.addColorStop(1, 'rgba(6,6,12,0)');
  c.fillStyle = g; c.fillRect(x - 20, y - 56, total + 110, 74);
  c.fillStyle = '#e8b04a'; c.fillRect(x - 20, y - 56, 4, 74);
  c.fillStyle = 'rgba(232,176,74,0.5)'; c.fillRect(x + wk + 16, y - 38, 2, 42);
  c.restore();
  const k = lt - 0.2;
  c.font = cjk('sans', 700, 26);
  revealText(c, 'AI 对战', x, y - 8, { lt: k - 0.05, stagger: 0.03, dur: 0.25, rise: 0, blur: 0, alpha: 0.95 * a, fill: '#e8c88a', tracking: 4 });
  c.font = cjk('sans', 800, 46);
  revealText(c, E.vs[0][0], nx, y, { lt: k, stagger: 0.02, dur: 0.25, rise: 0, blur: 8, alpha: a, fill: E.vs[0][1], tracking: 1 });
  revealText(c, E.vs[1][0], nx + w0 + gap + wv + gap, y, { lt: k - 0.1, stagger: 0.02, dur: 0.25, rise: 0, blur: 8, alpha: a, fill: E.vs[1][1], tracking: 1 });
  c.font = 'italic 600 46px "Cormorant-600"';
  revealText(c, 'VS', nx + w0 + gap, y - 1, { lt: k - 0.05, stagger: 0.04, dur: 0.25, rise: 0, blur: 6, alpha: a, fill: '#ffd98e', tracking: 0 });
}

function measure(c: CanvasRenderingContext2D, s: string, tracking: number) {
  return c.measureText(s).width + tracking * Math.max(0, [...s].length - 1);
}

/** Three diamonds at the corner: the seal's strokes. This era's flares and burns out on the first bar. */
function drawSealPips(c: CanvasRenderingContext2D, x: number, y: number, e: number, lt: number) {
  const burn = prog(lt, 0.2, 1.1, ease.inOutQuad);
  for (let i = 0; i < 3; i++) {
    const px = x + i * 40;
    const spent = i < e || (i === e && burn >= 1);
    const flare = i === e ? pulse(lt, 0.25, 0.35) : 0;
    c.save();
    c.translate(px, y); c.rotate(Math.PI / 4);
    if (spent) { c.strokeStyle = 'rgba(255,120,100,0.55)'; c.lineWidth = 2; c.strokeRect(-9, -9, 18, 18); }
    else {
      const a = i === e ? 1 - burn : 1;
      c.globalAlpha = a; c.fillStyle = '#ff3b2f'; c.shadowColor = '#ff2a1a'; c.shadowBlur = 14 + 30 * flare; c.fillRect(-9, -9, 18, 18);
      if (i === e) { c.globalAlpha = 1 - a; c.strokeStyle = 'rgba(255,120,100,0.55)'; c.lineWidth = 2; c.strokeRect(-9, -9, 18, 18); }
    }
    c.restore();
    // embers off the burning one
    if (i === e && burn > 0 && burn < 1) {
      for (let k = 0; k < 14; k++) {
        const ph = (k * 0.37 + lt * 1.6) % 1, ang = -Math.PI / 2 + Math.sin(k * 7.1) * 0.9;
        const r = 10 + ph * 46;
        c.fillStyle = `rgba(255,${120 + 80 * (1 - ph)},80,${(1 - ph) * (1 - burn) * 0.9})`;
        c.fillRect(px + Math.cos(ang) * r, y + Math.sin(ang) * r, 2.5, 2.5);
      }
    }
  }
  c.font = cjk('sans', 500, 20); c.fillStyle = 'rgba(255,170,150,0.85)'; c.textAlign = 'right';
  c.fillText(`令咒  ${burn < 0.5 ? 3 - e : 2 - e} / 3`, x + 98, y + 44);
  c.textAlign = 'left';
}

/** CRT-ish scanlines for 1987. */
function makeScan() {
  return new GL.FSPass(/* glsl */ `
    uniform float k;
    void main() {
      float y = gl_FragCoord.y;
      float s = 0.5 + 0.5 * sin(y * 3.14159 * 0.5);
      fragColor = vec4(vec3(0.0), k * s);
    }`, { k: { value: 0.1 } }, { blending: THREE.NormalBlending, transparent: true });
}
