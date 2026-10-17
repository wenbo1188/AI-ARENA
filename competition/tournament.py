"""Persistent six-player event, with on-site seeds and no implicit result selection.

Game engines are injected as play(bots, seed, replay_path). Only completed
games are counted. Random decisions are journaled *before* running a game.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import html
import itertools
import json
import math
from pathlib import Path
import secrets
import time


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def circle_rounds(names):
    """Five rounds, three pairings each; no random seeds are generated here."""
    wheel = list(names)
    if len(wheel) != 6 or len(set(wheel)) != 6:
        raise ValueError('本版正式赛制要求六名不同选手；不足六名须先确定新赛制')
    rounds = []
    for r in range(5):
        pairs = [(wheel[i], wheel[-1-i]) for i in range(3)]
        rounds.append([tuple(reversed(p)) if (r+i) % 2 else p for i, p in enumerate(pairs)])
        wheel = [wheel[0], wheel[-1], *wheel[1:-1]]
    return rounds


def points(scores):
    if (not isinstance(scores, list) or len(scores) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in scores)):
        raise ValueError('引擎比分必须是两个非负有限数值')
    return [3, 0] if scores[0] > scores[1] else [0, 3] if scores[0] < scores[1] else [1, 1]


def table(names, series):
    rows = {n: dict(name=n, played=0, points=0, wins=0, draws=0, losses=0,
                    game_wins=0, game_losses=0, scored=0, conceded=0) for n in names}
    for match in series:
        if not match.get('complete'):
            raise ValueError('不得用未完成大场生成排名')
        a, b = match['players']
        score = match['points']
        award = points(score)
        for i, n in enumerate((a, b)):
            row = rows[n]
            row['played'] += 1
            row['points'] += award[i]
            row['wins' if award[i] == 3 else 'draws' if award[i] == 1 else 'losses'] += 1
            for game in match['games']:
                seat = game['bots'].index(n)
                scores = game['scores']
                result = points(scores)[seat]
                row['game_wins'] += result == 3
                row['game_losses'] += result == 0
                row['scored'] += scores[seat]
                row['conceded'] += scores[1-seat]
    return rows


def tied_groups(names, series, football, head_to_head=True):
    """H2H is computed once for the entire original equal-points group.

    Never use names as a sporting tiebreak. Residual groups need actual games.
    """
    rows = table(names, series)
    by_points = defaultdict(list)
    for n in names:
        by_points[rows[n]['points']].append(n)
    groups = []
    for score in sorted(by_points, reverse=True):
        group = by_points[score]
        mini = table(group, [s for s in series if set(s['players']) <= set(group)])
        ranked = defaultdict(list)
        for n in group:
            row = rows[n]
            extra = ((row['scored']-row['conceded'], row['scored']) if football else
                     (row['game_wins']-row['game_losses'],))
            ranked[((mini[n]['points'],) if head_to_head else ()) + extra].append(n)
        groups.extend(ranked[key] for key in sorted(ranked, reverse=True))
    return groups


class Paused(RuntimeError):
    """Operational pause, never a draw, loss, or automatic qualification."""


class Tournament:
    def __init__(self, folder, play, check_frozen=lambda: None, game_limit=None):
        self.folder = Path(folder)
        self.path = self.folder / 'event.json'
        self.state = json.loads(self.path.read_text(encoding='utf-8'))
        self.play = play
        self.check_frozen = check_frozen
        self.game_limit = game_limit
        self.played_now = 0

    @classmethod
    def create(cls, folder, event, participants, frozen, mode='development'):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        if (folder / 'event.json').exists():
            raise ValueError('目录已有赛事，不能覆盖')
        names = list(participants)
        rounds = circle_rounds(names)
        state = dict(version='2.0', event=event, mode=mode, participants=participants,
                     frozen=frozen, rounds=rounds, seeds={}, seats={}, series={}, audit=[],
                     qualification={}, status='created', created_at=time.time())
        write_json(folder / 'event.json', state)
        return state

    def save(self):
        write_json(self.path, self.state)

    def seed(self, key):
        if key not in self.state['seeds']:
            used = set(self.state['seeds'].values()) | {12, 21, 34}
            value = secrets.randbits(52)
            while value in used:
                value = secrets.randbits(52)
            self.state['seeds'][key] = value
            self.state['audit'].append(dict(type='seed', key=key, value=value, at=time.time()))
            self.save()
        return self.state['seeds'][key]

    def seat(self, key):
        if key not in self.state['seats']:
            self.state['seats'][key] = secrets.randbelow(2)
            self.state['audit'].append(dict(type='seat', key=key, value=self.state['seats'][key], at=time.time()))
            self.save()
        return self.state['seats'][key]

    def _game(self, match, bots, seed, slot):
        """Resume replays the interrupted fixture, never the previous valid ones."""
        index = len(match['games'])
        record = match.get('pending')
        if record is None:
            if self.game_limit is not None and self.played_now >= self.game_limit:
                raise Paused('达到本次运行场数上限；结果保留，继续运行即可恢复')
            record = dict(bots=list(bots), seed=seed, slot=slot,
                          replay=f"replays/{match['id']}/{index:05d}", started_at=time.time())
            match['pending'] = record
            self.save()
        elif record['bots'] != list(bots) or record['seed'] != seed or record['slot'] != slot:
            raise ValueError('恢复赛程与已记录的待赛对局不一致')
        else:
            self.state['audit'].append(dict(type='interrupted_game_rerun', series=match['id'],
                                            seed=seed, bots=bots, at=time.time()))
            self.save()
        self.check_frozen()
        result = self.play(record['bots'], seed, self.folder / record['replay'])
        points(result['scores'])
        completed = {**record, **result, 'completed_at': time.time()}
        match['games'].append(completed)
        del match['pending']
        self.played_now += 1
        self.save()
        return completed

    def pair(self, key, players, seed_key):
        match = self.state['series'].setdefault(key, dict(id=key, players=list(players), kind='paired', games=[], complete=False))
        if match['players'] != list(players):
            raise ValueError('大场选手与冻结赛程不一致')
        for slot in range(len(match['games']), 2):
            if self.game_limit is not None and self.played_now >= self.game_limit:
                raise Paused('达到本次运行上限；尚未运行轮次不生成种子')
            # Generate only immediately before this round's first real game.
            seed = self.seed(seed_key)
            self._game(match, players if slot == 0 else players[::-1], seed, slot)
        totals = [0, 0]
        for game in match['games']:
            for i, n in enumerate(players):
                totals[i] += points(game['scores'])[game['bots'].index(n)]
        match.update(points=totals, complete=True)
        self.save()
        return match

    def bo5(self, key, players, stage):
        match = self.state['series'].setdefault(key, dict(id=key, players=list(players), kind='bo5', games=[], complete=False))
        if match['players'] != list(players):
            raise ValueError('BO5 选手与已记录赛程不一致')
        wins = [0, 0]
        slots = []
        for game in match['games']:
            award = points(game['scores'])
            if award != [1, 1]:
                wins[players.index(game['bots'][award.index(3)])] += 1
                slots.append(game)
        while max(wins) < 3:
            if self.game_limit is not None and self.played_now >= self.game_limit:
                self.save()
                raise Paused('达到本次运行上限；BO5 未判胜负，可继续运行')
            slot = len(slots)
            left = slot % 2 if slot < 4 else self.seat(stage + '/slot5')
            bots = list(players if left == 0 else players[::-1])
            # The first actual game of a slot uses its paired seed. Any draw
            # keeps that slot's side but gets a fresh shared-stage retry seed.
            draws = sum(g['slot'] == slot for g in match['games'])
            sk = f'{stage}/pair{slot//2}' if draws == 0 else f'{stage}/slot{slot}/retry{draws}'
            seed = self.seed(sk)
            game = self._game(match, bots, seed, slot)
            award = points(game['scores'])
            if award != [1, 1]:
                wins[players.index(bots[award.index(3)])] += 1
                slots.append(game)
            match['wins'] = list(wins)
            self.save()
        match.update(wins=wins, winner=players[wins.index(3)],
                     loser=players[1-wins.index(3)], complete=True)
        self.save()
        return match

    def resolve(self, names, series, key):
        order = []
        football = self.state['event']['game'] == 'football'
        for group_index, group in enumerate(tied_groups(names, series, football, key == 'qualification-order')):
            if len(group) == 1:
                order.extend(group)
            elif len(group) == 2:
                m = self.bo5(f'{key}-tie{group_index}', group, f'{key}-tie{group_index}')
                order.extend((m['winner'], m['loser']))
            else:
                # A residual subset recurses with only new games and new seeds.
                extra = []
                for i, pair in enumerate(itertools.combinations(group, 2)):
                    extra.append(self.pair(f'{key}-tie{group_index}-pair{i}', list(pair), f'{key}-tie{group_index}/map'))
                order.extend(self.resolve(group, extra, f'{key}-tie{group_index}-next'))
        return order

    def run(self):
        self.check_frozen()
        self.state['status'] = 'running'
        self.save()
        regular = []
        for r, pairs in enumerate(self.state['rounds'], 1):
            for i, pair in enumerate(pairs):
                regular.append(self.pair(f'round{r}-match{i+1}', list(pair), f'round{r}'))
        names = list(self.state['participants'])
        order = self.resolve(names, regular, 'qualification-order')
        self.state['regular_order'] = order
        self.state['regular_table'] = table(names, regular)
        self.save()
        semi1 = self.bo5('semifinal1', [order[0], order[3]], 'semifinals')
        semi2 = self.bo5('semifinal2', [order[1], order[2]], 'semifinals')
        fifth = self.bo5('fifth-place', order[4:6], 'fifth-place')
        third = self.bo5('third-place', [semi1['loser'], semi2['loser']], 'third-place')
        final = self.bo5('final', [semi1['winner'], semi2['winner']], 'final')
        ranking = [final['winner'], final['loser'], third['winner'], third['loser'], fifth['winner'], fifth['loser']]
        self.state.update(status='complete', ranking=ranking)
        self.save()
        self.export()
        return ranking

    def export(self):
        ranking = self.state.get('ranking')
        if self.state['status'] != 'complete' or ranking is None:
            raise ValueError('赛事未完成，不能发布正式排名')
        write_json(self.folder / 'ranking.json', dict(event=self.state['event'], mode=self.state['mode'],
                   ranking=[dict(rank=i, name=n) for i, n in enumerate(ranking, 1)]))
        title = html.escape(self.state['event']['title'])
        rows = ''.join(f'<tr><td>{i}</td><td>{html.escape(n)}</td></tr>' for i, n in enumerate(ranking, 1))
        matches = []
        for m in self.state['series'].values():
            links = ' '.join(f'<a href="{g["replay"]}.html">{i+1}</a>' for i, g in enumerate(m['games']))
            label = html.escape(' vs '.join(m['players']))
            result = html.escape(str(m.get('wins', m.get('points'))))
            matches.append(f'<tr><td>{html.escape(m["id"])}</td><td>{label}</td><td>{result}</td><td>{links}</td></tr>')
        mode = '正式比赛' if self.state['mode'] == 'official' else '本地试跑（非正式成绩）'
        (self.folder / 'ranking.html').write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>{title}</title><style>body{{font:16px/1.8 system-ui;max-width:1100px;margin:40px auto;padding:20px}}
td,th{{padding:8px 20px;border-bottom:1px solid #ddd}}table{{border-collapse:collapse}}</style>
<h1>{title}</h1><p>{mode}</p><table><tr><th>名次</th><th>AI</th></tr>{rows}</table>
<h2>大场与逐局回放</h2><table>{''.join(matches)}</table></html>''', encoding='utf-8')
