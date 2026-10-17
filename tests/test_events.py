import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from competition.tournament import Tournament, Paused, circle_rounds, points, tied_groups
from event import qualifying


class EventTests(unittest.TestCase):
    def make(self, tmp, game='football', play=None, **kw):
        event = dict(id='test', title='测试', game=game)
        Tournament.create(tmp, event, dict.fromkeys('ABCDEF', {}), {})
        def stronger(bots, seed, dest):
            winner = min(bots)
            return dict(scores=[1 if n == winner else 0 for n in bots], stats=[])
        return Tournament(tmp, play or stronger, **kw)

    def test_five_rounds_every_opponent_once(self):
        rounds = circle_rounds('ABCDEF')
        pairs = []
        for r in rounds:
            self.assertEqual(set(n for p in r for n in p), set('ABCDEF'))
            pairs.extend(frozenset(p) for p in r)
        self.assertEqual(len(pairs), 15)
        self.assertEqual(len(set(pairs)), 15)

    def test_roster_not_silently_resized(self):
        with self.assertRaises(ValueError):
            circle_rounds('ABCDE')

    def test_no_seeds_at_freeze_and_same_round_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = self.make(tmp, game_limit=6)
            self.assertEqual(event.state['seeds'], {})
            with self.assertRaises(Paused):
                event.run()
            games = [g for s in event.state['series'].values() for g in s['games']]
            self.assertEqual(len(games), 6)
            self.assertEqual(len({g['seed'] for g in games}), 1)
            self.assertEqual(set(event.state['seeds']), {'round1'})

    def test_complete_twenty_series_and_six_ranks(self):
        with tempfile.TemporaryDirectory() as tmp:
            event = self.make(tmp)
            self.assertEqual(event.run(), list('ABCDEF'))
            self.assertEqual(len(event.state['series']), 20)
            self.assertEqual(len(event.state['regular_table']), 6)
            self.assertTrue((Path(tmp)/'ranking.html').exists())
            self.assertEqual({max(s['wins']) for s in event.state['series'].values() if s['kind']=='bo5'}, {3})

    def test_resume_never_replays_valid_games(self):
        calls = []
        def play(bots, seed, dest):
            calls.append((tuple(bots),seed))
            return dict(scores=[int(n==min(bots)) for n in bots], stats=[])
        with tempfile.TemporaryDirectory() as tmp:
            event = self.make(tmp, play=play, game_limit=1)
            with self.assertRaises(Paused):event.run()
            first = calls[0]
            resumed = Tournament(tmp, play)
            resumed.run()
            self.assertEqual(calls.count(first),1)
            self.assertEqual(len(calls),45)

    def test_facility_interruption_keeps_seed_and_side(self):
        calls = []
        def broken(bots, seed, dest):
            calls.append((bots,seed))
            raise RuntimeError('facility')
        with tempfile.TemporaryDirectory() as tmp:
            event = self.make(tmp,play=broken)
            with self.assertRaises(RuntimeError):event.pair('p',['A','B'],'round1')
            def repaired(bots,seed,dest):
                calls.append((bots,seed))
                return dict(scores=[1,0],stats=[])
            resumed = Tournament(tmp,repaired)
            resumed.pair('p',['A','B'],'round1')
            self.assertEqual(calls[0],calls[1])
            self.assertTrue(any(a['type']=='interrupted_game_rerun' for a in resumed.state['audit']))

    def test_bo5_draw_retries_same_slot_without_counting_win(self):
        calls=[]
        def play(bots,seed,dest):
            calls.append((list(bots),seed))
            return dict(scores=[0,0] if len(calls)==1 else [int(n=='A') for n in bots],stats=[])
        with tempfile.TemporaryDirectory() as tmp:
            event=self.make(tmp,play=play)
            match=event.bo5('test',['A','B'],'final')
            self.assertEqual(match['wins'],[3,0])
            self.assertEqual(len(calls),4)
            self.assertEqual(calls[0][0],calls[1][0])
            self.assertNotEqual(calls[0][1],calls[1][1])
            self.assertEqual(calls[0][1],calls[2][1])
            self.assertEqual(calls[2][0],['B','A'])

    def test_bo5_fifth_slot_draw_uses_fixed_random_side(self):
        # Four decisive games split 2:2; draw in the fifth slot then A wins.
        calls=[]
        def play(bots,seed,dest):
            i=len(calls);calls.append((bots,seed))
            winner=['A','B','A','B',None,'A'][i]
            return dict(scores=[0,0] if winner is None else [int(n==winner) for n in bots],stats=[])
        with tempfile.TemporaryDirectory() as tmp:
            event=self.make(tmp,play=play)
            self.assertEqual(event.bo5('f',['A','B'],'final')['winner'],'A')
            self.assertEqual(calls[4][0],calls[5][0])
            self.assertNotEqual(calls[4][1],calls[5][1])

    def test_endless_draws_pause_without_inventing_ranking(self):
        with tempfile.TemporaryDirectory() as tmp:
            event=self.make(tmp,play=lambda *args:dict(scores=[0,0],stats=[]),game_limit=3)
            with self.assertRaises(Paused):event.bo5('p',['A','B'],'final')
            self.assertFalse(event.state['series']['p']['complete'])
            with self.assertRaises(ValueError):event.export()

    def test_tiebreak_group_not_name_sort(self):
        def series(a,b,sa,sb):
            return dict(players=[a,b], points=[3,0] if sa>sb else [0,3],complete=True,
                        games=[dict(bots=[a,b],scores=[sa,sb])])
        # Cycle: all 3 points and equal H2H; football goal difference resolves.
        matches=[series('A','B',2,0),series('B','C',1,0),series('C','A',1,0)]
        self.assertEqual(tied_groups(list('ABC'),matches,True),[['A'],['C'],['B']])
        self.assertEqual(tied_groups(list('ABC'),matches,False),[list('ABC')])

    def test_qualification_accepts_recovery_not_permanent_failure(self):
        self.assertTrue(qualifying(dict(initialized=True,accepted_turns=2,crashed=False,timeouts=1,invalid_lines=1)))
        self.assertFalse(qualifying(dict(initialized=True,accepted_turns=2,crashed=True)))
        self.assertFalse(qualifying(dict(initialized=True,accepted_turns=0,crashed=False)))


if __name__ == '__main__':unittest.main()
