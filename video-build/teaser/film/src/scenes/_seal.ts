// The command seal: three strokes, one per era, each in its own channel of one mask texture so it can burn in
// (seals) and burn away (era intros) on its own. Stroke 0 = 中世纪 (a crescent blade), 1 = 1987 (a stepped pixel
// bolt), 2 = 2087 (a lance through a ring).
import * as THREE from 'three';
import { GLSL_COMMON } from '../engine/glsl/common';
import { ADD } from './_grail';

const PRE = `precision highp float;\nprecision highp int;\n`;
const S = 1024;

export function sealTexture() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = S;
  const c = cv.getContext('2d')!;
  c.fillStyle = '#000';
  c.fillRect(0, 0, S, S);
  c.globalCompositeOperation = 'lighter';
  const cx = S / 2, cy = S / 2;

  // 0: crescent blade sweeping round the left, tapering to points at both ends
  c.fillStyle = '#f00';
  c.beginPath();
  const a0 = Math.PI * 0.42, a1 = Math.PI * 1.62;
  const N = 90;
  for (let i = 0; i <= N; i++) {
    const u = i / N, a = a0 + (a1 - a0) * u;
    const w = Math.sin(Math.PI * u) ** 0.8 * 58;
    const r = 372 + 14 * Math.sin(Math.PI * u);
    c.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
    void w;
  }
  for (let i = N; i >= 0; i--) {
    const u = i / N, a = a0 + (a1 - a0) * u;
    const w = Math.sin(Math.PI * u) ** 0.8 * 58;
    const r = 372 + 14 * Math.sin(Math.PI * u) - w;
    c.lineTo(cx + Math.cos(a + 0.05 * Math.sin(Math.PI * u)) * r, cy + Math.sin(a + 0.05 * Math.sin(Math.PI * u)) * r);
  }
  c.closePath();
  c.fill();
  // 1: stepped pixel bolt down the right side (square steps, like a 1987 sprite)
  c.fillStyle = '#0f0';
  const px = 30;
  const steps: [number, number][] = [[3, -12], [4, -11], [5, -10], [6, -9], [7, -8], [8, -7], [9, -6], [10, -5], [10, -4], [11, -3], [11, -2], [11, -1], [11, 0], [11, 1], [10, 2], [10, 3], [9, 4], [8, 5], [7, 6], [6, 7], [6, 8], [5, 9], [4, 10]];
  for (const [i, j] of steps) c.fillRect(cx + i * px, cy + j * px, px, px);
  // the inner edge, offset one cell, thinner, broken
  for (let k = 0; k < steps.length; k += 1) {
    if (k % 4 === 3) continue;
    const [i, j] = steps[k]!;
    c.fillRect(cx + (i - 1.6) * px, cy + j * px + px * 0.3, px * 0.55, px * 0.55);
  }
  // pixel spark at the head
  c.fillRect(cx + 1.6 * px, cy - 13 * px, px, px);
  c.fillRect(cx + 0.4 * px, cy - 14.4 * px, px * 0.7, px * 0.7);

  // 2: a lance down the centre through a ring
  c.fillStyle = '#00f';
  c.beginPath();
  c.moveTo(cx, cy - 430);
  c.lineTo(cx + 22, cy - 120);
  c.lineTo(cx + 9, cy + 330);
  c.lineTo(cx, cy + 440);
  c.lineTo(cx - 9, cy + 330);
  c.lineTo(cx - 22, cy - 120);
  c.closePath();
  c.fill();
  c.lineWidth = 16;
  c.strokeStyle = '#00f';
  c.beginPath(); c.arc(cx, cy - 40, 96, 0, Math.PI * 2); c.stroke();
  c.lineWidth = 5;
  c.beginPath(); c.arc(cx, cy - 40, 128, -0.3, Math.PI + 0.3, true); c.stroke();
  // cross-guard
  c.fillRect(cx - 120, cy + 150, 240, 10);

  const tex = new THREE.CanvasTexture(cv);
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.colorSpace = THREE.NoColorSpace;
  tex.anisotropy = 8;
  return tex;
}

/** Each stroke has `reveal` (burn in 0→1) and `burn` (burn away 0→1). Glow from the mask's mips. */
export function makeSeal(size: number, tex = sealTexture()) {
  const geo = new THREE.PlaneGeometry(size, size);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      mask: { value: tex }, reveal: { value: new THREE.Vector3() }, burn: { value: new THREE.Vector3() },
      amp: { value: 1 }, time: { value: 0 }, hot3: { value: new THREE.Vector3() },
    },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec2 vUv;
      uniform sampler2D mask; uniform vec3 reveal, burn, hot3; uniform float amp, time;
      void main() {
        vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
        vec3 m = texture(mask, uv).rgb;
        vec3 g1 = textureLod(mask, uv, 3.0).rgb, g2 = textureLod(mask, uv, 5.5).rgb;
        float n = 0.5 + fbm(uv * 7.0 + 3.1, 4);
        float n2 = snoise(uv * 40.0 + time * 0.4);
        vec3 col = vec3(0.0);
        for (int i = 0; i < 3; i++) {
          float k = m[i], gl = g1[i], gw = g2[i];
          // burn in: a front sweeping down the stroke (noisy); burn away: a front with a hot edge eating it
          float front = reveal[i] * 1.5 - 0.25;
          float y = uv.y + (n - 0.5) * 0.25;
          float shown = smoothstep(front, front - 0.06, y);
          float edgeIn = exp(-abs(y - front) * 30.0) * step(0.001, reveal[i]) * step(reveal[i], 0.999);
          float bf = burn[i] * 1.3 - 0.15;
          float eaten = smoothstep(bf - 0.02, bf + 0.02, n + n2 * 0.05);
          float edgeOut = exp(-abs(n + n2 * 0.05 - bf) * 26.0) * step(0.001, burn[i]) * step(burn[i], 0.999);
          float vis = shown * eaten;
          vec3 core = mix(vec3(0.55, 0.02, 0.04), vec3(1.25, 0.10, 0.10), 0.5 + 0.5 * snoise(uv * 9.0 + float(i) + time * 0.6));
          col += core * k * vis * (0.8 + hot3[i] * 3.0);
          col += vec3(1.6, 0.25, 0.12) * gl * vis * 0.55;   // inner glow
          col += vec3(0.9, 0.06, 0.05) * gw * vis * 0.6;    // wide glow
          col += vec3(3.0, 1.6, 0.8) * (edgeIn * k * 3.0 + edgeIn * gl * 1.2);
          col += vec3(3.2, 1.3, 0.4) * (edgeOut * (k + gl * 0.8)) * 2.0;
        }
        fragColor = vec4(col * amp, 0.0);
      }`,
    transparent: true, depthWrite: false, depthTest: false, blending: THREE.CustomBlending, ...ADD,
  });
  const mesh = new THREE.Mesh(geo, mat);
  return { mesh, mat, tex };
}
