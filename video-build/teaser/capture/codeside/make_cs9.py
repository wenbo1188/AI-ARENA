# Promo copy of a CodeSide replay: vendor names on the units, labels kept in ?clean=1. Never edits the module itself.
import os
import json, sys, importlib.util
CS = os.environ.get('ARENA_ROOT', '/mnt/project-files/arena') + '/arena/games/codeside/'
spec = importlib.util.spec_from_file_location('csv', CS + 'viewer.py'); V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
src, out, a, b = sys.argv[1:5]
R = json.load(open(src)); R['bots'] = [a, b]
html = V.render(R)
for x, y in [('LABELS = !CLEAN && QS.get("labels") !== "0"', 'LABELS = QS.get("labels") !== "0"'),
             ('const name = R.bots[team] + " / " + id,', 'const name = R.bots[team],')]:
    assert x in html, x; html = html.replace(x, y)
open(out, 'w').write(html)
