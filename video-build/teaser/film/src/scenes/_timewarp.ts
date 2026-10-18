// The time jump between eras (mrwang 2026-10-11: the matches run in order and time moves on after each, shown
// without words). The frame is pulled into a radial rush toward the centre while a clock dial spins up around it,
// time-streaks in the eras' colours pour past, a white-hot flash at the cut, and the next era rushes out of the
// centre as the dial expands past the edges. `dir` -1 spins the dial backwards (into the first era).
import * as THREE from 'three';
import { FSPass, W, H } from '../engine/gl';

export function makeTimeWarp() {
  return new FSPass(/* glsl */ `
    uniform sampler2D src;
    uniform float kOut, kIn, dir, time, aspect;
    uniform vec3 colA, colB;
    void main() {
      float e = max(kOut, kIn);
      vec2 c = vUv - 0.5;
      // leaving: the picture is sucked into the centre; arriving: it bursts out of it
      float scale = kOut > 0.0 ? 1.0 / (1.0 + 2.6 * kOut * kOut) : 1.0 - 0.55 * kIn * kIn;
      vec2 base = c * scale;
      float blur = 0.42 * e;
      vec3 acc = vec3(0.0); float wsum = 0.0;
      for (int i = 0; i < 28; i++) {
        float f = float(i) / 27.0;
        float w = 1.0 - 0.6 * f;
        vec2 uv = 0.5 + base * (1.0 - blur * f);
        acc += texture(src, uv).rgb * w; wsum += w;
      }
      vec3 col = acc / wsum;
      vec3 tint = mix(colA, colB, kOut > 0.0 ? 0.5 * kOut : 1.0 - 0.5 * kIn);
      col = mix(col, col * 0.55 + tint * dot(col, vec3(0.3, 0.5, 0.2)) * 1.2, 0.6 * e);
      // polar frame for the dial and streaks
      vec2 p = c * vec2(aspect, 1.0);
      float r = length(p), a = atan(p.y, p.x);
      // time streaks pouring outward
      float bins = 180.0, bin = floor((a / TAU + 0.5) * bins), h = hash11(bin * 1.37);
      float z = 0.22 / (r + 0.015);
      float dash = smoothstep(0.6, 0.92, fract(z * (0.25 + 0.3 * h) - time * 6.0 * (0.6 + 0.6 * h) + h * 9.0));
      float thin = 1.0 - smoothstep(0.15, 0.5, abs(fract((a / TAU + 0.5) * bins) - 0.5));
      col += tint * dash * thin * step(0.45, hash11(bin * 3.1)) * smoothstep(0.05, 0.3, r) * 1.6 * e;
      // the dial: a ring of ticks, a numeral-like heavier tick every 30 degrees, a sweeping hand
      float R = kOut > 0.0 ? mix(0.62, 0.3, kOut) : mix(0.3, 1.3, 1.0 - kIn);
      float spin = dir * (kOut > 0.0 ? kOut * kOut * 9.0 : (1.0 - kIn) * 3.0 + 9.0);
      float ring = exp(-abs(r - R) * 260.0) + 0.6 * exp(-abs(r - R * 0.86) * 400.0);
      float ta = fract((a + spin * 0.1) / TAU * 60.0);
      float tick = step(0.82, ta) * step(R * 0.9, r) * step(r, R * 0.97);
      float big = step(0.9, fract((a + spin * 0.1) / TAU * 12.0)) * step(R * 0.84, r) * step(r, R);
      float hand_a = mod(a - spin + PI, TAU) - PI;
      float hand = exp(-abs(hand_a) * r * 220.0) * step(r, R * 0.82) * smoothstep(0.02, 0.06, r);
      vec3 dialCol = mix(vec3(1.0, 0.86, 0.6), tint, 0.35);
      col += dialCol * (ring * 1.5 + tick * 0.9 + big * 1.4 + hand * 1.8) * e;
      // white-hot heart at the cut
      col += vec3(1.3, 1.05, 0.85) * exp(-r * mix(16.0, 4.0, e * e)) * e * e * 1.4;
      col = mix(col, vec3(1.25, 1.1, 0.95), pow(e, 9.0) * 0.7);
      fragColor = vec4(col, 1.0);
    }`, {
    src: { value: null }, kOut: { value: 0 }, kIn: { value: 0 }, dir: { value: 1 }, time: { value: 0 }, aspect: { value: W / H },
    colA: { value: new THREE.Vector3(1, 0.76, 0.35) }, colB: { value: new THREE.Vector3(0.35, 0.9, 1.0) },
  });
}
/** Era colours: gold (medieval), cyan (1987), crimson (2087). */
export const ERA_COL: [number, number, number][] = [[1.0, 0.72, 0.32], [0.3, 0.88, 1.0], [1.0, 0.3, 0.24]];
