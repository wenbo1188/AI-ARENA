"""Participant local match/check tools. Submit bot.py + a free-form document."""
from pathlib import Path
import argparse
import json
import sys

from arena.bot import BotSpec
from arena.runner import run_match, save_replay

ROOT = Path(__file__).resolve().parent


def spec(path, name):
    path = Path(path).resolve(strict=True)
    return BotSpec(name, [sys.executable, '-u', str(path)], str(path.parent))


def settings(args):
    local = ROOT / 'EVENT.json'
    if local.exists():
        return json.loads(local.read_text(encoding='utf-8'))
    # Source checkout supports all configurations; generated kits only their own.
    cfg = json.loads((ROOT / 'LOCAL_EVENTS.json').read_text(encoding='utf-8'))
    return cfg[args.stage or next(iter(cfg))]


def main():
    p = argparse.ArgumentParser(description='本项本地试跑和完整自测，无强制打包步骤')
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('match', 'check'):
        sp = sub.add_parser(command)
        sp.add_argument('--bot', type=Path, default=ROOT/'entry/bot.py')
        sp.add_argument('--stage', choices=('round1', 'round2', 'finals', 'single'))
        sp.add_argument('--ticks', type=int)
        sp.add_argument('--rounds', type=int)
        if command == 'match':
            sp.add_argument('--opponent', type=Path)
            sp.add_argument('--seed', type=int, default=12)
            sp.add_argument('--seat', choices=('left', 'right'), default='left')
    args = p.parse_args()
    try:
        cfg = settings(args)
        if args.stage and args.stage != cfg['stage']:
            raise ValueError('开发包仅支持本项配置')
        compile(args.bot.read_text(encoding='utf-8-sig'), str(args.bot), 'exec')
        options = ({'team_size':4, 'pick_mode':'blind', 'max_rounds': args.rounds or 30}
                   if cfg['game'] == 'octopath' else {'stage': cfg['stage'], 'ticks': args.ticks or cfg['ticks']})
        if args.ticks is not None and (cfg['game']=='octopath' or args.ticks < 1):
            raise ValueError('ticks 仅用于足球/射击，且须为正数')
        if args.rounds is not None and (cfg['game']!='octopath' or args.rounds < 1):
            raise ValueError('rounds 仅用于旅人，且须为正数')
        candidate = spec(args.bot, 'candidate')
        baseline = spec(getattr(args, 'opponent', None) or ROOT/cfg['baseline'], 'baseline')
        results = []
        seats = (0, 1) if args.command == 'check' else (int(args.seat == 'right'),)
        for seat in seats:
            bots = [candidate, baseline] if seat == 0 else [baseline, candidate]
            seed = 12 if args.command == 'check' else args.seed
            r = run_match(cfg['game'], bots, seed=seed, **options)
            record = dict(seat=seat, seed=seed, scores=r.scores, ticks=r.ticks, stats=r.stats)
            results.append(record)
            base = ROOT / 'results' / f'{args.command}-{cfg["stage"]}-{seed}-{seat}'
            save_replay(r, str(base)+'.json', str(base)+'.html')
            print(json.dumps(record, ensure_ascii=False))
        if args.command == 'check':
            passed = all(g['stats'][g['seat']].get('initialized')
                         and g['stats'][g['seat']].get('accepted_turns',0)>0
                         and not g['stats'][g['seat']]['crashed'] for g in results)
            baseline_ok = all(g['stats'][1-g['seat']].get('initialized')
                              and g['stats'][1-g['seat']].get('accepted_turns',0)>0
                              and not g['stats'][1-g['seat']]['crashed'] for g in results)
            full = (options.get('max_rounds')==30 if cfg['game']=='octopath' else options['ticks']==cfg['ticks'])
            report = dict(passed=bool(passed and baseline_ok), full_length=full, matches=results)
            (ROOT/'results/check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(('通过' if report['passed'] else '未通过') + ('（完整本地检查）' if full else '（短程调试，不是完整准入）'))
            return 0 if report['passed'] else 1
        return 0
    except (OSError, ValueError, KeyError, SyntaxError) as exc:
        print('失败：', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
