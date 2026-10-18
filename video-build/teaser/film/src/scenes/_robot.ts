// The football robot, ported from the arena's own CodeBall viewer (arena/games/football/viewer.py buildRobot):
// a low-poly astronaut robot in team colour, white torso, a dark-blue visor, big fists and boots, a nitro pack.
// Height ≈ 2 units (radius-1 physics sphere); scale the returned group.
import * as THREE from 'three';

function canvasTex(w: number, h: number, draw: (g: CanvasRenderingContext2D, w: number, h: number) => void) {
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  draw(cv.getContext('2d')!, w, h);
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function buildRobot(col = 0x13b832, css = '#16a34a', num = '1') {
  const root = new THREE.Group();
  const body = new THREE.Group(); root.add(body);
  body.position.y = 1.0;
  const metal = new THREE.MeshStandardMaterial({ color: new THREE.Color(col), roughness: 0.42, metalness: 0.05, flatShading: true, emissive: new THREE.Color(0, 0, 0) });
  const white = new THREE.MeshStandardMaterial({ color: 0xeef0f3, roughness: 0.45, metalness: 0.02, flatShading: true, emissive: new THREE.Color(0, 0, 0) });
  const whiteDS = white.clone(); whiteDS.side = THREE.DoubleSide;
  const dark = new THREE.MeshStandardMaterial({ color: 0x15181e, roughness: 0.6, flatShading: true });
  const visor = new THREE.MeshPhysicalMaterial({ color: 0x0e2d55, metalness: 0.2, roughness: 0.1, clearcoat: 1, clearcoatRoughness: 0.05, emissive: new THREE.Color(0, 0, 0) });
  const add = (geo: THREE.BufferGeometry, mat: THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D = body) => {
    const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); parent.add(m); return m;
  };
  const cyl = (r0: number, r1: number, h: number, seg = 6) => new THREE.CylinderGeometry(r0, r1, h, seg);
  const box = (w: number, h: number, d: number) => new THREE.BoxGeometry(w, h, d);
  add(cyl(0.37, 0.33, 0.14, 8), metal, 0, 0.17, 0).rotation.y = Math.PI / 8;
  add(cyl(0.33, 0.24, 0.36, 8), white, 0, -0.06, 0).rotation.y = Math.PI / 8;
  add(cyl(0.25, 0.2, 0.13, 8), metal, 0, -0.29, 0).rotation.y = Math.PI / 8;
  add(cyl(0.27, 0.3, 0.07, 10), white, 0, 0.26, 0);
  const numTex = canvasTex(256, 128, (g, w, h) => {
    g.fillStyle = '#eef2f8'; g.fillRect(0, 0, w, h);
    g.fillStyle = css; g.fillRect(0, 0, w, 16); g.fillRect(0, h - 12, w, 12);
    g.font = '900 86px "Archivo-1000-900", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(num, w / 2, h / 2 + 4);
  });
  const plate = add(new THREE.PlaneGeometry(0.22, 0.11), new THREE.MeshStandardMaterial({ map: numTex, roughness: 0.5 }), 0, -0.02, 0.305);
  plate.rotation.x = -0.22;
  const head = new THREE.Group(); head.position.set(0, 0.56, 0); body.add(head);
  add(new THREE.IcosahedronGeometry(0.42, 1), metal, 0, 0.02, -0.03, head).scale.set(1, 0.93, 0.98);
  add(new THREE.SphereGeometry(0.335, 40, 28), visor, 0, -0.01, 0.12, head);
  add(new THREE.CylinderGeometry(0.33, 0.33, 0.09, 14, 1, true, -1.25, 2.5), whiteDS, 0, -0.29, 0.06, head).scale.set(1, 1, 1.05);
  for (const sx of [-1, 1]) {
    add(box(0.12, 0.3, 0.3), metal, sx * 0.4, 0.04, 0.02, head);
    for (let k = -1; k <= 1; k++) add(box(0.015, 0.2, 0.035), dark, sx * 0.462, 0.04, 0.02 + k * 0.07, head);
  }
  const arms = [-1, 1].map((sx) => {
    add(new THREE.IcosahedronGeometry(0.12, 0), metal, sx * 0.4, 0.13, 0);
    const pv = new THREE.Group(); pv.position.set(sx * 0.44, 0.12, 0); pv.rotation.z = sx * 0.22; body.add(pv);
    add(cyl(0.07, 0.065, 0.2, 6), white, 0, -0.12, 0, pv);
    add(box(0.22, 0.24, 0.25), metal, 0, -0.32, 0.03, pv);
    for (const dz of [-0.04, 0.05]) add(box(0.226, 0.035, 0.035), white, 0, -0.26, 0.03 + dz, pv);
    add(box(0.2, 0.08, 0.2), metal, 0, -0.47, 0.05, pv).rotation.x = 0.3;
    return pv;
  });
  const legs = [-1, 1].map((sx) => {
    const pv = new THREE.Group(); pv.position.set(sx * 0.17, -0.36, 0); body.add(pv);
    add(new THREE.IcosahedronGeometry(0.1, 0), metal, 0, -0.04, 0, pv);
    add(cyl(0.12, 0.16, 0.3, 6), white, 0, -0.22, 0, pv);
    for (const dy of [-0.2, -0.27]) add(box(0.3, 0.03, 0.12), metal, 0, dy, 0.07, pv).rotation.x = -0.35;
    add(box(0.25, 0.17, 0.38), metal, 0, -0.46, 0.05, pv);
    add(box(0.23, 0.07, 0.12), metal, 0, -0.42, 0.25, pv).rotation.x = 0.5;
    for (const dx of [-1, 1]) add(box(0.01, 0.04, 0.2), white, dx * 0.128, -0.45, 0.06, pv);
    return pv;
  });
  add(box(0.42, 0.36, 0.17), white, 0, 0.0, -0.34);
  add(box(0.44, 0.06, 0.18), metal, 0, 0.12, -0.34);
  add(new THREE.CylinderGeometry(0.12, 0.17, 0.2, 16, 1, true), new THREE.MeshStandardMaterial({ color: 0xaab4c2, metalness: 0.9, roughness: 0.25, side: THREE.DoubleSide }), 0, -0.04, -0.5).rotation.x = Math.PI / 2;
  // nitro flame: additive cones out of the back
  const flame = new THREE.Group(); flame.position.set(0, -0.04, -0.6); flame.rotation.x = -Math.PI / 2; body.add(flame);
  const flameTex = canvasTex(32, 128, (g, w, h) => {
    const gr = g.createLinearGradient(0, h, 0, 0);
    gr.addColorStop(0, 'rgba(255,250,225,1)'); gr.addColorStop(0.3, 'rgba(255,170,60,1)'); gr.addColorStop(0.7, 'rgba(230,70,20,0.6)'); gr.addColorStop(1, 'rgba(120,20,10,0)');
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
  });
  const fmat = new THREE.MeshBasicMaterial({ map: flameTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, side: THREE.DoubleSide, color: new THREE.Color(3, 3, 3) });
  for (const [r, l] of [[0.18, 1.9], [0.1, 1.2]] as const) { const g = new THREE.ConeGeometry(r, l, 16, 1, true); g.translate(0, l / 2, 0); flame.add(new THREE.Mesh(g, fmat)); }
  flame.visible = false;
  return { root, body, head, arms, legs, flame, mats: [metal, white, whiteDS, visor] as (THREE.MeshStandardMaterial | THREE.MeshPhysicalMaterial)[] };
}
