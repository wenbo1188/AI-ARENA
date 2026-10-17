"""Build all participant-facing documents/archives from one rule source.

No organizer files are copied. Archives contain only local development tools;
official scheduling stays in the organizer checkout.
"""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'competition/events.json').read_text(encoding='utf-8'))


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8', newline='\n')


def build():
    rules = (ROOT / 'RULES.md').read_text(encoding='utf-8')
    for project, game in (('codeball','football'),('codeocto','octopath'),('codeside','codeside')):
        source = ROOT/project/'docs/接口源.md'
        content = source.read_text(encoding='utf-8').rstrip()+'\n'
        write(source, content)
        write(ROOT/project/'arena/games'/game/'DOC.md', content)
    for event_id, event in CATALOG['events'].items():
        project = ROOT / event['project']
        interface = (project / 'docs/接口源.md').read_text(encoding='utf-8')
        starter = (project / 'entry/bot.py').read_text(encoding='utf-8')
        config = {'rules_version': '2.0', 'event': event_id, **event}
        baseline = ('bots/octopath/quickstart_bot.py' if event['game'] == 'octopath' else
                    'bots/codeside/quickstart_bot.py' if event['game'] == 'codeside' else 'bots/quickstart_bot.py')
        config['baseline'] = baseline
        prompt = f'''你是「{event['title']}」的参赛 AI。请阅读完整参赛说明，在最多 120 分钟内自主开发、自测和修改策略。
仅需兼容本项引擎配置 `{event['stage']}`。最终交付 Python 标准库单文件 bot.py，以及一份自由格式的当前策略说明文档；说明不评分。
开发、自测、复用、故障和提交要求以随附完整参赛说明为准。不得编造测试结果。
'''
        full = (f'# {event["title"]} · 完整参赛说明 v2.0\n\n本项唯一配置：`{event["stage"]}`。'
                '无需兼容其他独立比赛配置。\n\n' + prompt + '\n' + rules
                + '\n\n# 本项游戏规则与通信接口\n\n' + interface
                + '\n\n# 起步策略\n\n```python\n' + starter.rstrip() + '\n```\n')
        materials = ROOT / 'participant-materials' / event_id
        write(materials / '完整参赛说明.md', full)
        write(materials / '完整参赛说明.txt', full)
        write(materials / '统一任务书.txt', prompt)
        write(materials / 'EVENT.json', json.dumps(config, ensure_ascii=False, indent=2) + '\n')
        files = {}
        for directory in ('arena', 'bots', 'entry', 'examples', 'licenses'):
            for p in (project / directory).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name != 'meta.json':
                    if directory == 'examples' and event['game'] == 'football' and event['stage'] not in p.parts and p.name != 'README.md':
                        continue
                    if directory == 'examples' and event['game'] == 'codeside' and p.name != 'README.md' and not p.name.startswith(event['stage']+'-'):
                        continue
                    files[str(p.relative_to(project)).replace('\\', '/')] = p.read_bytes()
        files['kit.py'] = (project / 'kit.py').read_bytes()
        files['EVENT.json'] = (materials / 'EVENT.json').read_bytes()
        files['完整参赛说明.md'] = full.encode('utf-8')
        files['完整参赛说明.txt'] = full.encode('utf-8')
        readme = f'''# {event['title']} · 选手开发包 v2.0

阅读完整参赛说明（MD / TXT 任选其一），修改 entry/bot.py。

```text
python kit.py match
python kit.py match --seat right
python kit.py check
```

check 默认使用本项完整长度、公开种子换边两局。需要短程调试可用 check --ticks 180（旅人用 --rounds 3），短程结果不是完整准入凭证。

比较策略修改前后的表现时，使用不同的输出目录保存结果：

```text
python kit.py match --out results/before
python kit.py match --out results/after
python kit.py check --out results/after
```

`--out` 同时适用于 match 和 check；相对路径以运行命令时的工作目录为准，含空格的路径请加引号。不指定时仍写入开发包的 results 目录。每局生成 HTML 回放和 JSON 对局记录，check 另生成 check.json；运行时会显示文件的完整路径。重复使用同一目录、命令、配置、种子和出场侧会覆盖同名结果，check.json 也会被该目录内的新检查覆盖；比较版本时请为每次测试使用不同目录。

最终只交 bot.py 和自由格式策略说明文档，不要求打包、自测报告或元信息。主办方独立复测。
这是本地开发工具，不提供完整禁网和跨选手文件隔离。正式比赛由主办方统一评测。
'''
        files['README.md'] = readme.encode('utf-8')
        checksums = ''.join(hashlib.sha256(v).hexdigest() + '  ' + k + '\n' for k, v in sorted(files.items()))
        files['MANIFEST.sha256'] = checksums.encode('utf-8')
        release = ROOT / 'releases' / f'{event_id}-Participant-Kit-v2.0.zip'
        release.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(release, 'w', zipfile.ZIP_DEFLATED) as z:
            for key, content in sorted(files.items()):
                info = zipfile.ZipInfo(key, (2026, 10, 17, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, content)
        write(release.with_suffix('.sha256'), hashlib.sha256(release.read_bytes()).hexdigest() + '  ' + release.name + '\n')
        print(event_id, len(files), release.stat().st_size)

    for project in ('codeball', 'codeocto', 'codeside'):
        base = ROOT / project
        candidates = [base/'kit.py', base/'VERSION.json', base/'COMPETITION.json', base/'LOCAL_EVENTS.json', base/'README.md']
        for directory in ('arena','bots','entry','examples','licenses','docs'):
            candidates.extend(p for p in (base/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
        write(base/'MANIFEST.sha256', ''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(base)).replace('\\','/')+'\n' for p in sorted(candidates)))


if __name__ == '__main__':
    build()
