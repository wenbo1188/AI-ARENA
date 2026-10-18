// Real game footage: JPG sequences at 60 fps under public/footage/<clip>/%05d.jpg, loaded as textures ahead of
// each frame (Scene.prepare), and a grading pass to sit them inside the film.
import * as THREE from 'three';
import { FSPass } from '../engine/gl';

export class Footage {
  private cache = new Map<string, THREE.Texture>();
  private order: string[] = [];
  constructor(public cap = 40) {}
  key(clip: string, i: number) { return `${clip}/${String(i).padStart(5, '0')}`; }
  async load(clip: string, i: number) {
    const k = this.key(clip, i);
    if (this.cache.has(k)) return;
    const res = await fetch(`footage/${k}.jpg`);
    if (!res.ok) throw new Error(`footage missing: ${k}`);
    const bmp = await createImageBitmap(await res.blob(), { imageOrientation: 'flipY' });
    const tex = new THREE.Texture(bmp as unknown as HTMLImageElement);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.minFilter = THREE.LinearFilter;
    tex.generateMipmaps = false;
    tex.flipY = false;
    tex.needsUpdate = true;
    this.cache.set(k, tex);
    this.order.push(k);
    while (this.order.length > this.cap) {
      const old = this.order.shift()!;
      const t = this.cache.get(old);
      if (t) { t.dispose(); (t.image as ImageBitmap).close?.(); }
      this.cache.delete(old);
    }
  }
  get(clip: string, i: number) { return this.cache.get(this.key(clip, i)) ?? null; }
}

/** Grade: exposure, contrast around mid grey, saturation, lift/gain tint, zoom/offset, an optional RGB split. */
export function makeGrade() {
  return new FSPass(/* glsl */ `
    uniform sampler2D img; uniform float exposure, contrast, satK, zoom, split, fade, blurK; uniform vec3 lift, gain; uniform vec2 offset;
    vec3 tap(vec2 uv) { return texture(img, clamp(uv, vec2(0.001), vec2(0.999))).rgb; }
    void main() {
      vec2 uv = (vUv - 0.5) / zoom + 0.5 + offset;
      vec3 c;
      if (split > 0.0) {
        vec2 d = (uv - 0.5) * split * 0.02;
        c = vec3(tap(uv + d).r, tap(uv).g, tap(uv - d).b);
      } else c = tap(uv);
      if (blurK > 0.0) {
        // defocus: a 48-tap Vogel disc whose radius shrinks with blurK, so easing blurK to 0 reads as a focus pull
        vec3 s = vec3(0.0);
        float r = blurK * 0.035;
        for (int i = 0; i < 48; i++) {
          float k = float(i) + 0.5, a = k * 2.39996;
          s += tap(uv + vec2(cos(a) / 1.7778, sin(a)) * r * sqrt(k / 48.0));
        }
        c = s / 48.0;
      }
      c *= exposure;
      float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
      c = mix(vec3(l), c, satK);
      c = (c - 0.18) * contrast + 0.18;
      c = max(c, 0.0) * gain + lift * (1.0 - min(c, 1.0));
      fragColor = vec4(c * fade, 1.0);
    }`, {
    img: { value: null }, exposure: { value: 1 }, contrast: { value: 1 }, satK: { value: 1 }, zoom: { value: 1 }, split: { value: 0 }, fade: { value: 1 }, blurK: { value: 0 },
    lift: { value: new THREE.Vector3(0, 0, 0) }, gain: { value: new THREE.Vector3(1, 1, 1) }, offset: { value: new THREE.Vector2(0, 0) },
  });
}
