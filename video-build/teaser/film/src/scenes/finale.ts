// 0:58.125–1:13.125 `finale` — back to 2031 on the big hit. The rain falls again on the plaza; the six columns stand
// around the pillar, the cracked grail above them. “圣杯只会选择一个。” Then over the drum build the six servants
// and names, one per beat (the sixth a shadow: UNKNOWN), the lockup on the bar, and on the climax (58.125)
// “第一届 · 即将开战” with the call to action.
import * as THREE from 'three';
import { Scene, type Frame, type PostOverrides } from '../engine/scene';
import { Layer2D, W, H } from '../engine/gl';
import { LineBatch } from '../engine/lines';
import { clamp, ease, lerp, prog, pulse } from '../engine/util';
import { City, Rain, cityUniforms, GRAIL_XZ } from './_city';
import { makeChalice, makePillar, makeGlow, runeTexture } from './_grail';
import { makeCircle } from './_circle';
import { circlePos, CIRCLE_R, SERVANT_H, SEATS, UNKNOWN } from './masters';
import { SERVANT_FILES, loadServantTex, makeServant, faceY, isShadow } from './_servant';
import { aim, catmull, cjk, drawRule, loadCJK, revealText, MASTERS, nameLines } from './_film';

const [GX, GZ] = GRAIL_XZ;
/** Beat 0.46875 s. The lineup starts on the bar (film 52.5), one servant per beat. */
const BEAT = 0.46875;
const LINE0 = 4 * BEAT;
const lineAt = (i: number) => LINE0 + i * BEAT;
/** The lockup on the next bar but one (film 56.25), the call to action on the climax (film 58.125). */
const LOCK = 12 * BEAT, CLIMAX = 16 * BEAT;
/** v10 (73 s music, one continuous take; the finale now starts on the phrase at film 58.125, lockup 63.75, call to
 *  action 65.625 as the music starts to fade): on film 67.5 the card opens into the end slate (title up, the six
 *  servants back above their names, one per beat); black at film 73.1. */
const SLATE = 20 * BEAT, SL_CARD = SLATE + BEAT, END = 32 * BEAT;
const slateK = (lt: number) => ease.inOutCubic(prog(lt, SLATE, SLATE + 0.85));

export default class Finale extends Scene {
  cam = new THREE.PerspectiveCamera(46, W / H, 1, 9000);
  u = cityUniforms();
  city!: City;
  fx = new THREE.Scene();
  grail = makeChalice();
  pillar = makePillar(7, 1);
  glow = makeGlow(380);
  circles: ReturnType<typeof makeCircle>[] = [];
  beams: ReturnType<typeof makePillar>[] = [];
  servants: ReturnType<typeof makeServant>[] = [];
  cards: ImageBitmap[] = [];
  rain = new Rain(LineBatch);
  text = new Layer2D();

  override async init() {
    await loadCJK();
    await document.fonts.load('700 34px "Archivo-1000-700"', 'OPUS5.GPT6-AstraDeepSeekv4.1FlashGLM-3MinimaxM3PreviewUNKNOWN');
    this.city = new City(this.u);
    this.u.grailPos.value.set(GX, 560, GZ);
    this.u.grailLight.value = 0.9;
    this.u.pillar.value = 1;
    this.city.sky.u.hole!.value = 640;
    const runes = runeTexture(5, 2048, 96);
    for (let i = 0; i < SEATS; i++) {
      const c = makeCircle(CIRCLE_R, runes);
      const [x, z] = circlePos(i);
      c.mesh.position.set(x, 0.4, z);
      c.mat.uniforms.seed!.value = i * 0.19;
      c.mat.uniforms.draw!.value = 1;
      c.mat.uniforms.power!.value = 1;
      this.fx.add(c.mesh);
      this.circles.push(c);
      const b = makePillar(3.2, 1);
      if (i === UNKNOWN) (b.mat.uniforms.color!.value as THREE.Vector3).set(0.45, 0.5, 0.8);
      b.mesh.position.set(x, 0, z);
      this.fx.add(b.mesh);
      this.beams.push(b);
    }
    const texs = await Promise.all(SERVANT_FILES.map(loadServantTex));
    this.cards = await Promise.all(SERVANT_FILES.map(async (n) => createImageBitmap(await (await fetch(`assets/servant_${isShadow(n) ? n : n + '_a'}.png`)).blob())));
    for (let i = 0; i < SEATS; i++) {
      const sv = makeServant(texs[i]!, SERVANT_H);
      const [x, z] = circlePos(i);
      sv.mesh.position.set(x, 0.6, z);
      sv.mat.uniforms.seed!.value = i * 0.37;
      sv.mat.uniforms.appear!.value = 1;
      sv.mesh.visible = false; // (from down here they only show cut off at the frame edges; the lineup carries them)
      this.fx.add(sv.mesh);
      this.servants.push(sv);
    }
    this.fx.add(this.grail.mesh, this.glow.mesh, this.pillar.mesh);
  }

  render(f: Frame, out: THREE.WebGLRenderTarget): PostOverrides {
    const { renderer } = this.ctx;
    const lt = f.lt, t = f.t;
    // from the plaza looking up the pillar to the grail, slowly rising
    const u = ease.inOutCubic(prog(lt, 0, 9.0));
    const p = catmull([[GX + 52, 5, GZ + 70], [GX + 46, 12, GZ + 62], [GX + 38, 24, GZ + 52]], u);
    const tg = catmull([[GX - 34, 70, GZ - 44], [GX - 8, 320, GZ - 12], [GX, 450, GZ]], u);
    const drift = ease.inOutCubic(prog(lt, 9.0, END));
    p[1] += 10 * drift; tg[1] += 30 * drift;
    aim(this.cam, p, tg, -0.03, 48 - 5 * drift);
    this.u.time.value = t;
    this.u.red.value = 0.25;
    this.city.sky.u.lightning!.value = pulse(lt, CLIMAX, 0.08) * 0.8;
    this.city.render(renderer, out, this.cam);

    const gp = this.u.grailPos.value;
    this.grail.mesh.position.copy(gp);
    this.grail.mesh.scale.setScalar(1.25);
    this.grail.mesh.rotation.y = t * 0.12;
    const gm = this.grail.mat.uniforms;
    gm.camPos!.value.copy(this.cam.position); gm.glow!.value = 0.7; gm.time!.value = t;
    gm.crack!.value = 0.4; gm.red!.value = 0.35;
    this.glow.mesh.position.copy(gp);
    this.glow.mat.uniforms.amp!.value = 0.4;
    this.pillar.mesh.position.set(gp.x, 0, gp.z);
    this.pillar.mesh.scale.set(1, gp.y - 60, 1);
    const pm = this.pillar.mat.uniforms;
    pm.camPos!.value.copy(this.cam.position); pm.time!.value = t; pm.amp!.value = 0.9;
    for (let i = 0; i < SEATS; i++) {
      const unk = i === UNKNOWN;
      const cm = this.circles[i]!.mat.uniforms;
      cm.spin!.value = t * 0.03 * (i % 2 ? -1 : 1); cm.time!.value = t;
      if (unk) { (cm.color!.value as THREE.Vector3).set(0.42, 0.48, 0.85); cm.power!.value = 0.45 + 0.08 * Math.sin(t * 2.6); }
      else (cm.color!.value as THREE.Vector3).set(1.0, 0.45, 0.22);
      const b = this.beams[i]!;
      b.mesh.scale.set(1, 700, 1);
      b.mat.uniforms.camPos!.value.copy(this.cam.position);
      b.mat.uniforms.time!.value = t + i;
      // each column flares as its master's name lands
      b.mat.uniforms.amp!.value = unk ? 0.1 + 0.6 * pulse(lt, lineAt(i), 0.2) : 0.25 + 3 * pulse(lt, lineAt(i), 0.2);
      // the servants stand in their circles; each flares with its master's name
      const sv = this.servants[i]!;
      faceY(sv.mesh, this.cam);
      sv.mat.uniforms.time!.value = t;
      sv.mat.uniforms.amp!.value = 0.85 + 1.6 * pulse(lt, lineAt(i), 0.25);
    }
    renderer.setRenderTarget(out);
    renderer.render(this.fx, this.cam);
    this.rain.render(renderer, out, this.cam, t, 0.9);

    const L = this.text; L.clear();
    const x2 = L.ctx;
    x2.textBaseline = 'alphabetic';
    const dark = prog(lt, 1.5, 2.1) * 0.55 + prog(lt, LOCK - 0.3, LOCK + 0.3) * 0.25;
    if (dark > 0) { x2.fillStyle = `rgba(3,4,10,${dark})`; x2.fillRect(0, 0, W, H); }
    // “back to 2031”
    if (lt > 0.15 && lt < LINE0) {
      const fo = 1 - prog(lt, LINE0 - 0.25, LINE0);
      x2.font = '500 15px "Plex-500"';
      revealText(x2, '2031.10.07  00:00', 132, 846, { lt: lt - 0.15, stagger: 0.015, dur: 0.35, rise: 0, blur: 0, alpha: 0.75 * fo, fill: 'rgba(238,233,223,1)', tracking: 2 });
      drawRule(x2, 132, 866, 300, prog(lt, 0.3, 0.9), `rgba(232,176,74,${0.6 * fo})`, 'left');
    }
    if (lt > 0.2 && lt < LINE0) {
      const fo = 1 - prog(lt, LINE0 - 0.25, LINE0);
      const g = x2.createRadialGradient(420, 960, 40, 420, 960, 760);
      g.addColorStop(0, `rgba(3,4,10,${0.8 * fo * prog(lt, 0.2, 0.5)})`); g.addColorStop(1, 'rgba(3,4,10,0)');
      x2.fillStyle = g; x2.fillRect(0, 500, W, H - 500);
      x2.font = cjk('serif', 900, 72);
      revealText(x2, '圣杯只会选择一个。', 120, 990, {
        lt: lt - 0.2, stagger: 0.04, dur: 0.4, rise: 20, blur: 14, alpha: fo, tracking: 14,
        fill: (a, y) => { const g = x2.createLinearGradient(0, y - 76, 0, y + 6); g.addColorStop(0, '#fff2cf'); g.addColorStop(1, '#e2a443'); return g; },
        glow: { color: 'rgba(255,150,40,0.4)', blur: 24 },
      });
    }
    // the six names, equal weight; one servant per beat
    if (lt > LINE0 - 0.05) {
      const m0 = LOCK - 0.45, m1 = LOCK + 0.15;
      const s2 = slateK(lt);
      const fo = lerp(1 - prog(lt, m0, LOCK) * 0.65, 1, s2);
      const ny = lerp(lerp(880, 800, ease.inOutCubic(prog(lt, m0, m1))), 878, s2);
      const sc = lerp(lerp(1, 0.62, ease.inOutCubic(prog(lt, m0, m1))), 0.8, s2);
      for (let i = 0; i < SEATS; i++) {
        const unk = i === UNKNOWN;
        const x = W / 2 + (i - (SEATS - 1) / 2) * 292 * lerp(1, 0.8, (1 - sc) / 0.38);
        const k = lt - lineAt(i);
        if (k <= 0) continue;
        // the servant rises above its master's name, bottom-up
        if (lt < m1) {
          const img = this.cards[i]!, sh = 470, sw = sh * (img.width / img.height);
          const up = ease.outCubic(clamp(k / (unk ? 0.5 : 0.4))), fa = clamp(k / 0.25) * (1 - prog(lt, m0 - 0.05, m1 - 0.1));
          const top = ny - 60 - sh, cut = top + sh * (1 - up);
          x2.save();
          x2.beginPath(); x2.rect(x - sw / 2, cut, sw, ny - 60 - cut + 2); x2.clip();
          x2.globalAlpha = fa;
          x2.drawImage(img, x - sw / 2, top + 14 * (1 - up), sw, sh);
          x2.restore();
          // the seam where it is still forming
          if (up < 0.92 && fa > 0) {
            const g = x2.createLinearGradient(0, cut - 6, 0, cut + 6);
            const sc0 = unk ? '170,185,255' : '255,220,160';
            g.addColorStop(0, `rgba(${sc0},0)`); g.addColorStop(0.5, `rgba(${sc0},${0.8 * fa})`); g.addColorStop(1, `rgba(${sc0},0)`);
            x2.fillStyle = g; x2.fillRect(x - sw * 0.38, cut - 6, sw * 0.76, 12);
          }
        }
        // the end slate: the servant returns above its name, bottom-up, one per beat
        const ks = lt - (SL_CARD + i * BEAT);
        if (ks > 0) {
          const img = this.cards[i]!, sh = 280, sw = sh * (img.width / img.height);
          const up = ease.outCubic(clamp(ks / (unk ? 0.5 : 0.4))), fa = clamp(ks / 0.25);
          const base = ny - 2 * 38 * sc - 22, top = base - sh, cut = top + sh * (1 - up);
          x2.save();
          x2.beginPath(); x2.rect(x - sw / 2, cut, sw, base - cut + 2); x2.clip();
          x2.globalAlpha = fa;
          x2.drawImage(img, x - sw / 2, top + 10 * (1 - up), sw, sh);
          x2.restore();
          if (up < 0.92) {
            const g = x2.createLinearGradient(0, cut - 6, 0, cut + 6);
            const sc0 = unk ? '170,185,255' : '255,220,160';
            g.addColorStop(0, `rgba(${sc0},0)`); g.addColorStop(0.5, `rgba(${sc0},${0.8 * fa})`); g.addColorStop(1, `rgba(${sc0},0)`);
            x2.fillStyle = g; x2.fillRect(x - sw * 0.38, cut - 6, sw * 0.76, 12);
          }
        }
        const name = MASTERS[i]!;
        const latin = /^[A-Za-z]/.test(name);
        // one size for every model name (the long ones wrap), so the row reads evenly
        x2.font = latin ? `700 ${Math.round(36 * sc)}px "Archivo-1000-700"` : cjk('sans', 700, Math.round(34 * sc));
        const lines = nameLines(x2, name, 272 * sc);
        // (a two-line name grows upward; the MASTER line stays put)
        lines.slice(0, -1).forEach((ln, j) => revealText(x2, ln, x, ny - (lines.length - 1 - j) * 38 * sc, { lt: k, stagger: 0.02, dur: 0.35, rise: 12, blur: 10, align: 'center', alpha: fo, fill: '#fff4dc', tracking: 1, glow: { color: 'rgba(255,170,70,0.5)', blur: 20 } }));
        revealText(x2, lines[lines.length - 1]!, x, ny, { lt: k, stagger: unk ? 0.05 : 0.02, dur: 0.35, rise: 12, blur: 10, align: 'center', alpha: fo * (unk ? 0.9 : 1), fill: unk ? '#cdd5ff' : '#fff4dc', tracking: unk ? 5 : 1, glow: { color: unk ? 'rgba(90,110,255,0.45)' : 'rgba(255,170,70,0.5)', blur: 20 } });
        x2.font = `500 ${Math.round(13 * sc)}px "Plex-500"`;
        revealText(x2, `MASTER · ${['I', 'II', 'III', 'IV', 'V', 'VI'][i]}`, x, ny + 34 * sc, { lt: k - 0.1, stagger: 0.02, dur: 0.3, rise: 0, blur: 0, align: 'center', alpha: 0.7 * fo, fill: unk ? 'rgba(150,165,230,1)' : 'rgba(232,176,74,1)', tracking: 4 });
      }
      if (lt < m0 + 0.3) {
        x2.font = cjk('serif', 600, 34);
        revealText(x2, '六位御主', W / 2, 250, { lt: lt - LINE0, stagger: 0.06, dur: 0.4, rise: 6, blur: 6, align: 'center', alpha: 1 - prog(lt, m0, m0 + 0.3), fill: '#efe3cc', tracking: 20 });
      }
    }
    // lockup on the bar; the date line and the call to action on the climax
    if (lt > LOCK) {
      const k = lt - LOCK;
      const dy = -190 * slateK(lt);
      x2.font = cjk('serif', 900, 150);
      revealText(x2, 'AI 圣杯战争', W / 2, 520 + dy, {
        lt: k, stagger: 0.05, dur: 0.7, rise: 16, blur: 18, align: 'center', tracking: 26,
        fill: (a, y) => { const g = x2.createLinearGradient(0, y - 130, 0, y + 10); g.addColorStop(0, '#fff7e6'); g.addColorStop(0.55, '#f2cf86'); g.addColorStop(1, '#c98a2c'); return g; },
        glow: { color: 'rgba(255,110,50,0.45)', blur: 36 },
      });
      drawRule(x2, W / 2, 572 + dy, 700, prog(k, 0.4, 1.0), 'rgba(232,176,74,0.7)');
      const kc = lt - CLIMAX;
      if (kc > 0) {
        x2.font = cjk('serif', 700, 52);
        revealText(x2, '第一届  ·  即将开战', W / 2, 660 + dy, { lt: kc, stagger: 0.03, dur: 0.35, rise: 8, blur: 8, align: 'center', fill: '#f3ead6', tracking: 14, glow: { color: 'rgba(0,0,0,0.8)', blur: 16 } });
        x2.font = cjk('sans', 500, 48);
        revealText(x2, '关注后续战报｜你看好谁？', W / 2, 1000, { lt: kc - 0.15, stagger: 0.025, dur: 0.35, rise: 6, blur: 6, align: 'center', fill: '#ffd98e', tracking: 6, glow: { color: 'rgba(0,0,0,0.85)', blur: 18 } });
      }
    }
    this.ctx.comp.draw(renderer, L.upload(), out);
    return {
      bloom: 0.8, bloomThreshold: 0.85, halation: 0.4, grain: 0.05, vignette: 0.6 + 0.2 * prog(lt, 1.5, 2.1), ca: 1.3,
      flash: 0.6 * (1 - prog(lt, 0, 0.3, ease.outQuad)) + pulse(lt, LOCK, 0.12) * 0.08 + pulse(lt, CLIMAX, 0.14) * 0.14,
      fade: prog(lt, END - 2.9, END - 0.1, ease.inQuad),
    };
  }
}
