#!/usr/bin/env node
// 把 CodeSide 回放 HTML 逐帧渲染成 PNG 序列（宣传片素材）。依赖 Node 和 playwright（含 Chromium）。
//
// 用法：
//   node arena/games/codeside/capture.js 回放.html 输出目录 [选项]
// 选项：
//   --w 3840 --h 2160      画面像素尺寸（默认 1920x1080；竖屏用 --w 1080 --h 1920）
//   --from 0 --to 400      起止 tick（默认整场）
//   --fps 60               输出帧率（默认 60）
//   --speed 1              播放速度，0.25 = 四倍慢动作（帧间用插值，不重复帧）
//   --hud 1                保留完整界面（比分条、单位卡片、控制条）；默认是只有游戏画面的干净模式
//   --labels 0             配合 --hud 1 使用：只去掉头顶名字和血条（干净模式本来就没有）
//   --view 20,15,2.5       镜头特写：以世界坐标 (20,15) 为中心放大 2.5 倍
// 合成视频：
//   ffmpeg -framerate 60 -i 输出目录/%05d.png -c:v libx264 -pix_fmt yuv420p -crf 16 out.mp4
"use strict";
const fs = require("fs");
const path = require("path");

function load() {
  for (const m of ["playwright", "playwright-core"]) { try { return require(m); } catch (e) { /* 试下一个 */ } }
  console.error("找不到 playwright：npm i playwright，或设置 NODE_PATH 指向已安装的位置");
  process.exit(1);
}

(async () => {
  const args = process.argv.slice(2), pos = [], opt = {};
  for (let k = 0; k < args.length; k++) {
    if (args[k].startsWith("--")) opt[args[k].slice(2)] = args[++k]; else pos.push(args[k]);
  }
  if (pos.length < 2) { console.error("用法：node capture.js 回放.html 输出目录 [--w 3840 --h 2160 --from 0 --to N --fps 60 --speed 1 --view cx,cy,zoom]"); process.exit(1); }
  const [html, out] = pos;
  const w = +(opt.w || 1920), h = +(opt.h || 1080), fps = +(opt.fps || 60), speed = +(opt.speed || 1);
  const q = new URLSearchParams({ w, h });
  if (opt.hud !== "1") q.set("clean", "1");
  if (opt.labels === "0") q.set("labels", "0");
  fs.mkdirSync(out, { recursive: true });

  const { chromium } = load();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: Math.min(w, 1920), height: Math.min(h, 1920) }, deviceScaleFactor: 1 });
  page.on("pageerror", e => console.error("页面错误：", e.message));
  await page.goto("file://" + path.resolve(html) + "?" + q.toString());
  await page.waitForFunction(() => window.arenaCapture && window.arenaCapture.ready);
  await page.evaluate(() => window.arenaCapture.ready);
  const info = await page.evaluate(() => ({ ticks: arenaCapture.ticks, tps: arenaCapture.fps }));
  if (opt.view) { const [cx, cy, z] = opt.view.split(",").map(Number); await page.evaluate(([a, b, c]) => arenaCapture.view(a, b, c), [cx, cy, z]); }
  const from = +(opt.from || 0), to = Math.min(info.ticks, opt.to != null ? +opt.to : info.ticks);
  const step = info.tps * speed / fps; // 每输出一帧前进多少 tick
  const total = Math.floor((to - from) / step) + 1;
  console.log(`${w}x${h}，tick ${from}→${to}，${fps} fps，速度 ${speed}×，共 ${total} 帧`);
  for (let n = 0; n < total; n++) {
    const p = from + n * step, tick = Math.floor(p), frac = p - tick;
    const data = await page.evaluate(([t, f]) => { arenaCapture.seek(t, f); arenaCapture.render(); return arenaCapture.png(); }, [tick, frac]);
    fs.writeFileSync(path.join(out, String(n).padStart(5, "0") + ".png"), Buffer.from(data.slice(data.indexOf(",") + 1), "base64"));
    if (n % 60 === 0) process.stdout.write(`\r${n + 1}/${total}`);
  }
  console.log(`\r${total}/${total} 完成 → ${out}`);
  console.log(`ffmpeg -framerate ${fps} -i ${path.join(out, "%05d.png")} -c:v libx264 -pix_fmt yuv420p -crf 16 out.mp4`);
  await browser.close();
})();
