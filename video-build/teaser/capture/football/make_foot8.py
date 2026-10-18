# Copy the football demo replay keeping only the five masters' brands in the stadium:
# ad boards and LED screens, the 8 hologram projectors (4 mascots, twice) and the air dancers on the stands.
# MiniMax has no mascot in the viewer, so it appears on the boards only.
# python3 make_foot8.py <replay.html> <out.html>
import re, sys
src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
def sub(pat, rep, what, flags=0):
    global s
    s, k = re.subn(pat, rep, s, flags=flags)
    print(what, 'ok' if k else 'NOT FOUND')
for name in ['Google DeepMind', 'Meta AI', 'Qwen 千问', 'Kimi', '豆包']:
    sub(r"\n\s*\{ t: '" + re.escape(name) + r"',[^\n]*\},", '', 'board ' + name)
# holograms: atlas cells CLAUDE 0, DEEPSEEK 1, CHATGPT 3, GLM 6 at both ends
sub(r"const order = \[0, 1, 2, 3, 4, 5, 6, 7\];", "const order = [0, 3, 1, 6, 6, 1, 3, 0];", 'holo order')
sub(r"(const nameTex = canvasTex\(1024, 512, \(c, w, h\) => \{\n\s*c\.fillStyle = '#060b16'; c\.fillRect\(0, 0, w, h\);\n\s*)HOLO\.forEach",
    r"\1order.map(k => HOLO[k]).forEach", 'holo name bands')
# air dancers: 4 per long side (Claude, DeepSeek, ChatGPT, GLM), spread wider
sub(r"for \(let k = 0; k < 8; k\+\+\) \{\n(\s*)const z = sx \* \(k - 3\.5\) \* 11\.5;",
    r"for (let k = 0; k < 4; k++) {\n\1const z = sx * (k - 1.5) * 19;", 'dancer slots')
sub(r"MASCOTS\[k\]\(\); bases\.push", "MASCOTS[[0, 1, 3, 6][k]](); bases.push", 'dancer mascots')
open(out, 'w', encoding='utf-8').write(s)
