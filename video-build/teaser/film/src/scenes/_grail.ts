// The grail and its attendants: the chalice (lathe), rune halos, the light pillar. Shared by city, rift, finale.
import * as THREE from 'three';
import { GLSL_COMMON } from '../engine/glsl/common';
import { SCALE } from '../engine/gl';

const PRE = `precision highp float;\nprecision highp int;\n`;

/** Pure additive blending into the HDR target (colour adds, alpha untouched). */
export const ADD = {
  blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
  blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor,
} as const;

/** Chalice profile (radius, height), base at y = -50, rim at y = 50. Outer wall then inner wall. */
const PROFILE: [number, number][] = [
  [0, -50], [29, -50], [31.5, -48.6], [31, -46.5], [24, -44], [14, -41], [9, -36], [7.2, -28],
  [8.5, -22], [12.5, -17], [13.4, -13.5], [10.5, -9.5], [6.6, -5], [6, 2], [7.2, 8],
  [12, 12.5], [21, 17.5], [29.5, 25], [35, 34], [37.6, 43], [38.4, 49], [38.6, 50.4],
  [37.2, 50.6], [36.4, 47.5], [34, 37], [28.5, 28], [20, 21.5], [10, 19], [0, 18.5],
];

export function makeChalice() {
  const pts = PROFILE.map(([r, y]) => new THREE.Vector2(r, y));
  const geo = new THREE.LatheGeometry(pts, 160);
  geo.computeVertexNormals();
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      glow: { value: 1 }, crack: { value: 0 }, red: { value: 0 }, time: { value: 0 }, fade: { value: 1 },
      camPos: { value: new THREE.Vector3() },
    },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec3 normal;
      uniform mat4 modelMatrix, viewMatrix, projectionMatrix;
      out vec3 vW; out vec3 vN; out vec3 vL;
      void main() {
        vec4 w = modelMatrix * vec4(position, 1.0);
        vW = w.xyz; vL = position;
        vN = normalize(mat3(modelMatrix) * normal);
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec3 vW; in vec3 vN; in vec3 vL;
      uniform float glow, crack, red, time, fade; uniform vec3 camPos;
      // cellular cracks in object space
      float cracks(vec3 p) {
        vec2 q = vec2(atan(p.z, p.x) * 2.8648, p.y * 0.075);
        vec3 n3 = vec3(cos(atan(p.z, p.x)), sin(atan(p.z, p.x)), p.y * 0.04) * 3.0;
        q += 0.2 * vec2(snoise(n3), snoise(n3 + 7.7)); // jagged seams (periodic around the cup)
        vec2 i = floor(q), f = fract(q);
        float d1 = 9.0, d2 = 9.0;
        for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
          vec2 g = vec2(x, y), o = hash22(i + g);
          float d = length(g + o - f);
          if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) d2 = d;
        }
        return d2 - d1;
      }
      void main() {
        vec3 N = normalize(vN), V = normalize(camPos - vW);
        if (dot(N, V) < 0.0) N = -N;
        vec3 R = reflect(-V, N);
        float fres = pow(1.0 - sat(dot(N, V)), 4.0);
        // gold metal reflecting a dark sky with a hot band above (the grail's own halo light)
        float sky = smoothstep(-0.2, 0.9, R.y);
        vec3 gold = mix(C_GOLD, C_CRIMSON, red);
        vec3 col = gold * (0.05 + 0.55 * sky * sky) + gold * 2.2 * pow(sat(R.y), 18.0);
        // anisotropic lathe highlights (vertical streaks)
        float ang = atan(vL.z, vL.x);
        col += gold * 0.4 * pow(0.5 + 0.5 * sin(ang * 3.0 + 1.3 - dot(V.xz, vec2(1.0, 0.0))), 24.0);
        col += mix(C_GOLD2, C_ROSE, red) * fres * 1.6;
        // inner light: the cup is full of light, the stem glows from within
        float cup = smoothstep(14.0, 50.0, vL.y) * step(length(vL.xz), 37.0);
        col += mix(C_GOLD2, C_ROSE, red) * glow * (0.08 * (1.0 - cup) + 1.6 * cup * smoothstep(30.0, 50.0, vL.y)) * (0.5 + 0.5 * fres);
        // cracks: white-hot seams opening as crack goes 0 -> 1
        float c = cracks(vL);
        float seam = (1.0 - smoothstep(0.0, 0.012 + 0.03 * crack, c)) * smoothstep(0.0, 0.25, crack);
        float X = 1.0 - (vL.y + 50.0) / 100.0 * 0.6 - hash12(floor(vec2(ang * 2.8648, vL.y * 0.075))) * 0.4;
        float spread = smoothstep(0.0, 0.15, crack * 1.3 - X);
        col += mix(vec3(6.0, 4.2, 3.0), vec3(4.0, 0.55, 0.3), red) * seam * spread + vec3(3.0, 2.2, 1.6) * pow(seam, 6.0) * spread;
        // light pouring out of the cracks onto the surface around them
        col += mix(C_GOLD, C_CRIMSON, red) * smoothstep(0.12, 0.0, c) * spread * smoothstep(0.0, 0.6, crack) * 0.3;
        fragColor = vec4(col * fade, 1.0);
      }`,
  });
  const mesh = new THREE.Mesh(geo, mat);
  return { mesh, mat };
}

/** A strip texture of runes: code glyphs and tokens in a mono face, for the halos and the summoning circles. */
export function runeTexture(seed = 1, w = 4096, h = 96) {
  const cv = document.createElement('canvas');
  cv.width = w * SCALE; cv.height = h * SCALE;
  const c = cv.getContext('2d')!;
  c.scale(SCALE, SCALE);
  c.clearRect(0, 0, w, h);
  const toks = ['def', 'act', 'return', 'while', 'for', 'if', 'λ', 'Σ', '∂', '∇', '{', '}', '⟨', '⟩', '0x1F', 'submit', 'seal', '01', '10', '≡', '∴', '→', 'yield', 'await', 'grail', 'Ω', 'α', 'θ', '∞', ';', '::', '#', '%', '[', ']'];
  let x = 6, s = seed * 9973;
  const rnd = () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
  c.fillStyle = '#fff';
  c.textBaseline = 'middle';
  while (x < w - 40) {
    const t = toks[Math.floor(rnd() * toks.length)]!;
    const sz = 30 + Math.floor(rnd() * 3) * 6;
    c.font = `${rnd() < 0.5 ? 500 : 400} ${sz}px "Plex-500", "DejaVu Sans Mono", monospace`;
    c.globalAlpha = 0.55 + rnd() * 0.45;
    c.fillText(t, x, h / 2 + 2);
    x += c.measureText(t).width + 18 + rnd() * 26;
    if (rnd() < 0.18) { c.globalAlpha = 0.6; c.fillRect(x, h / 2 - 2, 26, 3); x += 44; }
  }
  // fine rules above and below
  c.globalAlpha = 0.85;
  c.fillRect(0, 6, w, 2); c.fillRect(0, h - 8, w, 2);
  c.globalAlpha = 0.35;
  for (let i = 0; i < w; i += 16) c.fillRect(i, 12, 1, 6);
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = THREE.RepeatWrapping;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.anisotropy = 8;
  tex.colorSpace = THREE.NoColorSpace;
  return tex;
}

/** A flat annulus whose uv.x runs around (0..repeat) and uv.y across (0 inner .. 1 outer). */
export function ringGeometry(r0: number, r1: number, seg = 256, repeat = 1) {
  const pos: number[] = [], uv: number[] = [], idx: number[] = [];
  for (let i = 0; i <= seg; i++) {
    const a = (i / seg) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
    pos.push(c * r0, 0, s * r0, c * r1, 0, s * r1);
    uv.push((i / seg) * repeat, 0, (i / seg) * repeat, 1);
    if (i < seg) { const k = i * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

/** Additive textured rune ring material (gold by default). */
export function runeRingMaterial(tex: THREE.Texture, color: [number, number, number]) {
  return new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { tex: { value: tex }, color: { value: new THREE.Vector3(...color) }, amp: { value: 1 }, spin: { value: 0 }, reveal: { value: 1 } },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec2 vUv; uniform sampler2D tex; uniform vec3 color; uniform float amp, spin, reveal;
      void main() {
        float a = texture(tex, vec2(vUv.x + spin, vUv.y)).r;
        // reveal sweeps around the ring
        float u = fract(vUv.x);
        float rv = smoothstep(reveal - 0.02, reveal, 1.0 - u) ;
        rv = reveal >= 1.0 ? 1.0 : rv;
        fragColor = vec4(color * a * amp * rv, 0.0);
      }`,
    transparent: true, depthWrite: false, side: THREE.DoubleSide,
    blending: THREE.CustomBlending, ...ADD,
  });
}

/** A vertical additive light pillar (open cylinder, brightest where it faces the camera). */
export function makePillar(radius: number, height: number) {
  const geo = new THREE.CylinderGeometry(radius, radius, height, 64, 1, true);
  geo.translate(0, height / 2, 0);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { color: { value: new THREE.Vector3(1, 0.8, 0.45) }, amp: { value: 1 }, time: { value: 0 }, camPos: { value: new THREE.Vector3() }, height: { value: height } },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec3 normal;
      uniform mat4 modelMatrix, viewMatrix, projectionMatrix;
      out vec3 vW; out vec3 vN; out float vY;
      void main() {
        vec4 w = modelMatrix * vec4(position, 1.0);
        vW = w.xyz; vN = normalize(mat3(modelMatrix) * normal); vY = position.y;
        gl_Position = projectionMatrix * viewMatrix * w;
      }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec3 vW; in vec3 vN; in float vY;
      uniform vec3 color, camPos; uniform float amp, time, height;
      void main() {
        vec3 V = normalize(camPos - vW);
        float f = abs(dot(normalize(vN), V));
        float core = pow(f, 6.0) * 1.8 + pow(f, 1.5) * 0.25;
        float h = vY / height;
        float streak = 0.75 + 0.25 * snoise(vec2(atan(vN.z, vN.x) * 3.0, vY * 0.01 - time * 1.4));
        float ends = smoothstep(0.0, 0.03, h) * smoothstep(1.0, 0.85, h);
        fragColor = vec4(color * core * streak * ends * amp, 0.0);
      }`,
    transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.CustomBlending, ...ADD,
  });
  return { mesh: new THREE.Mesh(geo, mat), mat };
}

/** A camera-facing additive glow sprite (soft disc), for bloom sources the bloom alone can't make big enough. */
export function makeGlow(size: number) {
  const geo = new THREE.PlaneGeometry(size, size);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { color: { value: new THREE.Vector3(1, 0.75, 0.4) }, amp: { value: 1 }, falloff: { value: 2.2 } },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vUv;
      void main() {
        vUv = uv;
        // billboard: keep the centre, offset in view space
        vec4 c = modelViewMatrix * vec4(0.0, 0.0, 0.0, 1.0);
        c.xy += position.xy;
        gl_Position = projectionMatrix * c;
      }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + /* glsl */ `
      in vec2 vUv; uniform vec3 color; uniform float amp, falloff;
      void main() {
        float d = length(vUv - 0.5) * 2.0;
        float g = pow(max(0.0, 1.0 - d), falloff);
        fragColor = vec4(color * g * amp, 0.0);
      }`,
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.CustomBlending, ...ADD,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  return { mesh, mat };
}
