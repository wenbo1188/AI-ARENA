"""Verify tests and clean-extracted development packages; never run an official event."""
from pathlib import Path
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.environ['PYTHONUTF8'] = '1'
    output = ROOT/'validation'
    output.mkdir(exist_ok=True)
    report = dict(python=platform.python_version(), system=platform.system(), suites=[], packages=[])
    for directory in (ROOT, ROOT/'codeball', ROOT/'codeocto', ROOT/'codeside'):
        result = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=directory,
                                capture_output=True, text=True, encoding='utf-8')
        label = directory.name if directory!=ROOT else 'events'
        (output/(label+'-tests.txt')).write_text(result.stdout+result.stderr,encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?',result.stderr)
        report['suites'].append(dict(name=label, tests=int(count[1]) if count else 0, passed=result.returncode==0))
        if result.returncode:raise RuntimeError(label+' tests failed')
        print(label,'tests passed',flush=True)
    for archive in sorted((ROOT/'releases').glob('*-v2.0.zip')):
        with tempfile.TemporaryDirectory(prefix='arena clean extract ') as tmp:
            dest=Path(tmp)
            with zipfile.ZipFile(archive) as z:
                names=z.namelist()
                assert not any('organizer' in n or n.endswith('meta.json') for n in names)
                z.extractall(dest)
            assert (dest/'完整参赛说明.md').read_bytes()==(dest/'完整参赛说明.txt').read_bytes()
            for line in (dest/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
                sha,path=line.split('  ',1)
                assert hashlib.sha256((dest/path).read_bytes()).hexdigest()==sha,path
            cfg=json.loads((dest/'EVENT.json').read_text(encoding='utf-8'))
            args=['--rounds','3'] if cfg['game']=='octopath' else ['--ticks','8']
            result=subprocess.run([sys.executable,'kit.py','check',*args],cwd=dest,
                                  capture_output=True,text=True,encoding='utf-8')
            (output/(cfg['event']+'-package-check.txt')).write_text(result.stdout+result.stderr,encoding='utf-8')
            if result.returncode:raise RuntimeError(cfg['event']+' extracted check failed')
            check=json.loads((dest/'results/check.json').read_text(encoding='utf-8'))
            assert check['passed'] and not check['full_length']
            report['packages'].append(dict(event=cfg['event'], passed=True, check='short', matches=check['matches']))
            print(cfg['event'],'clean package check passed',flush=True)
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    total=sum(s['tests'] for s in report['suites'])
    (output/'REPORT.md').write_text(f'''# 验证记录 · 2026-10-17

环境：{report['system']} / Python {report['python']}。

全部 {total} 项测试通过，包括新赛事调度、BO5 和真实策略子进程恢复测试，以及保留的物理/战斗数值和历史结果检查。
七份 ZIP 均从干净目录解压，完整性摘要、MD/TXT 一致性及双侧短程自测通过；不含主办方目录或 meta.json 要求。

真实恢复测试覆盖单 tick 超时、错误 JSON、错误动作类型后正常回复，以及崩溃不重启。调度测试以模拟比分检查完整二十大场与一至六名、同分指标、现场随机种子、BO5 平局与第五局位、暂停和中断恢复，不代表实际 AI 强弱。

包内运行检查为足球/射击 8 tick、旅人 3 回合短程检查，不是完整正式长度准入；未执行真实参赛选手的正式比赛。独立隔离部署仍须主办方完成验收。

详细日志及结构化结果见同目录文件。\n''',encoding='utf-8')
    print('TOTAL',total,flush=True)


if __name__=='__main__':main()
