// The time vortex: a tunnel of streaks in the three eras' colours, clock rings rushing past, a white-hot far end.
import * as THREE from 'three';
import { FSPass, W, H } from '../engine/gl';

export function makeVortex() {
  return new FSPass(/* glsl */ `
      uniform float time, k, aspect, title;
      void main() {
        vec2 p = (vUv - 0.5) * vec2(aspect, 1.0);
        float r = length(p), a = atan(p.y, p.x);
        float z = 0.22 / (r + 0.015);
        float spd = time * 5.0;
        float bins = 220.0;
        float bin = floor((a / TAU + 0.5) * bins);
        float h = hash11(bin * 1.37);
        float dash = smoothstep(0.55, 0.9, fract(z * (0.25 + 0.3 * h) - spd * (0.6 + 0.6 * h) + h * 9.0));
        float thin = 1.0 - smoothstep(0.2, 0.5, abs(fract((a / TAU + 0.5) * bins) - 0.5));
        float streak = dash * thin * step(0.35, hash11(bin * 3.1));
        // era bands around the tunnel: gold (medieval), cyan (1987), crimson (2087)
        float u = a / TAU + 0.5 + time * 0.05;
        vec3 band = mix(mix(C_GOLD, C_CYAN, smoothstep(0.25, 0.45, fract(u))), C_CRIMSON, smoothstep(0.6, 0.8, fract(u)));
        band = mix(band, C_GOLD, smoothstep(0.9, 1.0, fract(u)));
        float cloud = fbm(vec2(a * 2.0, z * 0.6 - spd * 0.4), 4);
        vec3 c = band * streak * (0.35 + 1.4 * smoothstep(2.0, 0.4, z));
        c += band * smoothstep(-0.2, 0.6, cloud) * 0.18 * smoothstep(8.0, 1.0, z);
        // clock rings rushing past
        float rz = fract(z * 0.18 - spd * 0.12);
        float ring = exp(-abs(rz - 0.5) * 60.0);
        float ticks = step(0.75, fract((a / TAU + 0.5) * 60.0)) ;
        c += vec3(1.0, 0.85, 0.6) * ring * (0.25 + 0.75 * ticks) * smoothstep(9.0, 2.0, z) * 0.8;
        // the far end: white-hot
        c += vec3(1.2, 0.9, 0.75) * exp(-r * 14.0) * 1.2;
        // darker heart behind the title once it lands
        c *= 1.0 - title * 0.7 * exp(-pow(p.y * 3.2, 2.0)) * smoothstep(1.1, 0.2, abs(p.x));
        c *= smoothstep(0.0, 0.25, r * 3.0 + 0.1);
        fragColor = vec4(c * k, 1.0);
      }`, { time: { value: 0 }, k: { value: 1 }, aspect: { value: W / H }, title: { value: 0 } });
}
export type Vortex = ReturnType<typeof makeVortex>;
void THREE;
