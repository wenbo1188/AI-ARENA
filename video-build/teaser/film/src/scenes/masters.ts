// 0:09.375–0:15 `masters` — at the foot of the pillar, five summoning circles ignite on five beats, each raising a
// column of light and a servant of light in it: the five masters. A beat late the sixth circle half-lights, cold and
// broken, and a figure of shadow stands in it: UNKNOWN. “圣杯选中了六位御主。” / “没有一位是人类。”
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { Layer2D, W, H } from '../engine/gl';
import { LineBatch } from '../engine/lines';
import { clamp, ease, keys, lerp, prog, pulse } from '../engine/util';
import { City, Rain, cityUniforms, GRAIL_XZ } from './_city';
import { makeChalice, makePillar, makeGlow, runeTexture } from './_grail';
import { makeCircle } from './_circle';
import { aim, catmull, cjk, revealText, toScreen, loadCJK, MASTERS, drawRule, nameLines } from './_film';
import { SERVANT_FILES, loadServantTex, makeServant, faceY, isShadow } from './_servant';

const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI'];
/** Seats around the pillar; the last one is UNKNOWN. */
export const SEATS = 6;
export const UNKNOWN = 5;
/** On the beats (0.46875 s); the sixth comes two beats after the fifth. */
export const IGNITE = [0, 0.46875, 0.9375, 1.40625, 1.875, 2.8125];
export const PLAZA_R = 74;
export const CIRCLE_R = 21;
/** Servant card height in world units (the figure itself is about 0.85 of it). */
export const SERVANT_H = 44;
/** Seat angles (degrees) on the hexagon: the first faces the camera's approach; UNKNOWN takes the far seat just
 *  left of the pillar as the plaza is seen at the end, a shadow against the light. */
const SEAT_DEG = [90, 150, 270, 330, 30, 210];
/** Circle centres around the pillar. */
export const circlePos = (i: number): [number, number] => {
  const a = (SEAT_DEG[i]! * Math.PI) / 180;
  return [GRAIL_XZ[0] + Math.cos(a) * PLAZA_R, GRAIL_XZ[1] + Math.sin(a) * PLAZA_R];
};

export default class Masters extends Scene {
  cam = new THREE.PerspectiveCamera(40, W / H, 1, 9000);
  u = cityUniforms();
  city!: City;
  fx = new THREE.Scene();
  grail = makeChalice();
  pillar = makePillar(7, 1);
  glow = makeGlow(380);
  circles: ReturnType<typeof makeCircle>[] = [];
  beams: ReturnType<typeof makePillar>[] = [];
  servants: ReturnType<typeof makeServant>[] = [];
  rain = new Rain(LineBatch);
  sparks = new LineBatch(3000, { blend: 'add', screen2D: false });
  text = new Layer2D();

  override async init() {
    await loadCJK();
    this.city = new City(this.u);
    this.u.grailPos.value.set(GRAIL_XZ[0], 560, GRAIL_XZ[1]);
    this.u.grailLight.value = 1;
    this.u.pillar.value = 1;
    this.city.sky.u.hole!.value = 640;
    const runes = runeTexture(5, 2048, 96);
    for (let i = 0; i < SEATS; i++) {
      const c = makeCircle(CIRCLE_R, runes);
      const [x, z] = circlePos(i);
      c.mesh.position.set(x, 0.4, z);
      c.mat.uniforms.seed!.value = i * 0.19;
      if (i === UNKNOWN) styleUnknown(c.mat.uniforms);
      this.fx.add(c.mesh);
      this.circles.push(c);
      const b = makePillar(3.2, 1);
      if (i === UNKNOWN) (b.mat.uniforms.color!.value as THREE.Vector3).set(0.45, 0.5, 0.8);
      b.mesh.position.set(x, 0, z);
      this.fx.add(b.mesh);
      this.beams.push(b);
    }
    const texs = await Promise.all(SERVANT_FILES.map(loadServantTex));
    for (let i = 0; i < SEATS; i++) {
      const sv = makeServant(texs[i]!, SERVANT_H);
      const [x, z] = circlePos(i);
      sv.mesh.position.set(x, 0.6, z);
      sv.mat.uniforms.seed!.value = i * 0.37;
      if (isShadow(SERVANT_FILES[i]!)) { sv.mat.uniforms.shadow!.value = 1; (sv.mat.uniforms.tint!.value as THREE.Vector3).set(1, 1, 1); }
      this.fx.add(sv.mesh);
      this.servants.push(sv);
    }
    this.fx.add(this.grail.mesh, this.glow.mesh, this.pillar.mesh);
  }

  private camAt(lt: number) {
    // high above the plaza (the pentagon in the canyon of towers) → down among the columns, looking up
    const u = ease.inOutCubic(prog(lt, 2.0, 5.625));
    const gx = GRAIL_XZ[0], gz = GRAIL_XZ[1];
    const E: [number[], number[], number] = [[gx + 96, 40, gz + 88], [gx - 6, 22, gz], 56]; // low across the plaza: the servants in their circles
    const P = [[gx + 30, 560, gz + 150], [gx + 40, 330, gz + 130], [gx + 58, 110, gz + 98], E[0]];
    const T = [[gx, 0, gz - 10], [gx, 0, gz], [gx - 4, 20, gz - 10], E[1]];
    const p = catmull(P, u), tg = catmull(T, u);
    p[1] -= lt * 6 * (1 - u); // a slow push in while the circles ignite
    return { p, tg, roll: lerp(0.02, -0.02, u), fov: lerp(36, E[2], u) };
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    const lt = f.lt, t = f.t;
    const c = this.camAt(lt);
    aim(this.cam, c.p, c.tg, c.roll, c.fov);
    this.u.time.value = t;
    // the city dims a touch as the circles take over
    this.u.grailLight.value = 1 - 0.25 * prog(lt, 0.5, 3.5);
    this.city.render(renderer, out, this.cam);

    const gp = this.u.grailPos.value;
    this.grail.mesh.position.copy(gp);
    this.grail.mesh.scale.setScalar(1.25);
    this.grail.mesh.rotation.y = t * 0.12;
    const gm = this.grail.mat.uniforms;
    gm.camPos!.value.copy(this.cam.position); gm.glow!.value = 0.8; gm.time!.value = t;
    this.glow.mesh.position.copy(gp);
    this.glow.mat.uniforms.amp!.value = 0.5;
    this.pillar.mesh.position.set(gp.x, 0, gp.z);
    this.pillar.mesh.scale.set(1, gp.y - 60, 1);
    this.pillar.mat.uniforms.camPos!.value.copy(this.cam.position);
    this.pillar.mat.uniforms.time!.value = t;
    this.pillar.mat.uniforms.amp!.value = lerp(1.3, 0.4, prog(lt, 3.4, 5.1));

    const sb = this.sparks; sb.clear();
    for (let i = 0; i < SEATS; i++) {
      const t0 = IGNITE[i]!;
      const unk = i === UNKNOWN;
      const cm = this.circles[i]!.mat.uniforms;
      cm.draw!.value = prog(lt, t0 - 0.3, t0 + 0.05, ease.inOutCubic);
      cm.power!.value = prog(lt, t0, t0 + 0.9, ease.outCubic);
      // the sixth: the sweep stalls two-thirds round and the cold light breathes slowly
      const stut = unk ? 0.82 + 0.18 * Math.sin(t * 2.6 + 1.1) : 1;
      if (unk) { cm.draw!.value = prog(lt, t0 - 0.25, t0 + 0.1, ease.outCubic); cm.power!.value *= 0.55 * stut; }
      cm.spin!.value = lt * 0.03 * (i % 2 ? -1 : 1);
      cm.time!.value = t;
      const b = this.beams[i]!;
      const [x, z] = circlePos(i);
      const rise = prog(lt, t0 + 0.02, t0 + 0.5, ease.outExpo);
      b.mesh.scale.set((1 + 2.5 * pulse(lt, t0, 0.12)) * (1 - 0.5 * prog(lt, t0 + 0.6, t0 + 1.4)), 700 * rise, 1);
      b.mat.uniforms.camPos!.value.copy(this.cam.position);
      b.mat.uniforms.time!.value = t + i;
      const low = prog(lt, 3.4, 5.1);
      // once the servant has taken shape the column thins: the figure is the light now
      const held = prog(lt, t0 + 0.6, t0 + 1.4);
      b.mat.uniforms.amp!.value = (lerp(1.2, 0.55, low) * (1 - 0.8 * held) + 5 * pulse(lt, t0, 0.15)) * clamp(rise * 3) * (unk ? 0.3 * stut : 1);
      // the servant takes shape in the column
      const sv = this.servants[i]!;
      faceY(sv.mesh, this.cam);
      const su = sv.mat.uniforms;
      su.appear!.value = prog(lt, t0 + 0.15, t0 + 1.05, ease.inOutQuad);
      su.amp!.value = unk ? 1 : 1.15 + 1.5 * pulse(lt, t0 + 0.2, 0.25);
      su.time!.value = t;
      // embers rising in the column
      if (rise > 0 && !unk) for (let k = 0; k < 60; k++) {
        const h = ((k * 37.3 + (lt - t0) * (30 + (k % 7) * 9)) % 160);
        const ang = k * 2.4 + lt * 0.8;
        const rr = 2 + (k % 5) * 1.6;
        const px = x + Math.cos(ang) * rr, pz = z + Math.sin(ang) * rr;
        const a = 0.6 * (1 - h / 160) * clamp(rise * 2);
        sb.seg(px, h, pz, px, h + 1.6, pz, 1.4, 2.4 * a, 1.5 * a, 0.6 * a, 1);
      }
    }
    renderer.setRenderTarget(out);
    renderer.render(this.fx, this.cam);
    sb.render(renderer, out, this.cam);
    this.rain.render(renderer, out, this.cam, t, 0.8);

    // names above the circles, then the two title lines
    const L = this.text; L.clear();
    const x2 = L.ctx;
    for (let i = 0; i < SEATS; i++) {
      const t0 = IGNITE[i]!;
      const k = lt - t0 - 0.1;
      if (k <= 0) continue;
      const [x, z] = circlePos(i);
      // above the circle as seen: its centre on screen, lifted by its projected radius
      const c0 = toScreen(this.cam, x, 0, z);
      if (!c0) continue;
      let r = 0;
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
        const e = toScreen(this.cam, x + dx * CIRCLE_R, 0, z + dz * CIRCLE_R);
        if (e) r = Math.max(r, Math.abs(e.y - c0.y), Math.abs(e.x - c0.x) * 0.35);
      }
      const s = { x: c0.x, y: c0.y - Math.min(r, 260) - 34 };
      const name = MASTERS[i]!;
      const unk = i === UNKNOWN;
      // (UNKNOWN, lit last, keeps its name a moment longer)
      const fadeOut = unk ? 1 - prog(lt, 3.5, 3.9) : 1 - prog(lt, 3.2, 3.6);
      const latin = /^[A-Za-z]/.test(name);
      x2.font = latin ? '700 34px "Archivo-1000-700"' : cjk('sans', 700, 32);
      // long model names go on two lines so neighbouring labels never touch
      const lines = nameLines(x2, name, 300);
      lines.forEach((ln, j) => revealText(x2, ln, s.x, s.y - 8 - (lines.length - 1 - j) * 38, { lt: k - j * 0.08, stagger: unk ? 0.06 : 0.02, dur: 0.4, rise: 10, blur: 8, align: 'center', alpha: fadeOut * (unk ? 0.85 : 1), fill: unk ? '#c9d2ff' : '#fff4dc', tracking: unk ? 6 : 1, glow: { color: 'rgba(20,10,4,0.85)', blur: 14 } }));
      x2.font = '500 13px "Plex-500"';
      revealText(x2, unk ? 'MASTER · VI · 身份不明' : `MASTER · ${ROMAN[i]}`, s.x, s.y + 16, { lt: k - 0.15, stagger: 0.02, dur: 0.3, rise: 0, blur: 0, align: 'center', alpha: 0.75 * fadeOut, fill: unk ? 'rgba(150,165,230,1)' : 'rgba(232,176,74,1)', tracking: 4 });
    }
    // a soft dark band under the titles so they sit off the light
    const band = prog(lt, 3.4, 4.0) * (1 - prog(lt, 5.3, 5.6));
    if (band > 0) {
      // (the titles sit at the top: down low the servants' light would run through them)
      const g = x2.createLinearGradient(0, 0, 0, 420);
      g.addColorStop(0, `rgba(3,4,10,${0.8 * band})`); g.addColorStop(1, 'rgba(3,4,10,0)');
      x2.fillStyle = g; x2.fillRect(0, 0, W, 420);
    }
    const tA = lt - 3.5, tB = lt - 3.85;
    if (tA > 0) {
      const fo = 1 - prog(lt, 5.35, 5.6);
      x2.font = cjk('serif', 600, 44);
      revealText(x2, '圣杯选中了六位御主。', W / 2, 140, { lt: tA, align: 'center', stagger: 0.05, dur: 0.6, rise: 14, blur: 10, alpha: fo, fill: '#f3ead6', tracking: 10, glow: { color: 'rgba(0,0,0,0.8)', blur: 20 } });
      drawRule(x2, W / 2, 176, 360, prog(lt, 3.8, 4.3), `rgba(232,176,74,${0.6 * fo})`);
    }
    if (tB > 0) {
      const fo = 1 - prog(lt, 5.35, 5.6);
      x2.font = cjk('serif', 900, 84);
      revealText(x2, '没有一位是人类。', W / 2, 276, {
        lt: tB, align: 'center', stagger: 0.04, dur: 0.45, rise: 20, blur: 14, alpha: fo, tracking: 14,
        fill: (a, y) => { const g = x2.createLinearGradient(0, y - 76, 0, y + 6); g.addColorStop(0, '#fff2cf'); g.addColorStop(1, '#e2a443'); return g; },
        glow: { color: 'rgba(255,150,40,0.45)', blur: 26 },
      });
    }
    this.ctx.comp.draw(renderer, L.upload(), out);

    const hit = IGNITE.slice(0, UNKNOWN).reduce((m, t0) => Math.max(m, pulse(lt, t0, 0.09)), 0);
    const glitch = pulse(lt, IGNITE[UNKNOWN]! + 0.1, 0.12);
    return { bloom: 0.8, bloomThreshold: 0.85, halation: 0.4, grain: 0.05, vignette: 0.55, ca: 1.4 + 5 * glitch, flash: hit * 0.05, zoom: 1 + hit * 0.006 };
  }
}

/** The sixth circle: cold, dim. */
function styleUnknown(u: Record<string, THREE.IUniform>) {
  (u.color!.value as THREE.Vector3).set(0.42, 0.48, 0.85);
  (u.hot!.value as THREE.Vector3).set(0.75, 0.82, 1.0);
}
