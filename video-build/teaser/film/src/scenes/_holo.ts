// A floating holographic screen showing a still of a game's real arena: a camera-facing card with scanlines,
// a glowing frame, a little chromatic flicker while it switches on. Used in `rift` behind each era's figure
// so the three figures read as three games (mrwang 2026-10-11).
import * as THREE from 'three';

const PRE = `precision highp float;\nprecision highp int;\n`;

export async function makeHolo(url: string, w: number, h: number, tint: [number, number, number]) {
  const tex = await new THREE.TextureLoader().loadAsync(url);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  const geo = new THREE.PlaneGeometry(w, h);
  const mat = new THREE.RawShaderMaterial({
    glslVersion: THREE.GLSL3,
    uniforms: { map: { value: tex }, on: { value: 0 }, time: { value: 0 }, tint: { value: new THREE.Vector3(...tint) }, aspect: { value: w / h } },
    vertexShader: PRE + /* glsl */ `
      in vec3 position; in vec2 uv;
      uniform mat4 modelViewMatrix, projectionMatrix;
      out vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: PRE + /* glsl */ `
      out vec4 fragColor;
      in vec2 vUv;
      uniform sampler2D map; uniform float on, time, aspect; uniform vec3 tint;
      float hash(float n) { return fract(sin(n) * 43758.5453); }
      void main() {
        // switch-on: the screen opens from a bright horizontal line, then settles
        float open = smoothstep(0.0, 0.55, on);
        float half_ = 0.5 * open;
        float dy = abs(vUv.y - 0.5);
        if (dy > half_ + 0.004) discard;
        float jitter = (hash(floor(time * 30.0) + floor(vUv.y * 60.0)) - 0.5) * 0.02 * (1.0 - smoothstep(0.4, 1.0, on));
        vec2 uv = vec2(vUv.x + jitter, 0.5 + (vUv.y - 0.5) / max(open, 0.02));
        vec3 c;
        c.r = texture(map, uv + vec2(0.003, 0.0)).r;
        c.g = texture(map, uv).g;
        c.b = texture(map, uv - vec2(0.003, 0.0)).b;
        float scan = 0.9 + 0.1 * sin(vUv.y * 420.0 + time * 6.0);
        float roll = 0.9 + 0.1 * smoothstep(0.0, 0.08, abs(fract(vUv.y * 0.5 - time * 0.35) - 0.5));
        // frame: thin bright border plus a soft inner glow
        vec2 e = min(vUv, 1.0 - vUv) * vec2(aspect, 1.0);
        float edge = min(e.x, e.y);
        float border = smoothstep(0.012, 0.0, edge);
        float inner = smoothstep(0.12, 0.0, edge);
        float flick = 0.92 + 0.08 * hash(floor(time * 24.0));
        vec3 col = pow(c, vec3(0.85)) * scan * roll * 1.55 + tint * (border * 2.2 + inner * 0.35);
        float line = smoothstep(0.02, 0.0, abs(dy - half_)) * (1.0 - smoothstep(0.5, 0.9, on)) * 3.0;
        col += tint * line;
        float a = clamp(0.88 * flick + border, 0.0, 1.0) * smoothstep(0.0, 0.08, on);
        a = max(a, line * 0.8);
        fragColor = vec4(col * a, a);
      }`,
    transparent: true, depthWrite: false, depthTest: true,
    blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.renderOrder = -1;
  return { mesh, mat };
}
