# Promo copy of an Octopath replay: the cut-in names the AI (e.g. "Anthropic · 光"). Never edits the module itself.
import os
import json, sys, importlib.util, os
OD = os.environ.get('ARENA_ROOT', '/mnt/project-files/arena') + '/arena/games/octopath/'
spec = importlib.util.spec_from_file_location('ocv', OD + 'viewer.py'); V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
src, out = sys.argv[1:3]
R = json.load(open(src))
html = V.render(R)
a = "txt(c.who, tx, cy + ns * 0.42 + 34, 28, TEAM_COL[c.team], 'center');"
b = "txt(R.bots[c.team] + ' · ' + c.who, tx, cy + ns * 0.42 + 40, 36, TEAM_COL[c.team], 'center');"
assert a in html; html = html.replace(a, b)
open(out, 'w').write(html)
