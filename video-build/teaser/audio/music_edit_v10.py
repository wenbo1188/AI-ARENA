# v10 music (mrwang 2026-10-11): ONE continuous take, no splices. The track plays straight on from bar 4
# (film 0 = track 7.852 s) past the 60 s mark and fades out over the last phrase, ending on a phrase boundary.
#   python3 edit_v10c.py <gain dB> <end s> <fade bars> <out name>
#   end = film time in seconds where the fade reaches silence; fade in bars
#   Phrase boundaries after 60 s (chroma novelty): track bar 39 (film 65.62), 43 (film 73.12), 47 (film 80.62, section end)
import numpy as np, subprocess, sys
SR = 48000; BAR = 1.875; START = 7.852
g = float(sys.argv[1]); end_t = float(sys.argv[2]); fade = float(sys.argv[3]) * BAR
x = np.fromfile('octo.f32', np.float32).reshape(-1, 2)
a = int(round(START * SR)); out = x[a:a + int(round(end_t * SR))].copy()
k = int(0.003 * SR); out[:k] *= np.linspace(0, 1, k)[:, None]
f0 = int(round((end_t - fade) * SR)); n = len(out) - f0
out[f0:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, n)))[:, None] ** 1.3   # smooth S-curve to silence
out *= 10 ** (g / 20)
print('len', len(out) / SR, 'peak dBFS', 20 * np.log10(np.abs(out).max()))
name = sys.argv[4]
out.astype(np.float32).tofile(name + '.f32')
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', name + '.f32', '-c:a', 'pcm_s24le', name + '.wav'], check=True)
