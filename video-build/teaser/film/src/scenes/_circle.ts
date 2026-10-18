// The summoning circle: a flat procedural sigil (rings, rune band, star, ticks) drawn in a ground quad.
import * as THREE from 'three';
import { GLSL_COMMON } from '../engine/glsl/common';
import { ADD } from './_grail';

const PRE = `precision highp float;\nprecision highp int;\n`;

export function makeCircle(radius: number, runes: THREE.Texture) {
  const geo = new THREE.PlaneGeometry(radius * 2.4, radius * 2.4);
  geo.rotateX(-Math.PI / 2);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      runes: { value: runes }, draw: { value: 0 }, power: { value: 0 }, spin: { value: 0 }, time: { value: 0 },
      color: { value: new THREE.Vector3(1.0, 0.7, 0.32) }, hot: { value: new THREE.Vector3(1.0, 0.92, 0.75) }, points: { value: 5 }, seed: { value: 0 },
    },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vP;
      void main() { vP = (uv - 0.5) * 2.4; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec2 vP;
      uniform sampler2D runes; uniform float draw, power, spin, time, points, seed; uniform vec3 color, hot;
      float ring(float r, float r0, float w) { float aa = fwidth(r) * 1.2; return 1.0 - smoothstep(w - aa, w + aa, abs(r - r0)); }
      float seg(vec2 p, vec2 a, vec2 b, float w) { float aa = fwidth(p.x) * 1.2; return 1.0 - smoothstep(w - aa, w + aa, sdSegment(p, a, b)); }
      void main() {
        vec2 p = vP;            // radius 1 = the outer ring
        float r = length(p);
        float a = atan(p.y, p.x);
        float u = fract(a / TAU + 0.25);              // 0 at the top, clockwise-ish
        // the circle is drawn on: a sweep around (draw 0 -> 1)
        float sweep = 1.0 - smoothstep(draw * 1.04 - 0.04, draw * 1.04, u);
        sweep = draw >= 1.0 ? 1.0 : sweep;
        float m = 0.0;
        m += ring(r, 1.0, 0.012) + ring(r, 0.955, 0.004) + ring(r, 0.72, 0.008) + ring(r, 0.66, 0.003) + ring(r, 0.30, 0.006);
        // rune band between 0.76 and 0.94, rotating
        if (r > 0.76 && r < 0.94) {
          float v = (r - 0.76) / 0.18;
          float ru = fract(u * 3.0 + spin);
          m += texture(runes, vec2(ru + seed, v)).r * 0.9;
        }
        // tick marks outside the outer ring
        float tk = step(1.015, r) * step(r, 1.06) * (1.0 - smoothstep(0.0, 0.004, abs(fract(u * 120.0) - 0.5) / 120.0 * TAU - 0.0015));
        m += tk * 0.6;
        // the star: {points} vertices on r = 0.66, connected every second vertex, counter-rotating
        float st = 0.0;
        float rot = -spin * TAU * 0.5;
        for (int i = 0; i < 7; i++) {
          if (float(i) >= points) break;
          float a0 = rot + TAU * float(i) / points, a1 = rot + TAU * float(i + 2) / points;
          st = max(st, seg(p, 0.66 * vec2(sin(a0), cos(a0)), 0.66 * vec2(sin(a1), cos(a1)), 0.005));
          // small circles at the vertices
          st = max(st, ring(length(p - 0.66 * vec2(sin(a0), cos(a0))), 0.05, 0.004));
        }
        m += st;
        // inner sun: radial spokes
        float sp = (1.0 - smoothstep(0.0, 0.01, abs(fract(u * 24.0 - spin * 2.0) - 0.5) / 24.0 * TAU * r)) * step(0.1, r) * step(r, 0.28);
        m += sp * 0.5;
        m *= sweep;
        // ignition: a bright wave running outward, then a steady burn with flicker
        float wave = exp(-abs(r - power * 1.3) * 10.0) * step(0.001, power) * (1.0 - smoothstep(0.8, 1.0, power));
        float flick = 0.9 + 0.1 * snoise(vec2(a * 3.0, time * 3.0));
        vec3 c = color * m * (0.25 + 1.8 * power) * flick + hot * m * wave * 3.0;
        // glow pool on the ground
        c += color * exp(-r * 2.6) * 0.35 * power * smoothstep(1.2, 0.6, r);
        float edge = smoothstep(1.2, 1.05, r);
        fragColor = vec4(c * edge, 0.0);
      }`,
    transparent: true, depthWrite: false, blending: THREE.CustomBlending, ...ADD,
  });
  const mesh = new THREE.Mesh(geo, mat);
  return { mesh, mat };
}
