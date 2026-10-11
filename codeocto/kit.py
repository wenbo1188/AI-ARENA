"""Local participant tools. Only execute trusted strategy files."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import sys
import zipfile

from arena.bot import BotSpec
from arena.runner import run_match, save_replay

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT/'COMPETITION.json').read_text(encoding='utf-8'))
GAME = CFG['game']

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def spec(path, name):
    p = Path(path).resolve(strict=True)
    return BotSpec(name, [sys.executable, '-u', str(p)], str(p.parent))

def options(stage, ticks=None):
    if GAME == 'football':
        return {'stage': stage, 'ticks': ticks or 20000}
    return {'team_size': 4, 'pick_mode': 'blind', 'max_rounds': 30}

def check(args):
    bot = args.bot.resolve(strict=True)
    compile(bot.read_text(encoding='utf-8-sig'), str(bot), 'exec')
    report = {'kit_version': CFG['version'], 'game': GAME, 'bot_sha256': sha(bot),
              'competition_sha256': sha(ROOT/'COMPETITION.json'), 'ticks_limit': args.ticks,
              'matches': [], 'problems': []}
    for i, stage in enumerate(CFG['stages']):
        for seat in (0, 1):
            bots = [spec(ROOT/CFG['baseline'], 'baseline'), spec(bot, 'candidate')]
            if seat == 0: bots.reverse()
            result = run_match(GAME, bots, seed=CFG['practice_seeds'][i % 3], **options(stage,args.ticks))
            row = {'stage': stage, 'seat': seat, 'ticks': result.ticks, 'scores': result.scores, 'stats': result.stats}
            report['matches'].append(row)
            for st in result.stats:
                if st['crashed'] or st['timeouts'] or st['invalid_lines']:
                    report['problems'].append(f"{stage}/{seat}/{st['name']}: {st}")
            print(f"{stage} seat={seat} score={result.scores} ticks={result.ticks}", flush=True)
    report['passed'] = not report['problems'] and len(report['matches']) == 2*len(CFG['stages'])
    dump(ROOT/'results/check.json', report)
    print('PASS' if report['passed'] else 'FAIL: results/check.json')
    return int(not report['passed'])

def match(args):
    bots = [spec(args.bot,'candidate'), spec(args.opponent,'baseline')]
    if args.seat == 'right': bots.reverse()
    r = run_match(GAME,bots,seed=args.seed,**options(args.stage,args.ticks))
    dest=ROOT/'results'/f'{args.stage}-{args.seed}-{args.seat}'
    save_replay(r,str(dest)+'.json',str(dest)+'.html')
    print(json.dumps({'scores':r.scores,'ticks':r.ticks,'stats':r.stats},ensure_ascii=False,indent=2))
    print('Replay:',str(dest)+'.html')
    return int(any(s['crashed'] or s['timeouts'] or s['invalid_lines'] for s in r.stats))

def pack(args):
    bot=args.bot.resolve(strict=True)
    meta=json.loads(args.meta.read_text(encoding='utf-8-sig'))
    name=meta.get('participant_name','').strip()
    if not name or name=='请填写选手名称': raise ValueError('请填写 entry/meta.json 的 participant_name')
    report=json.loads((ROOT/'results/check.json').read_text(encoding='utf-8'))
    if (not report.get('passed') or report.get('kit_version')!=CFG['version'] or report.get('game')!=GAME
        or report.get('competition_sha256')!=sha(ROOT/'COMPETITION.json') or report.get('bot_sha256')!=sha(bot)
        or (GAME=='football' and report.get('ticks_limit',0)<180)):
        raise ValueError('请使用当前版本、当前代码重新完成自测')
    safe=re.sub(r'[^\w-]+','_',name)[:40]
    dest=ROOT/'dist'/f'{safe}-{sha(bot)[:12]}.zip';dest.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('bot.py',bot.read_bytes())
        z.writestr('meta.json',json.dumps({**meta,'game':GAME,'kit_version':CFG['version'],'bot_sha256':sha(bot)},ensure_ascii=False,indent=2))
        z.writestr('selfcheck.json',json.dumps(report,ensure_ascii=False,indent=2))
        z.writestr('SHA256.txt',sha(bot)+'  bot.py\n')
    print(dest)
    return 0

def fixtures(names, base_seed):
    """Symmetric football fixtures; five alternating Octopath fixtures, no early exit."""
    names=sorted(names)
    if len(names)<2 or len(set(names))!=len(names): raise ValueError('至少两名选手，名称不得重复')
    out=[]
    for stage_index,stage in enumerate(CFG['stages']):
        for a,b in itertools.combinations(range(len(names)),2):
            # Across the roster, a circular orientation balances the extra seat in odd-length series.
            extra_left = (b-a) <= (len(names)-1)//2
            for k in range(CFG['matches_per_pair_per_stage']):
                flip = (k%2==1) ^ (not extra_left)
                pair=[names[a],names[b]]
                if flip: pair.reverse()
                seed=base_seed+stage_index*100000+(k//2 if GAME=='football' else k)
                out.append({'match':len(out),'stage':stage,'seed':seed,'bots':pair})
    return out

def tournament(args):
    from standings import aggregate, write_results
    entries=json.loads(args.entries.read_text(encoding='utf-8-sig'))
    if not isinstance(entries,dict): raise ValueError('选手清单须为 {名称:bot.py路径}')
    paths={n:(args.entries.parent/p).resolve(strict=True) for n,p in entries.items()}
    manifest={'game':GAME,'version':CFG['version'],'seed':args.seed,'competition_sha256':sha(ROOT/'COMPETITION.json'),
              'participants':{n:{'bot_sha256':sha(p)} for n,p in paths.items()},'fixtures':fixtures(list(paths),args.seed)}
    out=args.out.resolve()
    if (out/'schedule.json').exists(): raise ValueError('输出目录已有赛程，请使用新目录以免覆盖赛事')
    dump(out/'schedule.json',manifest)
    if args.schedule_only:
        print(out/'schedule.json');return 0
    results=[]
    for f in manifest['fixtures']:
        if any(sha(paths[n])!=manifest['participants'][n]['bot_sha256'] for n in f['bots']):
            raise ValueError('参赛代码在比赛期间发生变化，停止赛事')
        r=run_match(GAME,[spec(paths[n],n) for n in f['bots']],seed=f['seed'],**options(f['stage']))
        save_replay(r,str(out/'replays'/f"{f['match']:05d}.json"),str(out/'replays'/f"{f['match']:05d}.html"))
        results.append({**f,'scores':r.scores,'stats':r.stats})
        dump(out/'matches.json',results)
        print(f"{len(results)}/{len(manifest['fixtures'])}: {f['bots']} {r.scores}",flush=True)
    write_results(aggregate(manifest,results),out)
    return 0

def main():
    p=argparse.ArgumentParser(description=CFG['title']+' 本地工具')
    sub=p.add_subparsers(dest='command',required=True)
    for command in ('match','check','pack'):
        q=sub.add_parser(command)
        q.add_argument('--bot',type=Path,default=ROOT/'entry/bot.py')
        if command=='pack': q.add_argument('--meta',type=Path,default=ROOT/'entry/meta.json')
        else: q.add_argument('--ticks',type=int,default=20000 if command=='match' else 180,
                             help='足球本地测试长度；八方始终使用30回合')
        if command=='match':
            q.add_argument('--stage',choices=CFG['stages'],default=CFG['stages'][0])
            q.add_argument('--seat',choices=['left','right'],default='left')
            q.add_argument('--seed',type=int,default=12)
            q.add_argument('--opponent',type=Path,default=ROOT/CFG['baseline'])
    q=sub.add_parser('tournament');q.add_argument('entries',type=Path)
    q.add_argument('--seed',type=int,required=True);q.add_argument('--out',type=Path,required=True)
    q.add_argument('--schedule-only',action='store_true')
    a=p.parse_args()
    if hasattr(a,"ticks") and a.ticks <= 0: p.error("ticks必须为正整数")
    try: return globals()[a.command](a)
    except (OSError,ValueError,SyntaxError) as e: print('ERROR:',e);return 1

if __name__=='__main__': raise SystemExit(main())
