// The masters' servants: figures of light on black (servant_<vendor>.png, 1024x1536), keyed by brightness and
// stood in the summoning circles as upright cards that turn to face the camera. They materialise bottom-up with a
// hot seam, shimmer faintly, and pass the beams behind them through their translucent cloth.
import * as THREE from 'three';
import { GLSL_COMMON } from '../engine/glsl/common';

const PRE = `precision highp float;\nprecision highp int;\n`;
/** In MASTERS order. The sixth seat is UNKNOWN: a figure of shadow (servant_unknown_a.png, straight alpha),
 *  drawn by its own alpha instead of being keyed by brightness. */
export const SERVANT_FILES = ['anthropic', 'openai', 'deepseek', 'glm', 'minimax', 'unknown_a'];
export const isShadow = (name: string) => name.startsWith('unknown');
/** Where the feet are in each picture (fraction of the height from the bottom). */
const FEET = 0.06;

export async function loadServantTex(name: string) {
  // (the UNKNOWN shadow has straight alpha: no mipmap fringe from premultiplying, colour is near black anyway)
  const tex = await new THREE.TextureLoader().loadAsync(`assets/servant_${name}.png`);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.generateMipmaps = true;
  tex.anisotropy = 4;
  return tex;
}

/** A card `h` world units tall (the picture's full height), feet at the local origin. */
export function makeServant(tex: THREE.Texture, h: number) {
  const w = h * (1024 / 1536);
  const geo = new THREE.PlaneGeometry(w, h);
  geo.translate(0, h * (0.5 - FEET), 0);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      map: { value: tex }, shadow: { value: 0 }, appear: { value: 0 }, amp: { value: 1 }, time: { value: 0 }, seed: { value: 0 },
      opacity: { value: 1 }, tint: { value: new THREE.Vector3(1, 0.92, 0.8) },
    },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec2 vUv;
      uniform sampler2D map; uniform float shadow, appear, amp, time, seed, opacity; uniform vec3 tint;
      void main() {
        vec4 tx = texture(map, vUv);
        vec3 c = tx.rgb;
        float l = max(c.r, max(c.g, c.b));
        float a = mix(smoothstep(0.004, 0.12, l), tx.a, shadow);
        c *= mix(1.0, tx.a, shadow);
        // materialise from the feet up along a ragged front, a hot seam at the front
        float n = fbm(vec2(vUv.x * 7.0 + seed * 13.0, vUv.y * 5.0 - time * 0.4), 3) * 0.12;
        float front = appear * 1.25 - 0.1;
        float y = vUv.y + n;
        float vis = smoothstep(front, front - 0.05, y);
        float seam = exp(-pow((y - front) / 0.018, 2.0)) * step(0.001, appear) * (1.0 - smoothstep(0.85, 1.0, appear));
        // faint shimmer: slow vertical bands of brightness moving up through the figure
        float sh = 0.9 + 0.1 * sin(vUv.y * 40.0 - time * 3.0 + seed * 6.0) + 0.08 * snoise(vec2(vUv.x * 9.0, vUv.y * 6.0 - time * 0.8));
        vec3 col = c * tint * amp * sh * vis;
        col += mix(vec3(3.2, 2.0, 1.0), vec3(1.2, 1.4, 2.6), shadow) * seam * smoothstep(0.0, 0.05, l + 0.02) * (0.4 + a);
        // the shadow flickers: thin bands of it drop out now and then
        float band = floor(vUv.y * 60.0), tick = floor(time * 12.0);
        float drop = shadow * step(0.93, fract(sin(band * 12.99 + tick * 78.2 + seed) * 43758.5)) * step(0.5, fract(sin(tick * 3.7 + seed) * 951.1));
        float alpha = a * vis * mix(0.82, 0.96, shadow) * (1.0 - 0.3 * drop);
        col *= 1.0 - 0.3 * drop;
        fragColor = vec4(col * opacity, alpha * opacity);
      }`,
    transparent: true,
    depthWrite: false,
    blending: THREE.CustomBlending,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.OneFactor,
    blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  return { mesh, mat };
}

/** Turn a card about the vertical axis to face the camera. */
export function faceY(mesh: THREE.Object3D, cam: THREE.Camera) {
  mesh.rotation.set(0, Math.atan2(cam.position.x - mesh.position.x, cam.position.z - mesh.position.z), 0);
}
