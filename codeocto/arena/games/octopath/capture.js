// 把八方旅人对决回放逐帧渲染成 PNG 序列（宣传片素材用）。
// 用法：node capture.js <回放.html> <输出目录> [--w 3840 --h 2160 --fps 60 --from 1 --to 45 --zoom 1 --focus 0,2 --ui]
//   --from/--to  起止步（含），默认整场
//   --zoom/--focus  推近倍数和对准的旅人（队伍,序号），不给 focus 就对准画面中央
//   --ui  保留界面（默认是 ?clean=1 的无界面画面）
//   --global  帧号按整场编号（第 1 步第 0 帧 = 0），几个进程分段并行导出到同一目录时用
// 输出 frame_000000.png …，再用 ffmpeg 合成：
//   ffmpeg -framerate 60 -i out/frame_%06d.png -c:v libx264 -pix_fmt yuv420p -crf 16 out.mp4
const path = require('path'), fs = require('fs');
const { chromium } = require(require('child_process').execSync('npm root -g', { cwd: '/tmp' }).toString().trim() + '/playwright');

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const VAL = new Set(['--w', '--h', '--fps', '--from', '--to', '--zoom', '--focus']);
const [file, outDir] = argv.filter((a, i) => !a.startsWith('--') && !VAL.has(argv[i - 1]));
if (!file || !outDir) { console.error('用法: node capture.js <回放.html> <输出目录> [--w 3840 --h 2160 --fps 60 --from 1 --to N --zoom 1 --focus 0,2 --ui]'); process.exit(1); }
const w = +opt('w', 1920), h = +opt('h', 1080), fps = +opt('fps', 60), zoom = +opt('zoom', 1), focus = opt('focus', null);
fs.mkdirSync(outDir, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const errs = []; page.on('pageerror', e => errs.push(String(e)));
  const q = `?w=${w}&h=${h}&fps=${fps}` + (argv.includes('--ui') ? '' : '&clean=1');
  await page.goto('file://' + path.resolve(file) + q);
  await page.evaluate(() => arenaCapture.ready);
  const ticks = await page.evaluate(() => arenaCapture.ticks);
  const from = Math.max(0, +opt('from', 1)), to = Math.min(ticks - 1, +opt('to', ticks - 1));
  let n = argv.includes('--global') ? await page.evaluate(from => { let s = 0; for (let t = 1; t < from; t++) s += arenaCapture.frames(t); return s; }, from) : 0;
  const n0 = n, t0 = Date.now();
  for (let t = from; t <= to; t++) {
    const frames = await page.evaluate(t => arenaCapture.frames(t), t);
    for (let k = 0; k < frames; k++) {
      await page.evaluate(([t, f, zoom, focus]) => {
        const C = arenaCapture;
        C.seek(t, f);
        if (focus) { const u = C.unit(...focus); C.view(zoom, u.x, u.y); } else C.view(zoom);
        C.render();
      }, [t, k / frames, zoom, focus ? focus.split(',').map(Number) : null]);
      await page.screenshot({ path: path.join(outDir, `frame_${String(n++).padStart(6, '0')}.png`) });
    }
    process.stdout.write(`\r第 ${t}/${to} 步，已输出 ${n - n0} 帧（${((Date.now() - t0) / 1000).toFixed(0)} 秒）`);
  }
  console.log(`\n完成：${n - n0} 帧（帧号 ${n0}~${n - 1}）→ ${outDir}` + (errs.length ? `\n页面错误：${errs.join('; ')}` : ''));
  await browser.close();
})();
