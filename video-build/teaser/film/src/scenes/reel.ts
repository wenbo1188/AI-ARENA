// Footage reels cut one per beat. `open` (0:00–0:03.75): “AI 圣杯战争，谁能夺冠？” from the first frame, over three
// highlights cut on the first hits. `montage` (0:46.875–0:58.125): 22 new shots across the three games, speeding up,
// whiting out into 2031.
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { Layer2D, W, H } from '../engine/gl';
import { ease, frameIdx, prog, pulse } from '../engine/util';
import { cjk, loadCJK, revealText } from './_film';
import { Footage, makeGrade } from './_footage';
import { GRADES, drawShot, prepareShots, shotAt, type Shot } from './_shots';

const BEAT = 0.46875;
const B = (n: number) => n * BEAT;
const lin = ease.linear;

// Hit(): a shot that cuts in on its impact: clip frame `hit` lands `lead` s after the cut at beat b0 (the cut-in slam or the
// hit, one or two frames past it), then rings out to frame `end` by the next cut. Optional zoom from z0 to z1.
function Hit(clip: string, g: number, b0: number, b1: number, hit: number, end: number, lead = 0.04, z0 = 1.0, z1 = 1.0): Shot {
  const t0 = B(b0), t1 = B(b1);
  const s: Shot = { clip, g, t0, t1, frames: [[t0, hit - 3], [t0 + lead, hit, lin], [t1, end, ease.outQuad]] };
  if (z0 !== z1) s.zoom = [[t0, z0], [t1, z1]];
  return s;
}
// v10c football clips: the frame the ball hits the net (the goal flash), and the nitro strike in f10_k4
const F10 = { long: 132, wall: 126, lob: 140, run: 146, goal5: 132, net: 138, k4: 40 };

const REELS: Record<string, Shot[]> = {
  open: [
    { clip: 'o10_fang_open', g: 0, t0: 0, t1: B(2), frames: [[0, 46], [B(2), 100, lin]], zoom: [[0, 1.06], [B(2), 1.0]] },
    { clip: 'cs9b', g: 1, t0: B(2), t1: B(4), frames: [[B(2), 74], [B(2) + 0.08, 80, lin], [B(4), 124, ease.outQuad]], zoom: [[B(2), 1.0], [B(4), 1.06]] },
    { clip: 'f8_net', g: 2, t0: B(4), t1: B(8), frames: [[B(4), 116], [B(4) + 0.08, 121, lin], [B(8), 176, ease.outQuad]], zoom: [[B(4), 1.0], [B(8), 1.06]] },
  ],
  // v10c (mrwang: too much repeated footage, check the beat sync, fewer Octopath and more football): every shot here is
  // new footage that appears nowhere else in the film (Octopath seed 11, three other CodeSide matches, other goals and
  // strikes, the stadium). 23 shots: football 10, CodeSide 7, Octopath 6. 6 bars that speed up: 2-beat cuts, 1-beat,
  // half-beat, 1-beat, then one slowed hero shot whiting out into 2031. Each action shot cuts in ON its impact (a cut-in
  // slamming shut, a hit, an explosion, a strike, the ball hitting the net), so hit and cut land together on the beat.
  montage: [
    // 2-beat cuts: the stadium itself (mrwang: football should include venue shots, moved like cinema) between hits
    { clip: 'f10_fly', g: 2, t0: B(0), t1: B(2), frames: [[B(0), 30], [B(2), 100, lin]] },
    Hit('o11_claw', 0, 2, 4, 8, 60, 0.06, 1.05),
    { clip: 'f10_holo2', g: 2, t0: B(4), t1: B(6), frames: [[B(4), 40], [B(6), 110, lin]] },
    Hit('cs10_dbl2', 1, 6, 8, 73, 108, 0.04, 1.0, 1.05),
    // 1-beat cuts
    Hit('f10_long', 2, 8, 9, F10.long, F10.long + 7, 0.04, 1.05),
    Hit('o11_sud', 0, 9, 10, 6, 40, 0.06),
    Hit('cs10_kill', 1, 10, 11, 60, 80, 0.04, 1.05),
    Hit('f10_goal5', 2, 11, 12, F10.goal5, F10.goal5 + 7, 0.04, 1.05),
    Hit('o11_whirl_in', 0, 12, 13, 17, 46, 0.04, 1.05),
    Hit('cs10_x2', 1, 13, 14, 50, 72),
    { clip: 'f10_dancers', g: 2, t0: B(14), t1: B(15), frames: [[B(14), 40], [B(15), 76, lin]] },
    Hit('cs10_k2', 1, 15, 16, 68, 79, 0.04, 1.05),
    // half-beat cuts
    Hit('f10_wall', 2, 16, 16.5, F10.wall, F10.wall + 3, 0.04),
    Hit('o11_axe_hit', 0, 16.5, 17, 23, 36, 0.04),
    Hit('cs10_top', 1, 17, 17.5, 40, 52, 0.04),
    Hit('f10_run', 2, 17.5, 18, F10.run, F10.run + 3, 0.04),
    Hit('o11_chaos', 0, 18, 18.5, 20, 38, 0.04),
    Hit('cs10_line', 1, 18.5, 19, 67, 78, 0.04),
    Hit('f10_lob', 2, 19, 19.5, F10.lob, F10.lob + 6, 0.04),
    Hit('cs10_wide', 1, 19.5, 20, 72, 84, 0.04),
    // 1-beat, then the hero
    Hit('o11_ice_hit', 0, 20, 21, 8, 44, 0.04, 1.05),
    Hit('f10_k4', 2, 21, 22, F10.k4, F10.k4 + 30),
    // hero: from inside the net the ball flies straight at the camera and fills the frame on the phrase change (2031)
    { clip: 'f10_net2', g: 2, t0: B(22), t1: B(24), frames: [[B(22), 84], [B(24), F10.net, ease.inQuad]], zoom: [[B(22), 1.0], [B(24), 1.1]] },
  ],
};

export default class Reel extends Scene {
  shots: Shot[] = [];
  kind = 'open';
  foot = new Footage(48);
  grade = makeGrade();
  text = new Layer2D();

  override async init() {
    await loadCJK();
    this.kind = (this.ctx.params?.reel as string) ?? 'open';
    this.shots = REELS[this.kind]!;
  }

  override async prepare(t0: number, t1: number) {
    await prepareShots(this.foot, this.shots, t0 - this.ctx.start, t1 - this.ctx.start);
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    const lt = f.lt, t = f.t, dur = f.end - f.start;
    const shot = shotAt(this.shots, lt) ?? this.shots[this.shots.length - 1]!;
    // (the film's very first frame is the thumbnail: no cut punch, flash or shake on it)
    const calm = this.kind === 'open' && shot === this.shots[0];
    // (mrwang) the opening footage starts out of focus and pulls into focus over about a second, so the eye lands on the
    // question first; slightly dimmed while soft
    const soft = this.kind === 'open' ? 1 - ease.inOutCubic(prog(lt, 0.1, 0.9)) : 0;
    const punch = drawShot(renderer, out, this.foot, this.grade, shot, lt, GRADES[shot.g ?? 0]!, { punch: calm ? 0 : 0.9, blur: soft, fade: 1 - 0.3 * soft });
    const L = this.text; L.clear();
    const x2 = L.ctx;
    x2.textBaseline = 'alphabetic';
    let fade = 0, flash = calm ? 0 : 0.18 * pulse(lt - shot.t0, 0, 0.06);
    if (this.kind === 'open') {
      // the question, on screen from the very first frame (it is the hook, and the thumbnail), over all three hits
      const q = lt + 1.0;
      {
        const fo = 1 - prog(lt, dur - 0.2, dur);
        const band = x2.createLinearGradient(0, H / 2 - 260, 0, H / 2 + 260);
        band.addColorStop(0, 'rgba(0,0,0,0)'); band.addColorStop(0.5, `rgba(0,0,0,${0.7 * fo})`); band.addColorStop(1, 'rgba(0,0,0,0)');
        x2.fillStyle = band; x2.fillRect(0, H / 2 - 260, W, 520);
        x2.font = cjk('serif', 900, 96);
        revealText(x2, 'AI 圣杯战争，', W / 2, H / 2 - 10, {
          lt: q, stagger: 0.04, dur: 0.3, rise: 14, blur: 12, align: 'center', alpha: fo, tracking: 12,
          fill: '#f6efe2', glow: { color: 'rgba(0,0,0,0.9)', blur: 24 },
        });
        revealText(x2, '谁能夺冠？', W / 2, H / 2 + 110, {
          lt: q - 0.35, stagger: 0.06, dur: 0.3, rise: 14, blur: 12, align: 'center', alpha: fo, tracking: 18,
          fill: (a, y) => { const g = x2.createLinearGradient(0, y - 86, 0, y + 6); g.addColorStop(0, '#fff2cf'); g.addColorStop(1, '#e2a443'); return g; },
          glow: { color: 'rgba(255,140,40,0.4)', blur: 26 },
        });
      }
      fade = prog(lt, dur - 0.12, dur);
    } else {
      // whiting out into 2031
      flash = Math.max(flash, 0.85 * prog(lt, dur - 0.3, dur, ease.inQuad));
    }
    this.ctx.comp.draw(renderer, L.upload(), out);
    const fi = frameIdx(t);
    const hit = calm ? 0 : pulse(lt - shot.t0, 0, 0.1);
    return {
      bloom: 0.35, bloomThreshold: 1.0, halation: 0.2, grain: 0.05, vignette: 0.4,
      ca: 1.0 + 2.5 * punch, flash, fade,
      shake: hit > 0.05 ? [Math.sin(fi * 2.3) * 7 * hit, Math.cos(fi * 1.7) * 7 * hit] : [0, 0],
    };
  }
}
