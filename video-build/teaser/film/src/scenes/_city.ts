// The 2031 city: instanced towers with procedural windows, wet streets, a cloud deck and night sky.
// Shared by `city` (the opening) and `finale` (the return).
import * as THREE from 'three';
import { GLSL_COMMON } from '../engine/glsl/common';
import { FSPass } from '../engine/gl';
import { hash, mulberry32 } from '../engine/util';

const PRE = `precision highp float;\nprecision highp int;\n`;
export const BLOCK = 40;
export const GRAIL_XZ: [number, number] = [0, -150];

/** Uniforms every city material shares (one object, so a scene sets them once per frame). */
export function cityUniforms() {
  return {
    camPos: { value: new THREE.Vector3() },
    grailPos: { value: new THREE.Vector3(0, 560, -150) },
    grailLight: { value: 1 },
    red: { value: 0 },
    time: { value: 0 },
    fogK: { value: 0.0014 },
    pillar: { value: 1 },
  };
}
type U = ReturnType<typeof cityUniforms>;

const FOG = /* glsl */ `
uniform vec3 camPos, grailPos; uniform float grailLight, red, time, fogK, pillar;
vec3 fogColor(vec3 dir) {
  vec3 g = mix(C_GOLD, C_CRIMSON, red);
  float toward = pow(sat(dot(normalize(dir), normalize(grailPos - camPos))), 8.0);
  return C_NIGHT * 1.6 + vec3(0.012, 0.016, 0.03) + g * 0.05 * toward * grailLight;
}
vec3 applyFog(vec3 col, vec3 wpos) {
  vec3 d = wpos - camPos;
  float dist = length(d);
  // height fog: thicker near the ground
  float hf = exp(-max(wpos.y, 0.0) / 260.0);
  float f = 1.0 - exp(-dist * fogK * (0.45 + 1.4 * hf));
  return mix(col, fogColor(d), sat(f));
}
// light the grail casts (and its pillar, a vertical line light down to the plaza)
vec3 grailLit(vec3 p, vec3 n) {
  vec3 g = mix(C_GOLD, C_CRIMSON, red);
  vec3 L = grailPos - p; float d = length(L);
  float lam = max(dot(n, L / d), 0.0);
  vec3 c = g * lam * grailLight * 9.0e4 / (d * d + 4.0e4);
  // pillar: closest point on the vertical segment under the grail
  vec3 q = vec3(grailPos.x, clamp(p.y, 0.0, grailPos.y - 50.0), grailPos.z);
  vec3 Lp = q - p; float dp = length(Lp);
  c += g * max(dot(n, Lp / dp), 0.0) * pillar * 1.4e3 / (dp * dp * 0.06 + 600.0);
  return c;
}`;

export class City {
  towers: THREE.InstancedMesh;
  ground: THREE.Mesh;
  base: number[][] = [];
  centers: [number, number, number, number][] = [];
  ids!: THREE.InstancedBufferAttribute;
  private frustum = new THREE.Frustum();
  private sph = new THREE.Sphere();
  scene = new THREE.Scene();
  sky: FSPass;
  u: U;
  count = 0;

  constructor(u: U, opts: { radius?: number; seed?: number } = {}) {
    this.u = u;
    const R = opts.radius ?? 26;
    const rnd = mulberry32(opts.seed ?? 7);
    const rnd2 = mulberry32((opts.seed ?? 7) * 31 + 5);
    const box = new THREE.BoxGeometry(1, 1, 1);
    box.translate(0, 0.5, 0);
    const mats: THREE.Matrix4[] = [];
    const extra: number[] = [];
    for (let i = -R; i <= R; i++) for (let j = -R; j <= R; j++) {
      const cx = i * BLOCK, cz = j * BLOCK;
      const dPlaza = Math.hypot(cx - GRAIL_XZ[0], cz - GRAIL_XZ[1]);
      if (dPlaza < 120) continue; // the plaza under the grail
      // one to three buildings per block
      const nb = rnd() < 0.35 ? 2 : 1;
      for (let b = 0; b < nb; b++) {
        const w = 12 + rnd() * 16, d = 12 + rnd() * 16;
        const ox = nb === 1 ? 0 : (b === 0 ? -1 : 1) * (BLOCK * 0.22), oz = (rnd() - 0.5) * 6;
        const r = Math.hypot(cx, cz);
        const n = rnd();
        const core = Math.exp(-Math.pow((dPlaza - 380) / 320, 2)); // a ring of towers around the plaza
        let h = 14 + 70 * n * n + 360 * core * Math.pow(rnd(), 1.6) + 120 * Math.exp(-r / 600) * rnd();
        if (rnd() < 0.04 && r < 900) h = 260 + rnd() * 300; // landmark spires
        const m = new THREE.Matrix4().compose(new THREE.Vector3(cx + ox, 0, cz + oz), new THREE.Quaternion(), new THREE.Vector3(w, h, d));
        mats.push(m);
        extra.push(rnd());
        // setbacks and masts on the tall ones (own random stream so the block layout stays put)
        if (h > 130 && rnd2() < 0.65) {
          let y = h, tw = w, td = d;
          const tiers = 1 + (rnd2() < 0.45 ? 1 : 0);
          for (let k = 0; k < tiers; k++) {
            tw *= 0.62 + rnd2() * 0.18; td *= 0.62 + rnd2() * 0.18;
            const th = h * (0.1 + rnd2() * 0.16);
            mats.push(new THREE.Matrix4().compose(new THREE.Vector3(cx + ox + (rnd2() - 0.5) * (w - tw) * 0.6, y, cz + oz + (rnd2() - 0.5) * (d - td) * 0.6), new THREE.Quaternion(), new THREE.Vector3(tw, th, td)));
            extra.push(rnd2());
            y += th;
          }
          if (rnd2() < 0.5) {
            mats.push(new THREE.Matrix4().compose(new THREE.Vector3(cx + ox, y, cz + oz), new THREE.Quaternion(), new THREE.Vector3(1.4, 18 + rnd2() * 40, 1.4)));
            extra.push(rnd2());
          }
        }
      }
    }
    this.count = mats.length;
    const mat = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      uniforms: u as any,
      vertexShader: PRE + /* glsl */ `
        in vec3 position; in vec3 normal; in mat4 instanceMatrix; in float aId;
        uniform mat4 viewMatrix, projectionMatrix;
        out vec3 vW; out vec3 vN; flat out int vId; out vec3 vSize; out vec3 vLocal; out float vBase;
        void main() {
          vBase = instanceMatrix[3].y;
          vec4 w = instanceMatrix * vec4(position, 1.0);
          vW = w.xyz; vN = normalize(mat3(instanceMatrix) * normal); vId = int(aId + 0.5);
          vSize = vec3(length(instanceMatrix[0].xyz), length(instanceMatrix[1].xyz), length(instanceMatrix[2].xyz));
          vLocal = position;
          gl_Position = projectionMatrix * viewMatrix * w;
        }`,
      fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + FOG + /* glsl */ `
        in vec3 vW; in vec3 vN; flat in int vId; in vec3 vSize; in vec3 vLocal; in float vBase;
        void main() {
          vec3 N = normalize(vN);
          float id = float(vId);
          float r1 = hash11(id * 1.37 + 0.5), r2 = hash11(id * 7.11 + 2.0), r3 = hash11(id * 3.3 + 9.0);
          vec3 col;
          if (N.y > 0.5) {
            // roof: dark with a faint gravel texture and the grail's light
            col = C_NIGHT2 * 0.25 + grailLit(vW, N) * 0.04;
            // aircraft warning lights on the tall ones, blinking
            float tall = step(150.0, vBase + vSize.y);
            vec2 rl = vLocal.xz * vSize.xz;
            float dl = length(rl - vec2(0.3, -0.25) * vSize.xz);
            float blink = step(0.55, fract(time * 0.8 + r1));
            col += vec3(1.0, 0.08, 0.04) * tall * blink * 30.0 * (1.0 - smoothstep(0.35, 0.6, dl));
          } else {
            // facade coordinates: along the face and up
            vec2 t2 = abs(N.x) > 0.5 ? vec2(vW.z, vW.y) : vec2(vW.x, vW.y);
            float cw = 2.2 + floor(r2 * 3.0) * 0.5, ch = 3.2 + r3 * 0.6;
            vec2 cell = t2 / vec2(cw, ch);
            vec2 ci = floor(cell), cf = fract(cell);
            float win = step(0.16, cf.x) * step(cf.x, 0.84) * step(0.22, cf.y) * step(cf.y, 0.8);
            float lit = step(hash13(vec3(ci, id + (N.x + 2.0 * N.z) * 31.0)), 0.1 + 0.26 * r1);
            // some floors fully dark, some fully on (offices)
            float floorK = hash12(vec2(ci.y, id));
            lit *= step(0.12, floorK);
            lit = max(lit, step(0.965, floorK) * step(0.3, r2));
            float warmth = hash13(vec3(ci.yx, id * 0.7));
            vec3 wc = warmth < 0.62 ? vec3(1.0, 0.62, 0.32) : warmth < 0.9 ? vec3(0.75, 0.86, 1.0) : vec3(1.0, 0.92, 0.8);
            float inten = 0.35 + 0.9 * hash13(vec3(ci, id + 5.0));
            // glass between windows reflects the sky: fresnel
            vec3 V = normalize(camPos - vW);
            float fres = pow(1.0 - sat(dot(N, V)), 3.0);
            vec3 glass = mix(C_NIGHT2 * 0.12, vec3(0.012, 0.016, 0.03), fres) + mix(C_GOLD, C_CRIMSON, red) * fres * 0.06 * grailLight;
            col = glass;
            float inner = 0.7 + 0.3 * smoothstep(0.2, 0.8, cf.y);
            float blinds = 1.0 - 0.35 * step(0.5, fract(cf.y * 9.0)) * step(0.6, hash13(vec3(ci, id + 2.0)));
            col += win * lit * wc * inten * 0.3 * inner * blinds;
            // floor slabs and fins
            col *= 1.0 - 0.5 * (1.0 - smoothstep(0.0, 0.06, cf.y)) ;
            col += C_STEEL * 0.025 * (1.0 - smoothstep(0.0, 0.05, abs(cf.x - 0.5) - 0.45));
            // mullions
            col *= 0.75 + 0.25 * win;
            // vertical LED trims on some towers, crowns on tall ones
            float top = vSize.y + vBase - vW.y;
            float crown = step(160.0, vSize.y) * (1.0 - smoothstep(0.0, 2.2, top)) * step(0.4, r3);
            col += (r1 < 0.5 ? C_CYAN : C_GOLD2) * crown * 1.6;
            float edgeU = min(cf.x, 1.0 - cf.x);
            col += C_STEEL * 0.12 * (1.0 - smoothstep(0.0, 0.03, abs(fract(t2.x / (vSize.x + vSize.z) * 2.0) - 0.5) - 0.48)) * step(0.85, r2);
            // the grail's light on the facades
            col += grailLit(vW, N) * 0.05 * (0.3 + 0.7 * (1.0 - win * lit));
            // street-level signs: narrow vertical neon strips with glyph gaps (HDR: they bloom)
            float signOn = step(0.5, r2) * step(vW.y, 90.0) * step(6.0, vW.y);
            float colW = 7.0;
            float sci = floor(t2.x / colW);
            float sh = hash12(vec2(sci, id));
            float sx = fract(t2.x / colW);
            float strip = step(0.72, sh) * (1.0 - smoothstep(0.06, 0.09, abs(sx - 0.5)));
            float sy = (vW.y - 10.0 - sh * 20.0);
            float span = step(0.0, sy) * step(sy, 22.0 + 30.0 * hash11(sh * 9.0));
            float glyphs = step(0.3, hash12(vec2(sci, floor(vW.y / 1.6)) + id));
            vec3 sCol = sh < 0.82 ? vec3(1.0, 0.18, 0.5) : sh < 0.92 ? vec3(0.25, 0.85, 1.0) : vec3(1.0, 0.55, 0.15);
            col += sCol * strip * span * signOn * (0.6 + 2.2 * glyphs);
            // the strip's spill on the facade around it
            col += sCol * 0.05 * signOn * step(0.72, sh) * span * exp(-abs(sx - 0.5) * 6.0);
          }
          // ambient occlusion toward the street
          col *= 0.55 + 0.45 * smoothstep(0.0, 40.0, vW.y);
          col = applyFog(col, vW);
          fragColor = vec4(col, 1.0);
        }`,
    });
    this.towers = new THREE.InstancedMesh(box, mat, mats.length);
    mats.forEach((m, i) => this.towers.setMatrixAt(i, m));
    this.towers.instanceMatrix.needsUpdate = true;
    // stable per-building id (the draw order changes every frame: front to back, culled to the frustum)
    this.base = mats.map((m) => m.elements.slice());
    this.centers = mats.map((m) => { const e = m.elements; return [e[12]!, e[13]! + e[5]! / 2, e[14]!, Math.hypot(e[0]!, e[5]!, e[10]!) / 2] as [number, number, number, number]; });
    this.ids = new THREE.InstancedBufferAttribute(new Float32Array(mats.length).map((_, i) => i), 1);
    this.ids.setUsage(THREE.DynamicDrawUsage);
    box.setAttribute('aId', this.ids);
    this.towers.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.towers.frustumCulled = false;
    this.scene.add(this.towers);

    // wet ground with glowing streets and the plaza
    const g = new THREE.PlaneGeometry(8000, 8000);
    g.rotateX(-Math.PI / 2);
    const gm = new THREE.RawShaderMaterial({
      glslVersion: THREE.GLSL3,
      uniforms: u as any,
      vertexShader: PRE + /* glsl */ `
        in vec3 position; uniform mat4 modelMatrix, viewMatrix, projectionMatrix; out vec3 vW;
        void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + FOG + /* glsl */ `
        in vec3 vW;
        void main() {
          vec2 p = vW.xz;
          vec2 b = abs(fract(p / ${BLOCK.toFixed(1)} + 0.5) - 0.5) * ${BLOCK.toFixed(1)};
          float road = smoothstep(12.0, 10.0, min(b.x, b.y) < 0.0 ? 0.0 : 20.0 - max(b.x, b.y));
          // street lamps: sodium points along the roads, and traffic streaks
          float lane = 1.0 - smoothstep(0.0, 0.8, abs(min(b.x, b.y) - 0.0));
          vec2 cell = floor(p / 9.0);
          float lamp = step(0.82, hash12(cell)) * (1.0 - smoothstep(0.6, 1.6, length(fract(p / 9.0) - 0.5) * 9.0));
          vec3 col = C_NIGHT2 * 0.18;
          float onRoad = step(20.0 - 6.0, max(b.x, b.y));
          col += vec3(1.0, 0.55, 0.22) * lamp * onRoad * 0.6;
          // car light streaks (move with time)
          float alongX = step(b.y, 3.0) * step(14.0, b.x);
          float alongZ = step(b.x, 3.0) * step(14.0, b.y);
          float sx = fract(p.x * 0.012 + time * 0.35 + hash11(floor(p.y / ${BLOCK.toFixed(1)}))) ;
          float sz = fract(p.y * 0.012 - time * 0.3 + hash11(floor(p.x / ${BLOCK.toFixed(1)}) + 3.0));
          col += vec3(1.0, 0.3, 0.2) * alongX * smoothstep(0.92, 1.0, sx) * 0.9;
          col += vec3(0.9, 0.95, 1.0) * alongZ * smoothstep(0.93, 1.0, sz) * 0.9;
          // plaza: polished stone with concentric inlay
          float dpl = length(p - grailPos.xz);
          float plaza = 1.0 - smoothstep(110.0, 118.0, dpl);
          col = mix(col, C_NIGHT2 * 0.3, plaza);
          col += mix(C_GOLD, C_CRIMSON, red) * plaza * (1.0 - smoothstep(0.0, 1.2, abs(fract(dpl / 18.0) - 0.5) * 18.0)) * 0.08;
          // wet sheen: the grail and its pillar reflected as a long streak toward the camera
          vec3 V = normalize(camPos - vW);
          vec3 R = reflect(-V, vec3(0.0, 1.0, 0.0));
          vec3 toG = normalize(grailPos - vW);
          float spec = pow(sat(dot(R, toG)), 60.0) * 1.6 + pow(sat(dot(normalize(R.xz), normalize(grailPos.xz - vW.xz))), 400.0) * 0.4 * pillar;
          col += mix(C_GOLD, C_CRIMSON, red) * spec * grailLight * (0.25 + 0.75 * (1.0 - plaza * 0.5));
          col += grailLit(vW, vec3(0.0, 1.0, 0.0)) * 0.12;
          col = applyFog(col, vW);
          fragColor = vec4(col, 1.0);
        }`,
    });
    this.ground = new THREE.Mesh(g, gm);
    this.ground.frustumCulled = false;
    this.ground.renderOrder = 1; // after the towers, so hidden ground fragments are rejected by depth
    this.scene.add(this.ground);

    // sky + cloud deck as a fullscreen pass driven by the camera's inverse view-projection
    this.sky = new FSPass(FOG + /* glsl */ `
      uniform mat4 invVP; uniform float cloudY, hole, lightning;
      vec3 rayDir(vec2 uv) {
        vec4 a = invVP * vec4(uv * 2.0 - 1.0, -1.0, 1.0), b = invVP * vec4(uv * 2.0 - 1.0, 1.0, 1.0);
        return normalize(b.xyz / b.w - a.xyz / a.w);
      }
      void main() {
        vec3 d = rayDir(vUv);
        vec3 g = mix(C_GOLD, C_CRIMSON, red);
        // base gradient: horizon haze to deep night
        float up = sat(d.y);
        vec3 col = mix(C_NIGHT * 2.2 + vec3(0.01, 0.012, 0.02), C_NIGHT * 0.5, pow(up, 0.6));
        // city light pollution near the horizon
        col += vec3(0.05, 0.03, 0.02) * exp(-abs(d.y) * 9.0);
        // cloud deck
        if (d.y > 0.0) {
          float tt = (cloudY - camPos.y) / d.y;
          vec3 p = camPos + d * tt;
          vec2 q = p.xz * 0.0016 + vec2(time * 0.01, time * 0.004);
          float dens = fbm(q, 6) * 0.5 + 0.5;
          dens = smoothstep(0.35, 0.85, dens);
          float dg = length(p.xz - grailPos.xz);
          // the grail parts the clouds: a ragged hole that widens with 'hole'
          float rag = fbm(vec2(atan(p.z - grailPos.z, p.x - grailPos.x) * 2.0, dg * 0.004), 4) * 120.0;
          float holeM = smoothstep(hole - 60.0, hole + 140.0, dg + rag);
          dens *= holeM;
          // underside lit by the grail (gold), rim of the hole hot
          float lit = exp(-dg / 900.0) * grailLight;
          float rim = exp(-abs(dg + rag - hole - 60.0) / 70.0) * step(1.0, hole) * grailLight;
          vec3 cc = C_NIGHT2 * 0.7 + g * (0.35 * lit + 1.4 * rim) + C_STEEL * 0.02;
          cc += vec3(0.6, 0.7, 1.0) * lightning * exp(-length(p.xz - vec2(-900.0, -1600.0)) / 1200.0) * 1.5;
          float fade = exp(-tt * 0.00035);
          col = mix(col, cc, dens * fade);
          // through the hole: deeper sky with a halo
          col += g * 0.25 * exp(-dg / 260.0) * (1.0 - dens) * grailLight * fade;
        }
        fragColor = vec4(col, 1.0);
      }`, { ...(u as any), invVP: { value: new THREE.Matrix4() }, cloudY: { value: 900 }, hole: { value: 0 }, lightning: { value: 0 } });
    // drawn last at the far plane, only where no geometry landed
    this.sky.mat.vertexShader = this.sky.mat.vertexShader.replace('gl_Position = vec4(position.xy, 0.0, 1.0);', 'gl_Position = vec4(position.xy, 0.99999, 1.0);');
    this.sky.mat.depthTest = true; this.sky.mat.depthFunc = THREE.LessEqualDepth; this.sky.mat.depthWrite = false;
  }

  /** Per-frame: camera, sky. Then render sky + city into out. */
  render(renderer: THREE.WebGLRenderer, out: THREE.WebGLRenderTarget, cam: THREE.PerspectiveCamera, extra?: THREE.Object3D[]) {
    this.u.camPos.value.copy(cam.position);
    const vp = new THREE.Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    (this.sky.u.invVP!.value as THREE.Matrix4).copy(vp).invert();
    // towers front to back, frustum-culled
    this.frustum.setFromProjectionMatrix(vp);
    const cp = cam.position;
    const vis: number[] = [], dist: number[] = [];
    for (let i = 0; i < this.centers.length; i++) {
      const c = this.centers[i]!;
      this.sph.center.set(c[0], c[1], c[2]); this.sph.radius = c[3];
      if (!this.frustum.intersectsSphere(this.sph)) continue;
      vis.push(i); dist[i] = (c[0] - cp.x) ** 2 + (c[1] - cp.y) ** 2 + (c[2] - cp.z) ** 2;
    }
    vis.sort((a, b) => dist[a]! - dist[b]!);
    const im = this.towers.instanceMatrix.array as Float32Array, ida = this.ids.array as Float32Array;
    vis.forEach((src, k) => { im.set(this.base[src]!, k * 16); ida[k] = src; });
    this.towers.count = vis.length;
    this.towers.instanceMatrix.needsUpdate = true;
    this.ids.needsUpdate = true;
    renderer.setRenderTarget(out);
    renderer.clearDepth();
    renderer.render(this.scene, cam);
    // the sky last, only where nothing was drawn (it sits at the far plane)
    this.sky.render(renderer, out);
  }
}

export const hashN = (i: number) => hash(i * 7.31 + 0.5);

/** Rain: streaks in a box around the camera, a pure function of t. */
export class Rain {
  drops: Float32Array;
  lb: import('../engine/lines').LineBatch;
  constructor(LB: typeof import('../engine/lines').LineBatch, n = 3200, seed = 11) {
    const rnd = mulberry32(seed);
    this.drops = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { this.drops[i * 4] = rnd(); this.drops[i * 4 + 1] = rnd(); this.drops[i * 4 + 2] = rnd(); this.drops[i * 4 + 3] = 0.7 + rnd() * 0.6; }
    this.lb = new LB(n + 16, { blend: 'add', screen2D: false });
  }
  render(renderer: THREE.WebGLRenderer, out: THREE.WebGLRenderTarget, cam: THREE.PerspectiveCamera, t: number, amt = 1, box = 260, tint: [number, number, number] = [0.7, 0.78, 1.0]) {
    const rb = this.lb; rb.clear();
    const D = this.drops, cp = cam.position;
    const fwd = new THREE.Vector3(); cam.getWorldDirection(fwd);
    for (let i = 0; i < D.length / 4; i++) {
      const sp = D[i * 4 + 3]!;
      const x = cp.x + fwd.x * box * 0.6 + (D[i * 4]! - 0.5) * box * 2;
      const z = cp.z + fwd.z * box * 0.6 + (D[i * 4 + 2]! - 0.5) * box * 2;
      const yy = (((D[i * 4 + 1]! * box * 2 - t * 260 * sp) % (box * 2)) + box * 2) % (box * 2);
      const y = cp.y + fwd.y * box * 0.6 - box + yy;
      const len = 7 * sp;
      const dist = Math.hypot(x - cp.x, y - cp.y, z - cp.z);
      const a = (0.08 + 0.32 * Math.exp(-dist / 110)) * amt;
      rb.seg(x, y, z, x + len * 0.12, y + len, z, 1.1, tint[0] * a, tint[1] * a, tint[2] * a, 1);
    }
    rb.render(renderer, out, cam);
  }
}
