// Footage shots shared by the era scenes and the reels: a clip, a window of local time, and a key track from local
// time to clip frame (so speed ramps put the action on the beat), plus the grade each game's footage sits in.
import * as THREE from 'three';
import { keys, pulse, type Key } from '../engine/util';
import { Footage, makeGrade } from './_footage';

export interface Shot {
  clip: string;
  t0: number; t1: number;
  /** local time → clip frame */
  frames: Key[];
  zoom?: Key[];
  /** a short caption naming the action (bottom right) */
  tag?: string;
  /** which game's grade (0 Octopath, 1 CodeSide, 2 CodeBall); defaults to the scene's */
  g?: number;
}

export interface Grade { exposure: number; contrast: number; sat: number; lift: [number, number, number]; gain: [number, number, number]; scan?: number }
export const GRADES: Grade[] = [
  { exposure: 1.04, contrast: 1.06, sat: 1.06, lift: [0.006, 0.004, 0.0], gain: [1.05, 1.0, 0.92] },
  { exposure: 1.02, contrast: 1.08, sat: 1.12, lift: [0.0, 0.004, 0.008], gain: [1.0, 1.0, 1.04], scan: 0.12 },
  { exposure: 1.0, contrast: 1.1, sat: 0.96, lift: [0.0, 0.003, 0.01], gain: [0.95, 1.0, 1.07] },
];

export const shotAt = (shots: Shot[], lt: number) => shots.find((s) => lt >= s.t0 && lt < s.t1) ?? null;
export const frameOf = (s: Shot, lt: number) => Math.round(keys(lt, s.frames));

/** Load the frames a render window will need (call from Scene.prepare). */
export async function prepareShots(foot: Footage, shots: Shot[], lt0: number, lt1: number) {
  const need = new Set<string>();
  for (const lt of [lt0, (lt0 + lt1) / 2, lt1]) {
    const s = shotAt(shots, lt);
    if (s) need.add(`${s.clip}|${frameOf(s, lt)}`);
  }
  await Promise.all([...need].map((k) => { const [c, i] = k.split('|'); return foot.load(c!, +i!); }));
}

/** Draw one shot frame through the grade; a small punch-in and RGB split on the cut. Returns the cut pulse. */
export function drawShot(renderer: THREE.WebGLRenderer, out: THREE.WebGLRenderTarget, foot: Footage, grade: ReturnType<typeof makeGrade>,
  s: Shot, lt: number, G: Grade, opts: { punch?: number; fade?: number; blur?: number } = {}) {
  const tex = foot.get(s.clip, frameOf(s, lt));
  const g = grade.u;
  g.img!.value = tex;
  g.exposure!.value = G.exposure; g.contrast!.value = G.contrast; g.satK!.value = G.sat;
  (g.lift!.value as THREE.Vector3).set(...G.lift); (g.gain!.value as THREE.Vector3).set(...G.gain);
  const k = lt - s.t0;
  const punch = pulse(k, 0, 0.09) * (opts.punch ?? 1);
  g.zoom!.value = (s.zoom ? keys(lt, s.zoom) : 1.0) * (1 + 0.035 * punch);
  g.split!.value = 1.8 * punch;
  g.blurK!.value = opts.blur ?? 0;
  g.fade!.value = opts.fade ?? 1;
  if (tex) grade.render(renderer, out);
  return punch;
}
