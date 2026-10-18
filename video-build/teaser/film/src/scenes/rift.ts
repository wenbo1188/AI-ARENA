// 0:18.75–0:26.25 `rift` — the servants. Three servants from three eras materialise on the plaza (a swordsman from
// the medieval era, a 1987 pixel rocket trooper, a 2087 football robot): servants from three times in one place.
// They clash at the foot of the pillar; the shock runs up into the grail, which cracks; the frame shatters
// like glass into a time vortex, and the title lands: “AI 圣杯战争”.
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { FSPass, Layer2D, W, H, makeRT } from '../engine/gl';
import { LineBatch } from '../engine/lines';
import { clamp, ease, frameIdx, keys, lerp, mulberry32, prog, pulse, warp } from '../engine/util';
import { City, Rain, cityUniforms, GRAIL_XZ } from './_city';
import { makeChalice, makePillar, makeGlow, runeTexture } from './_grail';
import { makeCircle } from './_circle';
import { circlePos, CIRCLE_R, SEATS, UNKNOWN } from './masters';
import { aim, catmull, cjk, loadCJK, revealText, toScreen, drawRule } from './_film';
import { loadPixelTex, makeSpriteCard } from './_sprite';
import { buildRobot } from './_robot';
import { makeSeal } from './_seal';
import { makeVortex } from './_vortex';
import { makeHolo } from './_holo';

const [GX, GZ] = GRAIL_XZ;
// servant marks on the plaza
const HIKARI: [number, number] = [GX - 40, GZ + 14];
const TROOPER: [number, number] = [GX + 34, GZ + 2];
const ROBOT: [number, number] = [GX - 14, GZ - 40];
const APPEAR = [0.25, 0.8, 1.35];
/** Game screens behind the figures: width, distance behind (along the view), height of the centre. */
const HOLO_W = [36, 36, 46], HOLO_D = 14, HOLO_Y = [31, 31, 50];
/** Shot boundaries (local time). */
const S2 = 2.35, S3 = 3.95, S4 = 5.0, S5 = 6.15;
/** Action time: slow motion around the impact. */
const SLOW0 = 2.95, SLOW1 = 3.75, SLOW_K = 0.4;
const actT = (lt: number) => (lt < SLOW0 ? lt : lt < SLOW1 ? SLOW0 + (lt - SLOW0) * SLOW_K : SLOW0 + (SLOW1 - SLOW0) * SLOW_K + (lt - SLOW1));
const IMPACT = 3.22; // in action time

export default class Rift extends Scene {
  cam = new THREE.PerspectiveCamera(40, W / H, 0.5, 9000);
  u = cityUniforms();
  city!: City;
  fx = new THREE.Scene();
  sprites = new THREE.Scene();
  grail = makeChalice();
  pillar = makePillar(7, 1);
  glow = makeGlow(380);
  circles: ReturnType<typeof makeCircle>[] = [];
  marks: ReturnType<typeof makeCircle>[] = [];
  beams: ReturnType<typeof makePillar>[] = [];
  hikari!: ReturnType<typeof makeSpriteCard>;
  trooper!: ReturnType<typeof makeSpriteCard>;
  trooperFire!: ReturnType<typeof makeSpriteCard>;
  rocket!: ReturnType<typeof makeSpriteCard>;
  boom!: ReturnType<typeof makeSpriteCard>;
  slash!: ReturnType<typeof makeSpriteCard>;
  robot = buildRobot();
  holos: Awaited<ReturnType<typeof makeHolo>>[] = [];
  lights: THREE.PointLight[] = [];
  rain = new Rain(LineBatch);
  lines = new LineBatch(4000, { blend: 'add', screen2D: false });
  text = new Layer2D();
  sceneRT = makeRT();
  vortex!: FSPass;
  shards!: THREE.Mesh;
  shardScene = new THREE.Scene();
  shardCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  cracks = new LineBatch(3000, { blend: 'add', screen2D: true });
  crackPaths: { pts: [number, number][]; d0: number }[] = [];
  seal = makeSeal(1.0);
  sealScene = new THREE.Scene();
  sealCam = new THREE.OrthographicCamera(-W / H, W / H, 1, -1, -1, 1);

  override async init() {
    await loadCJK();
    await document.fonts.load('600 40px "Cormorant-600"', '1987');
    this.city = new City(this.u);
    this.u.grailPos.value.set(GX, 560, GZ);
    this.u.grailLight.value = 0.8;
    this.u.pillar.value = 1;
    this.city.sky.u.hole!.value = 640;
    const runes = runeTexture(9, 2048, 96);
    for (let i = 0; i < SEATS; i++) {
      const c = makeCircle(CIRCLE_R, runes);
      const [x, z] = circlePos(i);
      c.mesh.position.set(x, 0.4, z);
      c.mat.uniforms.seed!.value = i * 0.19;
      c.mat.uniforms.draw!.value = 1;
      c.mat.uniforms.power!.value = 1;
      this.fx.add(c.mesh);
      this.circles.push(c);
    }
    for (const [x, z] of [HIKARI, TROOPER, ROBOT]) {
      const c = makeCircle(13, runes);
      c.mesh.position.set(x, 0.5, z);
      (c.mat.uniforms.color!.value as THREE.Vector3).set(1.0, 0.14, 0.1);
      (c.mat.uniforms.hot!.value as THREE.Vector3).set(1.0, 0.7, 0.55);
      c.mat.uniforms.points!.value = 3;
      this.fx.add(c.mesh);
      this.marks.push(c);
      const b = makePillar(2.6, 1);
      b.mesh.position.set(x, 0, z);
      this.fx.add(b.mesh);
      this.beams.push(b);
    }
    this.fx.add(this.grail.mesh, this.glow.mesh, this.pillar.mesh);

    // servants
    const hk = await loadPixelTex('assets/hikari.png');
    // frame 384×288 px, figure ≈190 px tall → 26 units; pivot (192, 264)
    const k = 26 / 190;
    this.hikari = makeSpriteCard(hk, 384 * k, 288 * k, [0.5, 24 / 288], 4, 2);
    this.hikari.mesh.position.set(HIKARI[0], 0, HIKARI[1]);
    // CodeSide kit v1.2 "Shinjuku 1987" operative with the kit's launcher (tools/make_cs_trooper.py): card 128×82 px,
    // body 72 px tall, feet at x 58 px (mirrored by flip, so the pivot is 70/128), 1.4 px above the bottom
    const cs = await loadPixelTex('assets/cs_trooper.png');
    const csf = await loadPixelTex('assets/cs_trooper_fire.png');
    const kc = 28 / 72; // operative 72 px → 28 units
    this.trooper = makeSpriteCard(cs, 128 * kc, 82 * kc, [70 / 128, 1.4 / 82]);
    this.trooperFire = makeSpriteCard(csf, 128 * kc, 82 * kc, [70 / 128, 1.4 / 82]);
    for (const s of [this.trooper, this.trooperFire]) { s.mesh.position.set(TROOPER[0], 0, TROOPER[1]); s.mat.uniforms.flip!.value = 1; }
    const rk = await loadPixelTex('assets/cs_rocket2.png');
    this.rocket = makeSpriteCard(rk, 18 * kc, 8 * kc, [0.5, 0.5]);
    this.rocket.mat.uniforms.flip!.value = 1;
    const bm = await loadPixelTex('assets/cs_explosion.png');
    this.boom = makeSpriteCard(bm, 64 * kc * 1.4, 64 * kc * 1.4, [0.5, 0.5]);
    const sl = await loadPixelTex('assets/fx_sword.png');
    this.slash = makeSpriteCard(sl, 44, 44, [0.5, 0.5], 4, 3);
    for (const s of [this.hikari, this.trooper, this.trooperFire, this.rocket, this.boom, this.slash]) this.sprites.add(s.mesh);
    // each figure stands for a game: a screen of that game's real arena switches on behind it
    const HOLO: [string, [number, number, number]][] = [['assets/holo_octo.jpg', [1.0, 0.72, 0.32]], ['assets/holo_cs.jpg', [0.35, 0.9, 1.0]], ['assets/holo_foot.jpg', [1.0, 0.36, 0.3]]];
    for (const [url, tint] of HOLO) { const k = this.holos.length, h = await makeHolo(url, HOLO_W[k]!, HOLO_W[k]! * 9 / 16, tint); this.sprites.add(h.mesh); this.holos.push(h); }
    this.robot.root.scale.setScalar(14);
    this.robot.root.position.set(ROBOT[0], 0, ROBOT[1]);
    this.sprites.add(this.robot.root);
    // lights for the robot (the cards carry their own lighting)
    this.sprites.add(new THREE.HemisphereLight(0x8090c0, 0x200808, 0.5));
    const key = new THREE.DirectionalLight(0xffd9a0, 1.6); key.position.set(GX, 400, GZ - 50); this.sprites.add(key); key.target.position.set(ROBOT[0], 0, ROBOT[1]); this.sprites.add(key.target);
    for (const [c, x, y, z, i] of [[0xff2a1a, ROBOT[0] + 30, 12, ROBOT[1] + 30, 3000], [0xffb050, GX, 30, GZ, 5000], [0x60d0ff, ROBOT[0] - 30, 40, ROBOT[1] - 20, 1500]] as const) {
      const l = new THREE.PointLight(c, i, 0, 2); l.position.set(x, y, z); this.sprites.add(l); this.lights.push(l);
    }

    // the time vortex behind the shattered frame
    this.vortex = makeVortex();

    // glass shards: a jittered grid of triangles in NDC, each knowing its centroid
    const NX = 11, NY = 6, rnd = mulberry32(17);
    const P: [number, number][][] = [];
    for (let j = 0; j <= NY; j++) { P.push([]); for (let i = 0; i <= NX; i++) {
      const ex = i === 0 || i === NX, ey = j === 0 || j === NY;
      P[j]!.push([-1 + (2 * i) / NX + (ex ? 0 : (rnd() - 0.5) * 1.7 / NX), -1 + (2 * j) / NY + (ey ? 0 : (rnd() - 0.5) * 1.7 / NY)]);
    } }
    const pos: number[] = [], cen: number[] = [], rn: number[] = [], bary: number[] = [];
    const tri = (a: [number, number], b: [number, number], c: [number, number]) => {
      const cx = (a[0] + b[0] + c[0]) / 3, cy = (a[1] + b[1] + c[1]) / 3, r1 = rnd(), r2 = rnd(), r3 = rnd();
      for (const [v, bb] of [[a, [1, 0, 0]], [b, [0, 1, 0]], [c, [0, 0, 1]]] as const) { pos.push(v[0], v[1], 0); cen.push(cx, cy); rn.push(r1, r2, r3); bary.push(...bb); }
    };
    for (let j = 0; j < NY; j++) for (let i = 0; i < NX; i++) {
      const a = P[j]![i]!, b = P[j]![i + 1]!, c = P[j + 1]![i]!, d = P[j + 1]![i + 1]!;
      if (rnd() < 0.5) { tri(a, b, d); tri(a, d, c); } else { tri(a, b, c); tri(b, d, c); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('cen', new THREE.Float32BufferAttribute(cen, 2));
    g.setAttribute('rnd', new THREE.Float32BufferAttribute(rn, 3));
    g.setAttribute('bary', new THREE.Float32BufferAttribute(bary, 3));
    const sm = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      uniforms: { img: { value: this.sceneRT.texture }, k: { value: 0 }, crack: { value: 0 }, origin: { value: new THREE.Vector2(0, 0.3) }, aspect: { value: W / H } },
      vertexShader: `precision highp float;\nin vec3 position; in vec2 cen; in vec3 rnd; in vec3 bary;
        uniform float k, aspect; uniform vec2 origin;
        out vec2 vUv0; out vec3 vB; out float vT; out float vD;
        void main() {
          vUv0 = position.xy * 0.5 + 0.5; vB = bary;
          vec2 d = cen - origin; d.x *= aspect;
          float t = clamp(k * 1.7 - length(d) * 0.35 - rnd.x * 0.25, 0.0, 1.0);
          vT = t; vD = length(d);
          float tt = t * t;
          vec2 local = position.xy - cen; local.x *= aspect;
          float ang = (rnd.y - 0.5) * 7.0 * tt;
          local = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * local;
          float z = min(tt * 1.6, 0.92);
          float s = 1.0 / (1.0 - z);
          vec2 dir = normalize(d + 1e-4);
          vec2 p = cen; p.x *= aspect;
          p = (p + dir * tt * (0.5 + rnd.z) + local) * s;
          p.y -= tt * 0.35;
          p.x /= aspect;
          gl_Position = vec4(p, 0.0, 1.0);
        }`,
      fragmentShader: `precision highp float;\nin vec2 vUv0; in vec3 vB; in float vT; in float vD; out vec4 fragColor;
        uniform sampler2D img; uniform float crack;
        void main() {
          vec3 c = texture(img, vUv0).rgb;
          float e = min(vB.x, min(vB.y, vB.z));
          float edge = 1.0 - smoothstep(0.0, 0.035, e);
          float rim = 1.0 - smoothstep(0.0, 0.012, e);
          c += vec3(2.4, 0.9, 0.6) * rim * smoothstep(0.0, 0.15, vT) * 2.0;
          c *= 1.0 + vT * 0.6;
          float a = 1.0 - smoothstep(0.55, 0.95, vT);
          fragColor = vec4(c * a, a);
        }`,
      depthTest: false, depthWrite: false, transparent: true,
      blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
    });
    this.shards = new THREE.Mesh(g, sm);
    this.shards.frustumCulled = false;
    this.shardScene.add(this.shards);
    this.sealScene.add(this.seal.mesh);
    // glass crack paths (unit space, origin at 0,0): radial jagged lines with branches, plus a few rings
    const cr = mulberry32(5);
    for (let i = 0; i < 11; i++) {
      const a0 = (i / 11) * Math.PI * 2 + (cr() - 0.5) * 0.4;
      let x = 0, y = 0, a = a0, d = 0;
      const pts: [number, number][] = [[0, 0]];
      while (d < 1400) { const st = 40 + cr() * 70; a += (cr() - 0.5) * 0.5; x += Math.cos(a) * st; y += Math.sin(a) * st; d += st; pts.push([x, y]); }
      this.crackPaths.push({ pts, d0: 0 });
      // a branch
      const bi = 2 + Math.floor(cr() * 4);
      const [bx, by] = pts[bi]!;
      const bp: [number, number][] = [[bx, by]];
      let ba = a0 + (cr() < 0.5 ? 0.6 : -0.6), xx = bx, yy = by;
      for (let k = 0; k < 4; k++) { ba += (cr() - 0.5) * 0.6; xx += Math.cos(ba) * 60; yy += Math.sin(ba) * 60; bp.push([xx, yy]); }
      this.crackPaths.push({ pts: bp, d0: Math.hypot(bx, by) });
    }
    for (const R of [70, 160, 300]) {
      for (let i = 0; i < 16; i++) {
        if (cr() < 0.35) continue;
        const a0 = (i / 16) * Math.PI * 2, a1 = ((i + 1) / 16) * Math.PI * 2;
        const r0 = R * (0.85 + cr() * 0.3), r1 = R * (0.85 + cr() * 0.3);
        this.crackPaths.push({ pts: [[Math.cos(a0) * r0, Math.sin(a0) * r0], [Math.cos(a1) * r1, Math.sin(a1) * r1]], d0: R });
      }
    }
  }

  /** Camera per shot. */
  private camAt(lt: number) {
    if (lt < S2) {
      const u = ease.inOutQuad(prog(lt, 0, S2));
      return { p: [lerp(-36, -14, u), lerp(8, 11, u), GZ + lerp(122, 104, u)] as [number, number, number], tg: [GX + lerp(-4, 0, u), 19, GZ] as [number, number, number], roll: 0.02, fov: 42 };
    }
    if (lt < S3) {
      const u = ease.outCubic(prog(lt, S2, SLOW0 + 0.2));
      const v = prog(lt, SLOW0, S3);
      return { p: [lerp(-14, 4, u) + v * 4, lerp(11, 7, u), GZ + lerp(100, 78, u) - v * 8] as [number, number, number], tg: [GX + lerp(0, 5, u), lerp(19, 15, u) + v * 6, GZ] as [number, number, number], roll: lerp(0.02, -0.07, u), fov: lerp(42, 50, u) };
    }
    const u = ease.inOutCubic(prog(lt, S3, S4 + 0.6));
    return { p: [GX + lerp(130, 90, u), lerp(455, 520, u), GZ + lerp(280, 205, u)] as [number, number, number], tg: [GX, lerp(545, 560, u), GZ] as [number, number, number], roll: lerp(0.06, 0.1, u), fov: lerp(42, 38, u) };
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    // v8 re-cut (7.5 s): the impact on the bar (film 22.5), the shatter on the last beat before the silent break
    // (film 23.4375), the title on the drop (film 24.375)
    const lt = warp(f.lt, [[0, 0], [3.75, 3.625], [4.6875, S4], [5.625, S5], [7.5, 8.0]]), t = f.t;
    const at = actT(lt);
    const c = this.camAt(lt);
    aim(this.cam, c.p, c.tg, c.roll, c.fov);
    const impactK = pulse(at, IMPACT, 0.12);
    const afterImpact = at >= IMPACT;
    const crack = prog(lt, S3 + 0.12, S3 + 0.9, ease.inOutCubic);
    this.u.time.value = at;
    this.u.red.value = Math.max(prog(at, IMPACT - 0.05, IMPACT + 0.3), 0.3);
    this.u.grailLight.value = (lt < S3 ? 0.8 : 0.45) + 2.5 * impactK + crack * 0.4;
    this.city.sky.u.lightning!.value = (lt > S3 ? pulse(lt, S3 + 0.15, 0.08) + 0.6 * pulse(lt, S3 + 0.5, 0.06) : 0);

    const showShards = lt >= S4;
    const target = showShards ? this.sceneRT : out;
    this.city.render(renderer, target, this.cam);

    // grail, pillar, glow
    const gp = this.u.grailPos.value;
    this.grail.mesh.position.copy(gp);
    this.grail.mesh.scale.setScalar(1.25);
    this.grail.mesh.rotation.y = at * 0.12;
    const gm = this.grail.mat.uniforms;
    gm.camPos!.value.copy(this.cam.position); gm.glow!.value = lt < S3 ? 0.8 : 0.3 + crack * 0.4; gm.time!.value = t;
    gm.crack!.value = crack; gm.red!.value = Math.max(0.5 * crack, 0.25 * prog(at, IMPACT, IMPACT + 0.4));
    this.glow.mesh.position.copy(gp);
    this.glow.mat.uniforms.amp!.value = lt < S3 ? 0.45 : 0.18 + crack * 0.25;
    this.pillar.mesh.position.set(gp.x, 0, gp.z);
    this.pillar.mesh.scale.set(1 + 2 * impactK, gp.y - 60, 1);
    const pm = this.pillar.mat.uniforms;
    pm.camPos!.value.copy(this.cam.position); pm.time!.value = t; pm.amp!.value = (lt < S3 ? 0.35 : 0.7) + 4 * impactK + 1.0 * pulse(lt, S3, 0.3);

    // circles burn crimson once the war is declared
    for (let i = 0; i < SEATS; i++) {
      const cm = this.circles[i]!.mat.uniforms;
      const cr = 0.5 + 0.5 * prog(at, 0, 0.6);
      (cm.color!.value as THREE.Vector3).set(lerp(1.0, 1.0, cr), lerp(0.7, 0.13, cr), lerp(0.32, 0.1, cr));
      cm.power!.value = 1 + 0.6 * impactK;
      if (i === UNKNOWN) { (cm.color!.value as THREE.Vector3).set(0.42, 0.48, 0.85); cm.power!.value = 0.5 + 0.08 * Math.sin(t * 2.6) + 0.6 * impactK; }
      cm.spin!.value = at * 0.03 * (i % 2 ? -1 : 1);
      cm.time!.value = at;
    }
    const lb = this.lines; lb.clear();
    // servant marks and summoning columns
    [HIKARI, TROOPER, ROBOT].forEach(([x, z], i) => {
      const t0 = APPEAR[i]!;
      const m = this.marks[i]!.mat.uniforms;
      m.draw!.value = prog(at, t0 - 0.3, t0, ease.inOutCubic);
      m.power!.value = prog(at, t0, t0 + 0.5, ease.outCubic);
      m.spin!.value = at * 0.06;
      m.time!.value = at;
      const b = this.beams[i]!;
      const flare = pulse(at, t0, 0.22);
      b.mesh.scale.set(1 + 2 * flare, 400 * prog(at, t0 - 0.05, t0 + 0.15, ease.outExpo), 1);
      b.mat.uniforms.camPos!.value.copy(this.cam.position);
      b.mat.uniforms.time!.value = t;
      b.mat.uniforms.amp!.value = (0.06 + 2.5 * flare) * (1 - prog(at, IMPACT, IMPACT + 0.3));
    });
    renderer.setRenderTarget(target);
    renderer.render(this.fx, this.cam);

    // --- servants ---
    const face = (o: THREE.Object3D) => { o.quaternion.copy(this.cam.quaternion); };
    const tint = (s: ReturnType<typeof makeSpriteCard>, flash = 0) => {
      (s.mat.uniforms.key!.value as THREE.Vector3).set(0.95, 0.82, 0.8).multiplyScalar(1 + 1.5 * impactK);
      (s.mat.uniforms.rim!.value as THREE.Vector3).set(1.6, 0.35, 0.25);
      s.mat.uniforms.flash!.value = flash;
    };
    // the game screens: switch on just after each figure lands, switch off as the shot cuts to the clash
    {
      const fwd = new THREE.Vector3(); this.cam.getWorldDirection(fwd); fwd.y = 0; fwd.normalize();
      [HIKARI, TROOPER, ROBOT].forEach(([x, z], i) => {
        const h = this.holos[i]!;
        const on = Math.min(prog(at, APPEAR[i]! + 0.1, APPEAR[i]! + 0.7), 1 - prog(lt, S2 - 0.4, S2 - 0.05));
        h.mesh.visible = on > 0 && lt < S2;
        h.mesh.position.set(x + fwd.x * HOLO_D, HOLO_Y[i]!, z + fwd.z * HOLO_D);
        h.mesh.quaternion.copy(this.cam.quaternion);
        h.mat.uniforms.on!.value = on; h.mat.uniforms.time!.value = t + i * 1.7;
      });
    }
    // Hikari: idle → wind-up → dash and strike at the pillar
    const h = this.hikari;
    face(h.mesh);
    h.mat.uniforms.appear!.value = prog(at, APPEAR[0]!, APPEAR[0]! + 0.55);
    const hDash = prog(at, 2.85, 3.15, ease.inQuad);
    h.mesh.position.set(lerp(HIKARI[0], GX - 10, hDash), 0 + Math.sin(hDash * Math.PI) * 4, lerp(HIKARI[1], GZ + 6, hDash));
    h.mat.uniforms.frame!.value = at < 2.45 ? 0 : at < 2.85 ? 1 : at < 3.4 ? 2 : 3;
    tint(h, pulse(at, APPEAR[0]!, 0.15));
    // trooper: fires a rocket
    const firing = at > 2.6 && at < 2.75;
    this.trooper.mesh.visible = !firing; this.trooperFire.mesh.visible = firing;
    for (const s of [this.trooper, this.trooperFire]) {
      face(s.mesh);
      s.mat.uniforms.appear!.value = prog(at, APPEAR[1]!, APPEAR[1]! + 0.5);
      tint(s, pulse(at, APPEAR[1]!, 0.15));
      s.mesh.position.set(TROOPER[0] + (firing ? 1.2 : 0) + pulse(at, 2.6, 0.1) * 2, 0, TROOPER[1]);
    }
    const rk = prog(at, 2.62, IMPACT, ease.inQuad);
    this.rocket.mesh.visible = at > 2.62 && at < IMPACT;
    face(this.rocket.mesh);
    const rx = lerp(TROOPER[0] - 10.8, GX + 4, rk), ry = lerp(17.5, 10.5, rk) + Math.sin(rk * Math.PI) * 2, rz = lerp(TROOPER[1], GZ + 8, rk);
    this.rocket.mesh.position.set(rx, ry, rz);
    tint(this.rocket); this.rocket.mat.uniforms.appear!.value = 1;
    if (this.rocket.mesh.visible) for (let k = 0; k < 40; k++) {
      const q = rk - k * 0.012; if (q < 0) break;
      const sx = lerp(TROOPER[0] - 10.8, GX + 4, q), sz = lerp(TROOPER[1], GZ + 8, q), sy = lerp(17.5, 10.5, q) + Math.sin(q * Math.PI) * 2;
      const a = (1 - k / 40) * 0.5;
      lb.seg(sx, sy, sz, sx + 0.8, sy + 0.3, sz, 2.5 + k * 0.08, 1.2 * a, 0.6 * a, 0.3 * a, 1);
    }
    // explosion where the rocket meets the clash
    const bk = prog(at, IMPACT, IMPACT + 0.5);
    this.boom.mesh.visible = bk > 0 && bk < 1;
    face(this.boom.mesh);
    this.boom.mesh.position.set(GX + 2, 12, GZ + 9);
    this.boom.mesh.scale.setScalar(0.28 + ease.outCubic(bk) * 0.5);
    tint(this.boom, 0.2 * (1 - bk)); this.boom.mat.uniforms.appear!.value = 1; this.boom.mat.uniforms.opacity!.value = 0.85 * Math.pow(1 - bk, 1.5);
    // the sword arc
    const sk = prog(at, 3.0, 3.5);
    this.slash.mesh.visible = sk > 0 && sk < 1;
    face(this.slash.mesh);
    this.slash.mesh.position.set(GX - 4, 14, GZ + 10);
    this.slash.mat.uniforms.frame!.value = Math.min(10, Math.floor(sk * 11));
    (this.slash.mat.uniforms.key!.value as THREE.Vector3).set(2.6, 2.4, 2.2);
    this.slash.mat.uniforms.appear!.value = 1;
    // robot: stands, then a nitro dash into the clash
    const r = this.robot;
    const rd = prog(at, 2.8, IMPACT, ease.inQuad);
    r.root.position.set(lerp(ROBOT[0], GX + 5, rd), Math.sin(rd * Math.PI) * 3, lerp(ROBOT[1], GZ - 8, rd));
    r.root.lookAt(GX, 0, GZ + 40 * (1 - rd));
    r.root.rotation.x += rd * 0.35;
    r.flame.visible = at > 2.8 && at < IMPACT + 0.2;
    r.flame.scale.setScalar(1 + 0.25 * Math.sin(at * 60));
    const rap = prog(at, APPEAR[2]!, APPEAR[2]! + 0.5);
    r.root.visible = rap > 0;
    r.root.scale.setScalar(14 * (0.92 + 0.08 * rap));
    for (const m of r.mats) (m.emissive as THREE.Color).setRGB(3.5 * (1 - rap) + 2 * impactK, 0.6 * (1 - rap) + 0.4 * impactK, 0.4 * (1 - rap) + 0.3 * impactK);
    // arms up for the dash
    r.arms.forEach((a, i) => { a.rotation.x = -1.2 * rd; a.rotation.z = (i ? 1 : -1) * (0.22 + 0.4 * rd); });
    this.lights[0]!.intensity = 3000 * (1 + 3 * impactK);
    renderer.setRenderTarget(target);
    renderer.render(this.sprites, this.cam);

    // impact: shockwave ring on the ground + a bolt up the pillar
    if (at > IMPACT - 0.02) {
      const w = at - IMPACT;
      const R = 4 + w * 160;
      const a = Math.exp(-w * 3.5);
      for (let k = 0; k < 160; k++) {
        const a0 = (k / 160) * Math.PI * 2, a1 = ((k + 1) / 160) * Math.PI * 2;
        lb.seg(GX + Math.cos(a0) * R, 0.8, GZ + Math.sin(a0) * R, GX + Math.cos(a1) * R, 0.8, GZ + Math.sin(a1) * R, 2.5, 3 * a, 0.7 * a, 0.5 * a, 1);
      }
      const up = clamp(w / 0.6);
      const y0 = up * (gp.y - 60);
      for (let k = 0; k < 24; k++) {
        const y = y0 - k * 4; if (y < 0) break;
        const jx = Math.sin(k * 7.1 + at * 40) * 2.5, jz = Math.cos(k * 5.3 + at * 33) * 2.5;
        lb.seg(GX + jx, y, GZ + jz, GX - jx, y + 4, GZ - jz, 3.0, 3.5, 0.9, 0.7, 1 - k / 24);
      }
    }
    // gold shards bursting off the grail as it cracks
    if (lt > S3) {
      const w = lt - S3 - 0.12;
      if (w > 0) for (let k = 0; k < 140; k++) {
        const th = k * 2.39996, ph = Math.acos(1 - 2 * ((k * 0.618) % 1));
        const sp = 30 + (k % 7) * 12;
        const d = sp * w;
        const x = gp.x + Math.sin(ph) * Math.cos(th) * d, y = gp.y + 10 + Math.cos(ph) * d - 20 * w * w, z = gp.z + Math.sin(ph) * Math.sin(th) * d;
        const a = Math.exp(-w * 1.5) * 0.9;
        lb.seg(x, y, z, x + Math.cos(th) * 2, y + 1.2, z + Math.sin(th) * 2, 1.8, 2.8 * a, 1.6 * a, 0.6 * a, 1);
      }
    }
    lb.render(renderer, target, this.cam);
    // rain: slows with the action, hangs frozen once the grail cracks
    const rainT = lt < S3 ? at : actT(S3);
    this.rain.render(renderer, target, this.cam, rainT, 0.8);

    // labels under the figures during the summon: era and game (they stand for the three games, not servants)
    const L = this.text; L.clear();
    const x2 = L.ctx;
    x2.textBaseline = 'alphabetic';
    if (lt < S2) {
      const items: [string, string, [number, number], number][] = [['中世纪', '八方旅人', HIKARI, 0], ['1987', '枪战对决', TROOPER, 1], ['2087', '机器人足球', ROBOT, 2]];
      const fo = 1 - prog(lt, S2 - 0.3, S2);
      for (const [era, who, [x, z], i] of items) {
        const k = at - APPEAR[i]! - 0.2;
        if (k <= 0) continue;
        const p = toScreen(this.cam, x, -2, z);
        if (!p) continue;
        x2.font = /^\d/.test(era) ? '600 44px "Cormorant-600"' : cjk('serif', 700, 34);
        revealText(x2, era, p.x, p.y + 52, { lt: k, stagger: 0.05, dur: 0.45, rise: 10, blur: 8, align: 'center', alpha: fo, fill: '#fff0dc', tracking: 8, glow: { color: 'rgba(0,0,0,0.9)', blur: 14 } });
        x2.font = cjk('sans', 700, 24);
        revealText(x2, `GAME  ·  ${who}`, p.x, p.y + 82, { lt: k - 0.15, stagger: 0.03, dur: 0.3, rise: 0, blur: 0, align: 'center', alpha: 0.95 * fo, fill: 'rgba(255,190,150,1)', tracking: 4, glow: { color: 'rgba(0,0,0,0.9)', blur: 10 } });
      }
    }
    if (lt > 1.0 && lt < S2 + 0.6) {
      const fo = 1 - prog(lt, S2 + 0.3, S2 + 0.6);
      x2.font = cjk('serif', 600, 50);
      revealText(x2, '三场比赛，跨越三个时代。', 126, 140, { lt: lt - 1.0, stagger: 0.05, dur: 0.5, rise: 12, blur: 10, alpha: fo, fill: '#f3ead6', tracking: 10, glow: { color: 'rgba(0,0,0,0.9)', blur: 18 } });
    }
    // the war opens on the clash, and the grail breaks at once (mrwang's timeline: open, crack, the arenas thrown back)
    if (lt > 2.7 && lt < S4 + 0.3) {
      const fo = 1 - prog(lt, S4, S4 + 0.3);
      x2.font = cjk('serif', 600, 50);
      const w = revealText(x2, '圣杯战争开启，', 126, 990, { lt: lt - 2.7, stagger: 0.05, dur: 0.5, rise: 12, blur: 10, alpha: fo, fill: '#f3ead6', tracking: 10, glow: { color: 'rgba(0,0,0,0.9)', blur: 18 } });
      if (lt > S3 + 0.1) revealText(x2, '圣杯随即碎裂。', 126 + w + 10, 990, { lt: lt - S3 - 0.1, stagger: 0.05, dur: 0.4, rise: 12, blur: 10, alpha: fo, fill: '#ffd7a8', tracking: 10, glow: { color: 'rgba(255,90,40,0.6)', blur: 22 } });
    }

    if (showShards) {
      // vortex behind, then the glass shards of the last frame flying at us
      this.vortex.u.time!.value = lt;
      this.vortex.u.k!.value = prog(lt, S4, S4 + 0.5);
      this.vortex.u.title!.value = prog(lt, S5, S5 + 0.4);
      this.vortex.render(renderer, out);
      const sm = this.shards.material as THREE.RawShaderMaterial;
      sm.uniforms.k!.value = prog(lt, S4 + 0.18, S4 + 1.05, ease.inQuad);
      sm.uniforms.crack!.value = prog(lt, S4 - 0.02, S4 + 0.3) * (1 - prog(lt, S4 + 0.6, S4 + 1.0));
      const gs = toScreen(this.cam, gp.x, gp.y, gp.z);
      if (gs) (sm.uniforms.origin!.value as THREE.Vector2).set(gs.x / W * 2 - 1, 1 - gs.y / H * 2);
      renderer.setRenderTarget(out);
      renderer.render(this.shardScene, this.shardCam);
      // the cracks race out from the grail just before the glass breaks
      const grow = prog(lt, S4 - 0.12, S4 + 0.18, ease.outCubic) * 1500;
      const ca = 1 - prog(lt, S4 + 0.15, S4 + 0.45);
      if (ca > 0 && gs) {
        const cb = this.cracks; cb.clear();
        for (const cp of this.crackPaths) {
          let d = cp.d0;
          for (let i = 1; i < cp.pts.length; i++) {
            const [ax, ay] = cp.pts[i - 1]!, [bx, by] = cp.pts[i]!;
            const L = Math.hypot(bx - ax, by - ay);
            if (d > grow) break;
            const f = Math.min(1, (grow - d) / L);
            const w = Math.max(0.6, 1.8 - d / 500);
            cb.seg2(gs.x + ax, gs.y + ay, gs.x + ax + (bx - ax) * f, gs.y + ay + (by - ay) * f, w, [2.2 * ca, 1.9 * ca, 1.8 * ca]);
            cb.seg2(gs.x + ax, gs.y + ay, gs.x + ax + (bx - ax) * f, gs.y + ay + (by - ay) * f, w * 5, [0.35 * ca, 0.06 * ca, 0.05 * ca]);
            d += L;
          }
        }
        cb.render(renderer, out);
      }
      // years rushing past in the tunnel
      const yrs = ['中世纪', '1987', '2087', '2031', '中世纪', '1987', '2087', 'XII', '1987', '2087', '中世纪', '∞'];
      const vk = prog(lt, S4 + 0.3, S4 + 0.8) * (1 - prog(lt, S5 + 0.1, S5 + 0.5) * 0.7);
      for (let i = 0; i < yrs.length; i++) {
        const ph = ((lt - S4) * 0.55 + i / yrs.length) % 1;
        const z = lerp(6, 0.35, ph * ph);
        const ang = i * 2.4 + 0.3;
        const rr = 300 / z;
        const x = W / 2 + Math.cos(ang) * rr, y = H / 2 + Math.sin(ang) * rr * 0.8;
        const sz = Math.min(220, 60 / z);
        const a = vk * clamp(ph * 4) * (1 - clamp((ph - 0.8) * 5));
        if (a <= 0) continue;
        const s = yrs[i]!;
        x2.font = /^[\dXI∞]/.test(s) ? `600 ${sz.toFixed(1)}px "Cormorant-600"` : cjk('serif', 700, sz * 0.8);
        x2.globalAlpha = a;
        x2.fillStyle = i % 3 === 0 ? '#ffd890' : i % 3 === 1 ? '#a8f4ff' : '#ff9a8a';
        x2.textAlign = 'center';
        x2.shadowColor = x2.fillStyle; x2.shadowBlur = 20;
        x2.fillText(s, x, y);
        x2.shadowBlur = 0; x2.globalAlpha = 1; x2.textAlign = 'left';
      }
    }
    // title
    if (lt > S5) {
      const k = lt - S5;
      // the seal, faint, behind the title
      const su = this.seal.mat.uniforms;
      (su.reveal!.value as THREE.Vector3).set(1, 1, 1);
      (su.hot3!.value as THREE.Vector3).set(0, 0, 0);
      su.amp!.value = 0.32 * prog(k, 0.0, 0.4) * (1 + 1.5 * pulse(k, 0, 0.2));
      su.time!.value = t;
      this.seal.mesh.scale.setScalar(1.55 + k * 0.05);
      this.seal.mesh.position.set(0, 0.02, 0);
      renderer.setRenderTarget(out);
      renderer.render(this.sealScene, this.sealCam);
      const e = ease.outExpo(clamp(k / 0.35));
      x2.save();
      x2.translate(W / 2, H / 2 + 40);
      const s = lerp(1.35, 1.0, e) + k * 0.012;
      x2.scale(s, s);
      x2.font = cjk('serif', 900, 176);
      revealText(x2, 'AI 圣杯战争', 0, 0, {
        lt: k, stagger: 0.0, dur: 0.3, rise: 0, blur: 22, align: 'center', tracking: 30,
        fill: (a, y) => { const g = x2.createLinearGradient(0, y - 150, 0, y + 10); g.addColorStop(0, '#fff7e6'); g.addColorStop(0.55, '#f2cf86'); g.addColorStop(1, '#c98a2c'); return g; },
        glow: { color: 'rgba(255,90,50,0.55)', blur: 40 },
      });
      x2.restore();
      drawRule(x2, W / 2, H / 2 + 92, 760, prog(k, 0.3, 0.9), 'rgba(232,176,74,0.7)');
      x2.font = cjk('serif', 600, 30);
      revealText(x2, '三个时代  ·  六位御主  ·  一只圣杯', W / 2, H / 2 + 150, { lt: k - 0.5, stagger: 0.03, dur: 0.5, rise: 8, blur: 8, align: 'center', fill: '#efe3cc', tracking: 8 });
    }
    this.ctx.comp.draw(renderer, L.upload(), out);

    const fi = frameIdx(t);
    const shake = Math.max(impactK, pulse(lt, S3 + 0.15, 0.1) * 0.6, pulse(lt, S4 + 0.1, 0.12) * 0.8, lt > S5 ? pulse(lt, S5, 0.12) : 0);
    return {
      bloom: 0.85, bloomThreshold: 0.85, halation: 0.45, grain: 0.055, vignette: 0.55,
      ca: 1.3 + 4 * impactK + (showShards ? 2 * (1 - prog(lt, S4 + 0.8, S5)) : 0),
      flash: impactK * 0.3 + pulse(lt, S3, 0.06) * 0.2 + pulse(lt, S4 + 0.05, 0.08) * 0.15 + (lt > S5 ? pulse(lt, S5, 0.1) * 0.2 : 0),
      shake: shake > 0.02 ? [Math.sin(fi * 2.1) * 9 * shake, Math.cos(fi * 1.7) * 9 * shake] : [0, 0],
      zoom: 1 + impactK * 0.02,
    };
  }
}
