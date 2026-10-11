"""Actual child-process timing checks; no game-physics substitutions."""
import json
import sys
import time
import unittest

from arena.bot import BotProcess, BotSpec
from arena.resources import MEMORY_LIMIT, ProcessResources
from arena.runner import run_match


def bot(code, name='test'):
    return BotSpec(name, [sys.executable, '-u', '-c', code])


def strategy(init='', turn=''):
    return '''import sys,json,time
for line in sys.stdin:
 m=json.loads(line)
 if m['type']=='init':
  %s
  print(json.dumps({'ready':True}),flush=True)
 elif m['type']=='turn':
  %s
  print(json.dumps({'tick':m['tick'],'actions':{}}),flush=True)
 else: break
''' % (init or 'pass', turn or 'pass')


class ResourceTimingTests(unittest.TestCase):
    def match(self, code, **kw):
        return run_match('codeside', [bot(code), bot(strategy(), 'fast')], ticks=4, **kw)

    def test_default_budget_uses_maximum_ticks(self):
        r = self.match(strategy())
        self.assertEqual(r.replay['time_limit_ms'], 1000)
        self.assertEqual(r.replay['total_time_ms'], 20080)
        self.assertEqual(r.replay['memory_limit_bytes'], MEMORY_LIMIT)
        self.assertEqual(r.replay['time_budget_type'], 'cpu_user_system')
        self.assertFalse(any(s['crashed'] for s in r.stats), r.stats)

    def test_sleep_is_wall_time_but_not_cpu_budget(self):
        r = self.match(strategy(turn='time.sleep(.18)'), total_time_ms=300)
        self.assertFalse(r.stats[0]['crashed'], r.stats)
        self.assertGreater(r.stats[0]['avg_ms'], 150)
        self.assertLess(r.stats[0]['cpu_ms'], 300)

    def test_busy_cpu_exhausts_budget_before_wall_limit(self):
        r = self.match(strategy(turn='exec("while True: pass")'), total_time_ms=150)
        self.assertTrue(r.stats[0]['crashed'])
        self.assertIn('CPU', r.stats[0]['crash_reason'])
        self.assertEqual(r.stats[0]['timeouts'], 0)

    def test_single_wall_timeout_is_fatal(self):
        r = self.match(strategy(turn='time.sleep(1.2)'))
        self.assertTrue(r.stats[0]['crashed'])
        self.assertEqual(r.stats[0]['timeouts'], 1)
        self.assertIn('tick 0', r.stats[0]['crash_reason'])
        self.assertFalse(r.stats[1]['crashed'], r.stats)

    def test_initialization_and_first_turn_share_window(self):
        r = self.match(strategy(init='time.sleep(.6)', turn='time.sleep(.6)'))
        self.assertTrue(r.stats[0]['crashed'])
        self.assertEqual(r.stats[0]['timeouts'], 1)
        self.assertFalse(r.stats[1]['crashed'], r.stats)

    def test_slow_initialization_does_not_penalize_opponent(self):
        r = self.match(strategy(init='time.sleep(1.2)'))
        self.assertTrue(r.stats[0]['crashed'])
        self.assertFalse(r.stats[1]['crashed'], r.stats)

    def test_initialization_cpu_is_in_budget(self):
        r = self.match(strategy(init='exec("while True: pass")'), total_time_ms=150)
        self.assertIn('CPU', r.stats[0]['crash_reason'])

    def test_protocol_error_is_fatal_without_waiting_for_timeout(self):
        r = self.match(strategy(turn="print('broken json',flush=True)"))
        self.assertTrue(r.stats[0]['crashed'])
        self.assertEqual(r.stats[0]['invalid_lines'], 1)
        self.assertEqual(r.stats[0]['timeouts'], 0)

    def test_total_budget_is_per_process_in_two_unit_team(self):
        r = self.match(strategy(), stage='finals')
        self.assertEqual(r.replay['total_time_ms'], 20080)

    def test_malformed_actions_crash_bot_without_crashing_referee(self):
        code = strategy().replace("'actions':{}", "'actions':[]")
        r = self.match(code)
        self.assertIn('协议错误', r.stats[0]['crash_reason'])
        self.assertFalse(r.stats[1]['crashed'])

    def test_monitor_counts_background_cpu_outside_receive(self):
        b = BotProcess(bot("import time\nwhile True: pass"), 0, total_time_ms=150)
        try:
            until = time.monotonic() + 3
            while not b.stats.crashed and time.monotonic() < until:
                time.sleep(.02)
            self.assertTrue(b.stats.crashed)
            self.assertIn('CPU', b.stats.crash_reason)
        finally:
            b.close()

    def test_blocked_stdin_does_not_block_send_or_close(self):
        b = BotProcess(bot('import time; time.sleep(20)'), 0)
        start = time.monotonic()
        try:
            sent = b.send({'data': 'x' * 1000000})
            self.assertIsNone(b.receive(sent + .15, None))
        finally:
            b.close()
        self.assertLess(time.monotonic() - start, 2)

    def test_oversize_stdout_is_bounded(self):
        b = BotProcess(bot("print('x'*70000,flush=True); import time; time.sleep(10)"), 0)
        try:
            b.receive(time.monotonic() + 1, None)
            self.assertTrue(b.stats.crashed)
            self.assertIn('stdout', b.stats.crash_reason)
        finally:
            b.close()

    def test_memory_ceiling_prevents_large_allocation(self):
        code = "import sys\ntry: x=bytearray(300*1024*1024)\nexcept MemoryError: print('{\"ready\":true}',flush=True); sys.stdin.readline()\nelse: print('{\"ready\":false}',flush=True); sys.stdin.readline()"
        b = BotProcess(bot(code), 0)
        try:
            self.assertEqual(b.receive(time.monotonic()+1, None), {'ready': True})
        finally:
            b.close()

    def test_linux_cpu_stat_parser_with_unusual_process_name(self):
        stat = '123 (name with ) spaces) ' + ' '.join(['S'] + ['0']*10 + ['7','3'] + ['0']*20)
        self.assertEqual(ProcessResources.linux_cpu_ms(stat, 100), 100)

    def test_cannot_restore_separate_init_grace(self):
        with self.assertRaises(ValueError):
            self.match(strategy(), init_time_limit_ms=3000)


if __name__ == '__main__':
    unittest.main()
