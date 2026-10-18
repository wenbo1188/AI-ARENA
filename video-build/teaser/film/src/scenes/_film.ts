// Shared pieces of the film: CJK typography, title reveals, camera helpers.
import * as THREE from 'three';
import { clamp, ease, lerp } from '../engine/util';

type Ctx2 = CanvasRenderingContext2D;

/** System CJK families (Noto CJK SC, all weights installed). */
export const SERIF_CJK = '"Noto Serif CJK SC"';
export const SANS_CJK = '"Noto Sans CJK SC"';
export const cjk = (kind: 'serif' | 'sans', weight: number, px: number) => `${weight} ${px}px ${kind === 'serif' ? SERIF_CJK : SANS_CJK}`;

/** Make sure the CJK faces are decoded before the first frame that uses them (Canvas2D falls back silently). */
export async function loadCJK() {
  const specs = [
    cjk('serif', 900, 40), cjk('serif', 700, 40), cjk('serif', 600, 40), cjk('serif', 500, 40), cjk('serif', 300, 40),
    cjk('sans', 300, 40), cjk('sans', 400, 40), cjk('sans', 500, 40), cjk('sans', 700, 40), cjk('sans', 900, 40),
  ];
  await Promise.all(specs.map((s) => document.fonts.load(s, '圣杯战争御主令咒中世纪年未来召唤从者时代AIGLM0123456789')));
}

/** Per-glyph advances of `text` with extra tracking (px). */
export function glyphRun(c: Ctx2, text: string, tracking: number) {
  const chars = [...text];
  const adv = chars.map((ch) => c.measureText(ch).width);
  const total = adv.reduce((s, a) => s + a, 0) + tracking * Math.max(0, chars.length - 1);
  return { chars, adv, total };
}

export interface RevealOpts {
  /** Time since the reveal started (s). */
  lt: number;
  /** Seconds between consecutive glyphs. */
  stagger?: number;
  /** Seconds each glyph takes to arrive. */
  dur?: number;
  /** Vertical travel (px) of each glyph as it arrives. */
  rise?: number;
  /** Blur (px) of each glyph at the start of its arrival. */
  blur?: number;
  /** Global alpha multiplier (fade-out etc.). */
  alpha?: number;
  align?: 'left' | 'center' | 'right';
  tracking?: number;
  /** Fill style or gradient factory (x0, y, x1) → style. */
  fill: string | ((x0: number, y: number, x1: number) => string | CanvasGradient);
  glow?: { color: string; blur: number };
  /** Solid colour used while a gradient-filled glyph is still blurred. */
  blurColor?: string;
}

/** Draw `text` at (x, y baseline) with a staggered per-glyph arrival (rise + blur + fade). Returns its width. */
export function revealText(c: Ctx2, text: string, x: number, y: number, o: RevealOpts) {
  const tr = o.tracking ?? 0;
  const run = glyphRun(c, text, tr);
  let x0 = o.align === 'center' ? x - run.total / 2 : o.align === 'right' ? x - run.total : x;
  const fill = typeof o.fill === 'function' ? o.fill(x0, y, x0 + run.total) : o.fill;
  const st = o.stagger ?? 0.05, du = o.dur ?? 0.6, rise = o.rise ?? 18, bl = o.blur ?? 10, A = o.alpha ?? 1;
  let cx = x0;
  for (let i = 0; i < run.chars.length; i++) {
    const k = clamp((o.lt - i * st) / du);
    if (k > 0 && A > 0) {
      const e = ease.outCubic(k);
      c.save();
      c.globalAlpha = A * clamp(k * 1.6);
      const b = bl * (1 - e);
      const gy = y + rise * (1 - e);
      if (b > 0.35) {
        // blurred glyph via an offset shadow: canvas \`filter\` makes a full-canvas layer per call (very slow in
        // software); a shadow blur only covers the glyph's bounds
        c.shadowColor = typeof fill === 'string' ? fill : (o.blurColor ?? '#f1d6a0');
        // shadow offset and blur ignore the transform: express them in the current scale
        const m = c.getTransform(), k = Math.hypot(m.a, m.b) || 1;
        c.shadowBlur = b * 2 * k;
        c.shadowOffsetX = 20000 * k; c.shadowOffsetY = 0;
        c.fillStyle = '#000';
        c.fillText(run.chars[i]!, cx - 20000, gy);
      } else {
        if (o.glow) { c.shadowColor = o.glow.color; c.shadowBlur = o.glow.blur; }
        c.fillStyle = fill;
        c.fillText(run.chars[i]!, cx, gy);
      }
      c.restore();
    }
    cx += run.adv[i]! + tr;
  }
  return run.total;
}

/** A thin rule that draws out from its centre (or left) over k in 0..1. */
export function drawRule(c: Ctx2, x: number, y: number, len: number, k: number, color: string, from: 'center' | 'left' = 'center', w = 1) {
  const e = ease.inOutCubic(clamp(k));
  if (e <= 0) return;
  c.save();
  c.strokeStyle = color; c.lineWidth = w;
  c.beginPath();
  if (from === 'center') { c.moveTo(x - (len / 2) * e, y); c.lineTo(x + (len / 2) * e, y); }
  else { c.moveTo(x, y); c.lineTo(x + len * e, y); }
  c.stroke();
  c.restore();
}

/** Set a perspective camera from position/target/roll. */
export function aim(cam: THREE.PerspectiveCamera, p: [number, number, number], target: [number, number, number], roll = 0, fov?: number) {
  if (fov !== undefined && cam.fov !== fov) { cam.fov = fov; cam.updateProjectionMatrix(); }
  cam.position.set(p[0], p[1], p[2]);
  cam.up.set(Math.sin(roll), Math.cos(roll), 0);
  cam.lookAt(target[0], target[1], target[2]);
  cam.updateMatrixWorld();
}

export const lerp3 = (a: number[], b: number[], k: number): [number, number, number] => [lerp(a[0]!, b[0]!, k), lerp(a[1]!, b[1]!, k), lerp(a[2]!, b[2]!, k)];

/** Catmull-Rom through points, u in 0..1 over the whole path. */
export function catmull(pts: number[][], u: number): [number, number, number] {
  const n = pts.length - 1;
  const x = clamp(u) * n, i = Math.min(n - 1, Math.floor(x)), f = x - i;
  const p0 = pts[Math.max(0, i - 1)]!, p1 = pts[i]!, p2 = pts[i + 1]!, p3 = pts[Math.min(n, i + 2)]!;
  const out: number[] = [];
  for (let d = 0; d < 3; d++) {
    const a = p0[d]!, b = p1[d]!, c2 = p2[d]!, e = p3[d]!;
    out.push(0.5 * (2 * b + (-a + c2) * f + (2 * a - 5 * b + 4 * c2 - e) * f * f + (-a + 3 * b - 3 * c2 + e) * f * f * f));
  }
  return out as [number, number, number];
}

/** Project a world point to logical screen px (y down). Returns null behind the camera. */
export function toScreen(cam: THREE.PerspectiveCamera, x: number, y: number, z: number, W = 1920, H = 1080) {
  const v = new THREE.Vector3(x, y, z).project(cam);
  if (v.z > 1) return null;
  return { x: (v.x * 0.5 + 0.5) * W, y: (0.5 - v.y * 0.5) * H, z: v.z };
}

/** The six masters, in the order they are summoned: model names (mrwang 2026-10-11), never company names or logos. */
export const MASTERS = ['OPUS 5.5', 'GPT6-Astra', 'DeepSeek v4.1 Flash', 'GLM-5.3-Flash', 'Minimax-M3.1-Flash-Preview', 'UNKNOWN'] as const;

/** Lines for a name that must fit in maxW with the context's current font: one line if it fits, else broken at the
 *  space or hyphen nearest the middle (a hyphen stays at the end of the first line). */
export function nameLines(c: CanvasRenderingContext2D, name: string, maxW: number): string[] {
  if (c.measureText(name).width <= maxW) return [name];
  let best = -1, bd = 1e9;
  for (let i = 1; i < name.length - 1; i++) {
    if (name[i] !== ' ' && name[i] !== '-') continue;
    const d = Math.abs(i - name.length / 2);
    if (d < bd) { bd = d; best = i; }
  }
  if (best < 0) return [name];
  return name[best] === ' ' ? [name.slice(0, best), name.slice(best + 1)] : [name.slice(0, best + 1), name.slice(best + 1)];
}
