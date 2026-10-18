// 0:03.75–0:09.375 `city` — 2031. Rain over a night city; the camera cranes up out of the streets as the clouds part
// and the grail descends, a pillar of light falling into the plaza. Titles: the date, then “圣杯降临。”
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { Layer2D, W, H } from '../engine/gl';
import { LineBatch } from '../engine/lines';
import { clamp, ease, keys, lerp, mulberry32, prog, frameIdx, warp } from '../engine/util';
import { City, cityUniforms } from './_city';
import { makeChalice, makePillar, makeGlow, ringGeometry, runeRingMaterial, runeTexture } from './_grail';
import { aim, catmull, cjk, drawRule, loadCJK, revealText } from './_film';

export default class CityScene extends Scene {
  cam = new THREE.PerspectiveCamera(38, W / H, 1, 9000);
  u = cityUniforms();
  city!: City;
  fx = new THREE.Scene();
  grail = makeChalice();
  pillar = makePillar(7, 1);
  glow = makeGlow(380);
  rings: { mesh: THREE.Mesh; mat: THREE.RawShaderMaterial; speed: number }[] = [];
  rain = new LineBatch(4000, { blend: 'add', screen2D: false });
  text = new Layer2D();
  drops: Float32Array = new Float32Array(0);

  override async init() {
    await loadCJK();
    this.city = new City(this.u);
    this.fx.add(this.grail.mesh, this.glow.mesh);
    // the pillar spans ground -> grail base; rebuilt in scale each frame
    this.fx.add(this.pillar.mesh);
    const tex = runeTexture(3);
    for (const [r0, r1, tilt, speed, rep] of [[78, 92, 0.08, 0.018, 3], [104, 112, -0.12, -0.011, 4], [126, 140, 0.04, 0.007, 5]] as const) {
      const mat = runeRingMaterial(tex, [1.0, 0.72, 0.36]);
      const mesh = new THREE.Mesh(ringGeometry(r0, r1, 256, rep), mat);
      mesh.rotation.x = tilt;
      this.fx.add(mesh);
      this.rings.push({ mesh, mat, speed });
    }
    // rain drops: (x, y, z, speed) in a box around the camera, wrapped deterministically
    const rnd = mulberry32(11);
    const N = 3200;
    this.drops = new Float32Array(N * 4);
    for (let i = 0; i < N; i++) { this.drops[i * 4] = rnd(); this.drops[i * 4 + 1] = rnd(); this.drops[i * 4 + 2] = rnd(); this.drops[i * 4 + 3] = 0.7 + rnd() * 0.6; }
  }

  /** Camera path over the shot (local time 0..6). */
  private camAt(lt: number) {
    const u = ease.inOutCubic(clamp((lt - 0.2) / 5.6));
    const P = [[20, 18, 640], [20, 60, 600], [16, 220, 640], [8, 420, 760], [0, 520, 880]];
    const T = [[14, 120, 300], [12, 260, 120], [6, 420, -60], [0, 470, -150], [0, 430, -170]];
    const p = catmull(P, u), tg = catmull(T, u);
    const roll = lerp(-0.05, 0.0, ease.outCubic(u));
    return { p, tg, roll };
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    // v8: 5.625 s, the pillar strikes the plaza on a beat (scene 2.8125 = film 6.5625)
    const lt = warp(f.lt, [[0, 0], [2.8125, 2.9], [5.625, 6]]), t = f.t;
    const c = this.camAt(lt);
    aim(this.cam, c.p, c.tg, c.roll, 38);

    // the grail descends out of the cloud deck
    const gy = keys(lt, [[0, 1080], [0.6, 1040, ease.linear], [4.6, 560, ease.outCubic]]);
    const gp = new THREE.Vector3(0, gy, -150);
    this.u.grailPos.value.copy(gp);
    this.u.time.value = t;
    const lightOn = prog(lt, 0.4, 2.6, ease.inOutQuad);
    this.u.grailLight.value = 0.15 + 0.85 * lightOn;
    this.u.pillar.value = prog(lt, 2.2, 3.4, ease.outCubic);
    (this.city.sky.u.hole!.value as number) = 0;
    this.city.sky.u.hole!.value = keys(lt, [[0.3, 0], [3.0, 520, ease.outCubic], [6, 640, ease.linear]]);
    this.city.sky.u.lightning!.value = Math.max(0, 1 - Math.abs(lt - 1.1) * 14) + 0.6 * Math.max(0, 1 - Math.abs(lt - 1.28) * 20);

    this.city.render(renderer, out, this.cam);

    // grail + halos + glow + pillar
    this.grail.mesh.position.copy(gp);
    this.grail.mesh.scale.setScalar(1.25);
    this.grail.mesh.rotation.y = t * 0.12;
    const gm = this.grail.mat.uniforms;
    gm.camPos!.value.copy(this.cam.position);
    gm.glow!.value = 0.25 + 0.55 * lightOn;
    gm.time!.value = t;
    this.glow.mesh.position.copy(gp).add(new THREE.Vector3(0, 10, 0));
    this.glow.mat.uniforms.amp!.value = 0.12 + 0.38 * lightOn;
    this.rings.forEach((r, i) => {
      r.mesh.position.copy(gp).add(new THREE.Vector3(0, -6 + i * 8, 0));
      r.mat.uniforms.spin!.value = t * r.speed;
      r.mat.uniforms.reveal!.value = prog(lt, 1.0 + i * 0.35, 2.6 + i * 0.35, ease.inOutCubic);
      r.mat.uniforms.amp!.value = 1.6 * lightOn;
    });
    const ph = Math.max(1, gy - 50);
    this.pillar.mesh.position.set(gp.x, 0, gp.z);
    this.pillar.mesh.scale.set(1, ph, 1);
    const pm = this.pillar.mat.uniforms;
    pm.height!.value = 1;
    pm.camPos!.value.copy(this.cam.position);
    pm.time!.value = t;
    // the pillar falls from the grail to the plaza
    const fall = prog(lt, 2.2, 2.9, ease.inQuad);
    this.pillar.mesh.scale.y = ph * fall;
    this.pillar.mesh.position.y = gy - 50 - ph * fall;
    pm.amp!.value = 1.5 * this.u.pillar.value + 6 * Math.max(0, 1 - Math.abs(lt - 2.9) * 5);
    renderer.setRenderTarget(out);
    renderer.render(this.fx, this.cam);

    // rain: streaks in a box around the camera, falling and slanted, drawn in 3D
    const rb = this.rain; rb.clear();
    const box = 260, D = this.drops, cp = this.cam.position;
    for (let i = 0; i < D.length / 4; i++) {
      const sp = D[i * 4 + 3]!;
      const x = cp.x + (D[i * 4]! - 0.5) * box * 2;
      const z = cp.z + (D[i * 4 + 2]! - 0.5) * box * 2 - 60;
      const yy = (((D[i * 4 + 1]! * box * 2 - t * 260 * sp) % (box * 2)) + box * 2) % (box * 2);
      const y = cp.y - box + yy;
      const len = 7 * sp;
      const dist = Math.hypot(x - cp.x, y - cp.y, z - cp.z);
      const a = 0.08 + 0.32 * Math.exp(-dist / 110);
      rb.seg(x, y, z, x + len * 0.12, y + len, z, 1.1, 0.7 * a, 0.78 * a, 1.0 * a, 1);
    }
    rb.render(renderer, out, this.cam);

    // titles
    const L = this.text; L.clear();
    const x2 = L.ctx;
    const tA = lt - 0.9;
    if (tA > 0) {
      const fadeA = 1 - prog(lt, 5.3, 5.9);
      x2.font = '500 15px "Plex-500"';
      x2.textBaseline = 'alphabetic';
      revealText(x2, 'N 35°41′  E 139°42′', 132, 846, { lt: tA, stagger: 0.012, dur: 0.35, rise: 0, blur: 0, alpha: 0.7 * fadeA, fill: 'rgba(238,233,223,1)', tracking: 2 });
      x2.font = '500 15px "Plex-500"';
      revealText(x2, '2031.10.06  23:59', 132, 870, { lt: tA - 0.25, stagger: 0.015, dur: 0.35, rise: 0, blur: 0, alpha: 0.7 * fadeA, fill: 'rgba(238,233,223,1)', tracking: 2 });
      drawRule(x2, 132, 890, 300, prog(lt, 1.3, 2.2), `rgba(232,176,74,${0.6 * fadeA})`, 'left');
    }
    const tB = lt - 3.15;
    if (tB > 0) {
      const fadeB = 1 - prog(lt, 5.45, 5.95);
      x2.font = cjk('serif', 700, 92);
      revealText(x2, '圣杯降临。', 126, 990, {
        lt: tB, stagger: 0.11, dur: 0.9, rise: 26, blur: 16, alpha: fadeB, tracking: 18,
        fill: (a, y, b) => { const g = x2.createLinearGradient(0, y - 80, 0, y + 6); g.addColorStop(0, '#fff6e2'); g.addColorStop(1, '#e9c27a'); return g; },
        glow: { color: 'rgba(255,190,90,0.35)', blur: 24 },
      });
      x2.font = '500 14px "Plex-500"';
      revealText(x2, 'THE GRAIL DESCENDS', 132, 1022, { lt: tB - 0.6, stagger: 0.02, dur: 0.4, rise: 0, blur: 0, alpha: 0.55 * fadeB, fill: 'rgba(232,176,74,1)', tracking: 6 });
    }
    this.ctx.comp.draw(renderer, L.upload(), out);

    const flash = Math.max(0, 1 - Math.abs(lt - 2.9) * 8) * 0.07;
    return {
      bloom: 0.7, bloomThreshold: 0.9, halation: 0.35, grain: 0.05, vignette: 0.5, ca: 1.4,
      fade: 1 - prog(f.lt, 0, 0.35, ease.outQuad), flash,
      shake: lt > 2.85 && lt < 3.3 ? [Math.sin(frameIdx(t) * 2.1) * 2 * (3.3 - lt), Math.cos(frameIdx(t) * 1.7) * 2 * (3.3 - lt)] : [0, 0],
    };
  }
}
