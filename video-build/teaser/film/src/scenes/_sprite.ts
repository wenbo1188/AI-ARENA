// Pixel-art servants as camera-facing cards in the 3D scene: crisp nearest sampling, a frame from an atlas,
// lit by a key/rim tint, and a materialize dissolve (pixel blocks appearing bottom-up behind a hot edge).
import * as THREE from 'three';
import { GLSL_COMMON } from '../engine/glsl/common';

const PRE = `precision highp float;\nprecision highp int;\n`;

export async function loadPixelTex(url: string) {
  const tex = await new THREE.TextureLoader().loadAsync(url);
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.generateMipmaps = true;
  return tex;
}

/** A card `w`×`h` world units with its pivot (feet) at local origin; `pivot` is in card-uv (0..1, y up). */
export function makeSpriteCard(tex: THREE.Texture, w: number, h: number, pivot: [number, number], cols = 1, rows = 1) {
  const geo = new THREE.PlaneGeometry(w, h);
  geo.translate(w * (0.5 - pivot[0]), h * (0.5 - pivot[1]), 0);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: {
      map: { value: tex }, frame: { value: 0 }, grid: { value: new THREE.Vector2(cols, rows) }, flip: { value: 0 },
      appear: { value: 1 }, key: { value: new THREE.Vector3(1, 1, 1) }, rim: { value: new THREE.Vector3(0, 0, 0) },
      glowCol: { value: new THREE.Vector3(1.0, 0.25, 0.15) }, flash: { value: 0 }, texel: { value: new THREE.Vector2(1, 1) }, opacity: { value: 1 },
    },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: PRE + `out vec4 fragColor;\n` + GLSL_COMMON + /* glsl */ `
      in vec2 vUv;
      uniform sampler2D map; uniform float frame, flip, appear, flash, opacity; uniform vec2 grid, texel; uniform vec3 key, rim, glowCol;
      vec4 tap(vec2 uv) {
        vec2 fr = vec2(mod(frame, grid.x), floor(frame / grid.x));
        vec2 u = vec2(flip > 0.5 ? 1.0 - uv.x : uv.x, uv.y);
        vec2 a = (fr + u) / grid; a.y = 1.0 - ((fr.y + 1.0 - u.y) / grid.y);
        return texture(map, a);
      }
      void main() {
        vec4 c = tap(vUv);
        // rim: alpha edge on the side facing the light behind (approximate with neighbour alpha)
        float e = 0.0;
        e += 1.0 - tap(vUv + vec2(texel.x, 0.0)).a;
        e += 1.0 - tap(vUv - vec2(texel.x, 0.0)).a;
        e += 1.0 - tap(vUv + vec2(0.0, texel.y)).a;
        e = clamp(e, 0.0, 1.0) * c.a;
        // materialize: blocks fill in bottom-up with noise; a hot band at the front
        vec2 blk = floor(vUv / texel / 3.0);
        float n = hash12(blk);
        float front = appear * 1.35 - 0.2;
        float y = vUv.y + (n - 0.5) * 0.25;
        float shown = step(y, front);
        float band = exp(-abs(y - front) * 22.0) * step(0.001, appear) * step(appear, 0.999);
        vec3 col = c.rgb * key + rim * e + glowCol * (band * 4.0 + flash * 2.0) * c.a;
        float a = c.a * max(shown, band) * opacity;
        if (a < 0.02) discard;
        fragColor = vec4(col * a, a);
      }`,
    transparent: true, depthWrite: false,
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
    blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
  });
  const img = tex.image as { width: number; height: number };
  (mat.uniforms.texel!.value as THREE.Vector2).set(cols / img.width, rows / img.height);
  const mesh = new THREE.Mesh(geo, mat);
  return { mesh, mat };
}
