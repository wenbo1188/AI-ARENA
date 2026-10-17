"""Official seven-event entry point. Participants submit code + a free-form document."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from competition.tournament import Tournament, Paused, digest, write_json

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / 'competition/events.json').read_text(encoding='utf-8'))


def implementation_files(project):
    files = [ROOT / 'event.py', ROOT / 'event_worker.py', ROOT / 'RULES.md']
    files += list((ROOT / 'competition').glob('*.py')) + list((ROOT / 'competition').glob('*.json'))
    for p in (ROOT / project / 'arena').rglob('*'):
        if p.is_file() and p.suffix in ('.py', '.json', '.txt', '.md'):
            files.append(p)
    files += list((ROOT / project / 'bots').rglob('*.py'))
    return {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p) for p in files}


def verify(state):
    for rel, sha in state['frozen']['implementation'].items():
        if digest(ROOT / rel) != sha:
            raise ValueError(f'规则或评测器已变更，停止赛事：{rel}')
    for n, entry in state['participants'].items():
        if digest(entry['bot']) != entry['bot_sha256'] or digest(entry['description']) != entry['description_sha256']:
            raise ValueError(f'冻结提交已变更：{n}')
    if state['mode'] == 'official':
        deployment = state['frozen']['deployment']
        if platform.system() != 'Windows' or platform.python_version() != '3.12.6':
            raise ValueError('正式比赛须使用 Windows / Python 3.12.6')
        if not (deployment.get('isolation_verified') is True and deployment.get('hardware')
                and deployment.get('bot_command') and deployment.get('machine_id')):
            raise ValueError('正式部署缺少验收、硬件、机器编号或独立隔离启动命令')
        if deployment['machine_id'] != platform.node():
            raise ValueError('本机与已冻结评测机器不一致')
        command = deployment['bot_command']
        if not isinstance(command, list) or not all(isinstance(x, str) for x in command) or not any('{bot}' in x for x in command):
            raise ValueError('隔离启动命令须为含 {bot} 的字符串数组')
        if deployment.get('python') != '3.12.6' or deployment.get('os') != 'Windows':
            raise ValueError('隔离环境须验收为 Windows / Python 3.12.6')
        if deployment.get('parallel_matches') != 1:
            raise ValueError('正式比赛每次只能进行一场')


def adapter(state):
    def play(names, seed, dest):
        verify(state)
        dest = Path(dest).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        request, response = dest.with_suffix('.job.json'), dest.with_suffix('.result.json')
        entries = []
        for n in names:
            if n == '__public_baseline__':
                suffix = 'octopath/quickstart_bot.py' if state['event']['game'] == 'octopath' else (
                    'codeside/quickstart_bot.py' if state['event']['game'] == 'codeside' else 'quickstart_bot.py')
                path = ROOT / state['event']['project'] / 'bots' / suffix
                entries.append(dict(name=n, bot=str(path)))
            else:
                entries.append(dict(name=n, bot=state['participants'][n]['bot']))
        if response.exists():
            # A worker may have completed just before the scheduler was interrupted.
            # Recover that durable result instead of replaying a valid game.
            result = json.loads(response.read_text(encoding='utf-8'))
            expected = {'seed':seed, 'bots':names, 'event':state['event']}
            if result.get('fixture') != expected:
                raise ValueError('已保存小局结果与待赛记录不一致')
            return result
        write_json(request, dict(project=str(ROOT / state['event']['project']), event=state['event'],
                                bots=entries, seed=seed, replay=str(dest), result=str(response),
                                bot_command=state['frozen']['deployment'].get('bot_command')))
        completed = subprocess.run([sys.executable, str(ROOT / 'event_worker.py'), str(request)],
                                   capture_output=True, text=True, encoding='utf-8', errors='replace',
                                   env={**os.environ, 'PYTHONUTF8':'1'})
        if completed.returncode != 0:
            raise RuntimeError('裁判执行异常；原种子保留，修复后恢复：' + completed.stderr[-3000:])
        return json.loads(response.read_text(encoding='utf-8'))
    return play


def create(args):
    raw = json.loads(args.entries.read_text(encoding='utf-8-sig'))
    circle_names = list(raw)
    from competition.tournament import circle_rounds
    circle_rounds(circle_names)
    prepared = {}
    for i, (name, entry) in enumerate(raw.items()):
        if not name.strip() or name == '__public_baseline__':
            raise ValueError('选手名称不合法')
        source = (args.entries.parent / entry['bot']).resolve(strict=True)
        description = (args.entries.parent / entry['description']).resolve(strict=True)
        if source.suffix != '.py':
            raise ValueError('策略须为 Python 单文件')
        if description == source:
            raise ValueError('须另交一份策略说明文档，内容格式不限')
        prepared[name] = (source, description)
    folder = args.out.resolve()
    if folder.exists() and any(folder.iterdir()):
        raise ValueError('创建赛事需要空目录')
    deployment = json.loads(args.deployment.read_text(encoding='utf-8')) if args.deployment else {}
    event = dict(CATALOG['events'][args.event], id=args.event)
    frozen = dict(implementation=implementation_files(event['project']), deployment=deployment,
                  host=platform.node(), python=platform.python_version())
    participants = {}
    for i, (name, (source, description)) in enumerate(prepared.items()):
        dest = folder / 'participants' / f'AI-{i+1:02d}'
        dest.mkdir(parents=True)
        bot, doc = dest / 'bot.py', dest / ('strategy' + description.suffix)
        shutil.copyfile(source, bot)
        shutil.copyfile(description, doc)
        participants[name] = dict(bot=str(bot), description=str(doc), bot_sha256=digest(bot), description_sha256=digest(doc))
    state = Tournament.create(folder, event, participants, frozen, 'official' if args.official else 'development')
    verify(state)
    print('已冻结六份提交；未生成任何正式种子。下一步运行 qualify。')


def qualifying(stats):
    return stats.get('initialized') is True and stats.get('accepted_turns', 0) > 0 and not stats.get('crashed', True)


def qualify(folder, state):
    verify(state)
    play = adapter(state)
    for index, n in enumerate(state['participants']):
        report = state['qualification'].setdefault(n, dict(games=[]))
        for seat in range(len(report['games']), 2):
            names = [n, '__public_baseline__'] if seat == 0 else ['__public_baseline__', n]
            result = play(names, 12, folder / 'qualification' / f'AI-{index+1:02d}-{seat}')
            if not qualifying(result['stats'][1-seat]):
                raise RuntimeError('公开基准或评测环境异常；不能据此判定选手失败')
            report['games'].append(dict(seat=seat, seed=12, **result))
            write_json(folder / 'event.json', state)
        report['passed'] = all(qualifying(g['stats'][g['seat']]) for g in report['games'])
        write_json(folder / 'event.json', state)
        print(f'{n}: ' + ('通过' if report['passed'] else '未通过准入（不进入对战排名）'), flush=True)


@contextlib.contextmanager
def event_lock(folder):
    # OS-owned lock is released on crash; resume does not require deleting a stale lock.
    path = folder / '.event.lock'
    with path.open('a+b') as handle:
        handle.seek(0)
        handle.write(b'0')
        handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('该赛事已有运行进程') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    p = argparse.ArgumentParser(description='七项独立比赛：六人积分赛 + BO5 名次赛')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    init = sub.add_parser('init')
    init.add_argument('--event', choices=CATALOG['events'], required=True)
    init.add_argument('--entries', type=Path, required=True)
    init.add_argument('--out', type=Path, required=True)
    init.add_argument('--official', action='store_true')
    init.add_argument('--deployment', type=Path)
    for name in ('qualify', 'run', 'status'):
        sp = sub.add_parser(name)
        sp.add_argument('folder', type=Path)
        if name == 'run':
            sp.add_argument('--max-games', type=int, help='本次执行的小局上限；仅暂停，不改判平局或胜负')
    args = p.parse_args()
    try:
        if args.command == 'list':
            for key, event in CATALOG['events'].items():
                print(key, event['title'])
        elif args.command == 'init':
            create(args)
        else:
            folder = args.folder.resolve()
            with event_lock(folder):
                state = json.loads((folder / 'event.json').read_text(encoding='utf-8'))
                verify(state)
                if args.command == 'status':
                    print(json.dumps({k: state.get(k) for k in ('event', 'mode', 'status', 'qualification', 'regular_order', 'ranking')}, ensure_ascii=False, indent=2))
                elif args.command == 'qualify':
                    qualify(folder, state)
                else:
                    if args.max_games is not None and args.max_games < 1:
                        raise ValueError('max-games 必须为正整数')
                    if any(not state['qualification'].get(n, {}).get('passed') for n in state['participants']):
                        raise ValueError('须先完成六名选手准入；不足六名不得套用六人赛制')
                    event = Tournament(folder, adapter(state), lambda: verify(state), args.max_games)
                    print(event.run())
        return 0
    except Paused as exc:
        print('赛事暂停：', exc)
        return 2
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print('停止：', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
