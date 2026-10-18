// Fallback exporter: renders frames with __pdoom.still() + png() in N pages (each takes a contiguous range),
// pipes PNGs into one ffmpeg per range, then concatenates the segments. Slower than stream(), but robust here.
//   bun scripts/export2.ts --url http://localhost:5401 --from 0 --to 60 --fps 30 --workers 2 --samples 1 --out out/x.mp4
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync, rmSync } from 'fs';
import path from 'path';
const argv = process.argv.slice(2);
const opt = (k: string, d?: string) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const url = opt('url', 'http://localhost:5401')!, from = +opt('from', '0')!, to = +opt('to', '60')!, fps = +opt('fps', '30')!;
const workers = +opt('workers', '2')!, samples = +opt('samples', '1')!, out = opt('out', 'out/film.mp4')!;
const crf = opt('crf', '16')!, preset = opt('preset', 'medium')!;
const scale = opt('scale', '1')!; // e.g. 0.3333 for a 640x360 draft
const f0 = Math.round(from * fps), f1 = Math.round(to * fps), total = f1 - f0;
const segDir = path.join(path.dirname(out), `.seg-${process.pid}`);
mkdirSync(segDir, { recursive: true });
let done = 0; const t0 = performance.now();
async function run(k: number, a: number, b: number) {
  const seg = path.join(segDir, `${k}.mp4`);
  const ff = Bun.spawn(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'png', '-r', String(fps), '-i', 'pipe:0',
    '-vf', 'scale=out_color_matrix=bt709,setparams=color_primaries=bt709:color_trc=bt709', '-c:v', 'libx264', '-preset', preset, '-crf', crf,
    '-pix_fmt', 'yuv420p', '-tune', 'grain', '-x264-params', 'aq-mode=3', seg], { stdin: 'pipe', stderr: 'inherit' });
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto(`${url}/?export=1&scale=${scale}`);
  await page.waitForFunction(() => (window as any).__pdoom?.ready || (window as any).__pdoom?.error, null, { timeout: 180000 });
  const err = await page.evaluate(() => (window as any).__pdoom.error);
  if (err) throw new Error(err);
  for (let n = a; n < b; n++) {
    const b64: string = await page.evaluate(async ([t, s]) => { const p = (window as any).__pdoom; await p.still(t, s); return p.png(); }, [n / fps, samples] as const);
    ff.stdin.write(Buffer.from(b64, 'base64')); await ff.stdin.flush();
    done++;
    if (done % 15 === 0) { const el = (performance.now() - t0) / 1000; process.stdout.write(`\r${done}/${total}  ${(done / el).toFixed(2)} fps  eta ${((total - done) / (done / el) / 60).toFixed(1)} min   `); }
  }
  await browser.close();
  ff.stdin.end();
  if ((await ff.exited) !== 0) throw new Error(`ffmpeg failed on segment ${k}`);
  return seg;
}
const per = Math.ceil(total / workers);
const segs = await Promise.all(Array.from({ length: workers }, (_, k) => run(k, f0 + k * per, Math.min(f1, f0 + (k + 1) * per))));
writeFileSync(path.join(segDir, 'list.txt'), segs.map((s) => `file '${path.resolve(s)}'`).join('\n'));
const audio = opt('audio');
const cat = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(segDir, 'list.txt')];
if (audio) cat.push('-ss', String(from), '-t', String(to - from), '-i', audio, '-c:a', 'aac', '-b:a', '320k', '-shortest');
cat.push('-c:v', 'copy', '-movflags', '+faststart', out);
if ((await Bun.spawn(cat, { stderr: 'inherit' }).exited) !== 0) throw new Error('concat failed');
rmSync(segDir, { recursive: true, force: true });
console.log(`\nwrote ${out}: ${total} frames in ${((performance.now() - t0) / 60000).toFixed(1)} min`);
