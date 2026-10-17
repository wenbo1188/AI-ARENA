import json
import queue
import time
import unittest
from unittest.mock import patch

from arena.bot import BotProcess, BotSpec, BotStats
from arena.runner import MatchResult, run_tournament
from arena.protocol import action_errors


class TimingTests(unittest.TestCase):
    def receiver(self, lines):
        b = BotProcess.__new__(BotProcess)
        b.stats = BotStats()
        b._lines = queue.Queue()
        b.last_arrival = 0
        b.sample_cpu = lambda: None
        def kill(reason):
            b.stats.crashed = True
            b.stats.crash_reason = reason
        b.kill = kill
        for msg, arrived in lines:
            b._lines.put((json.dumps(msg), arrived))
        return b

    def test_on_time_reply_is_read_after_other_bot_wait(self):
        now = time.monotonic()
        b = self.receiver([({"tick": 7, "actions": {}}, now - 0.2)])
        self.assertEqual(b.receive(now - 0.1, 7)["tick"], 7)
        self.assertEqual(b.last_arrival, now - 0.2)

    def test_late_reply_is_rejected_even_when_queued(self):
        now = time.monotonic()
        b = self.receiver([({"tick": 7}, now - 0.05)])
        self.assertIsNone(b.receive(now - 0.1, 7))

    def test_old_tick_is_discarded_and_current_reply_recovers(self):
        now = time.monotonic()
        b = self.receiver([({"tick": 6}, now - 0.3), ({"tick": 7}, now - 0.2)])
        self.assertEqual(b.receive(now - 0.1, 7)["tick"],7)
        self.assertFalse(b.stats.crashed)

    def test_empty_queue_returns_at_expired_deadline(self):
        self.assertIsNone(self.receiver([]).receive(time.monotonic() - 1, 1))


class FixtureTests(unittest.TestCase):
    def test_same_map_for_all_pairs_and_reversed_seats_per_round(self):
        jobs = []

        class Pool:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def map(self, fn, scheduled):
                jobs.extend(scheduled)
                return [(j[4], MatchResult([j[1].name, j[2].name], [0, 0], 1, {},
                                          [{"timeouts": 0}, {"timeouts": 0}])) for j in scheduled]

        with patch("arena.runner.ProcessPoolExecutor", Pool):
            board = run_tournament("codeside", [BotSpec(n, []) for n in "ABC"], seed=101, rounds=2)
        self.assertEqual(len(jobs), 12)
        for offset, seed in ((0, 101), (6, 102)):
            chunk = jobs[offset:offset + 6]
            self.assertEqual({j[3] for j in chunk}, {seed})
            self.assertEqual({(j[1].name, j[2].name) for j in chunk},
                             {(a, b) for a in "ABC" for b in "ABC" if a != b})
        self.assertEqual([r["played"] for r in board], [8, 8, 8])

    def test_duplicate_names_and_invalid_field_rejected(self):
        with self.assertRaises(ValueError):
            run_tournament("codeside", [BotSpec("A", []), BotSpec("A", [])])
        with self.assertRaises(ValueError):
            run_tournament("codeside", [BotSpec("A", [])])

    def test_semantic_protocol_errors(self):
        self.assertTrue(action_errors({"actions": {"9": {}}}, {"1"}))
        self.assertTrue(action_errors({"actions": {"1": {"shoot": "false"}}}, {"1"}))
        self.assertTrue(action_errors({"actions": {"1": {"velocity": float("nan")}}}, {"1"}))
        self.assertEqual(action_errors({"actions": {"1": {"aim": {"x": 1, "y": 0}}}}, {"1"}), [])


if __name__ == "__main__":
    unittest.main()
