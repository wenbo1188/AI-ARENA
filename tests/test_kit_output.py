"""Exercise local output selection through the real CLI and strategy processes."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KitOutputTests(unittest.TestCase):
    def test_separate_runs_preserve_previous_results(self):
        for project, stage, length in (
            ('codeball', 'round1', ['--ticks', '2']),
            ('codeside', 'round1', ['--ticks', '2']),
            ('codeocto', 'single', ['--rounds', '1']),
        ):
            with self.subTest(project=project), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                kit = ROOT / project / 'kit.py'

                def run(command, out):
                    result = subprocess.run(
                        [sys.executable, str(kit), command, '--stage', stage,
                         *length, '--out', out], cwd=cwd,
                        capture_output=True, text=True, encoding='utf-8',
                        env={**os.environ, 'PYTHONUTF8': '1'}, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    return result

                before = cwd / 'runs' / 'before version'
                run('match', 'runs/before version')
                original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in before.iterdir()}
                self.assertEqual(set(original), {
                    f'match-{stage}-12-0.html', f'match-{stage}-12-0.json'})

                after = cwd / 'runs' / 'after version'
                match = run('match', str(after))
                self.assertIn(str(after / f'match-{stage}-12-0.html'), match.stderr)
                check = run('check', str(after))
                report = json.loads((after / 'check.json').read_text(encoding='utf-8'))
                self.assertTrue(report['passed'])
                self.assertFalse(report['full_length'])
                self.assertEqual({g['seat'] for g in report['matches']}, {0, 1})
                self.assertIn(str(after / 'check.json'), check.stderr)
                for seat in (0, 1):
                    for suffix in ('html', 'json'):
                        self.assertTrue((after / f'check-{stage}-12-{seat}.{suffix}').is_file())
                self.assertEqual(original, {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in before.iterdir()})


if __name__ == '__main__':
    unittest.main()
