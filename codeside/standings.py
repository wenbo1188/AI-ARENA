"""将 round1、round2、finals 的完整双循环结果汇总为等权平均积分榜。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import html
import json
import math
from pathlib import Path

STAGES = ("round1", "round2", "finals")


def stage_scores(data):
    """从逐场比分重新计分；不信任选手或旧榜单内的积分、名次。"""
    games = data.get("matches")
    if not isinstance(games, list) or not games:
        raise ValueError("赛段缺少比赛结果")
    rows = defaultdict(lambda: {"played": 0, "win": 0, "draw": 0, "loss": 0, "points": 0})
    fixtures = Counter()
    ids = set()
    for game in games:
        names, scores = game.get("bots"), game.get("scores")
        if not isinstance(names, list) or len(names) != 2 or any(not isinstance(n, str) or not n for n in names) or names[0] == names[1]:
            raise ValueError("对局必须包含两名不同选手")
        if not isinstance(scores, list) or len(scores) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in scores):
            raise ValueError("对局得分必须是两项非负有限数值")
        if type(game.get("match")) is not int or game["match"] in ids:
            raise ValueError("比赛编号缺失或重复")
        ids.add(game["match"])
        seed = game.get("seed")
        if type(seed) is not int:
            raise ValueError("结果缺少地图种子，无法核对同图换边")
        fixtures[(seed, names[0], names[1])] += 1
        for index, name in enumerate(names):
            row = rows[name]
            row["played"] += 1
            own, opponent = scores[index], scores[1 - index]
            result = "win" if own > opponent else "draw" if own == opponent else "loss"
            row[result] += 1
            row["points"] += {"win": 3, "draw": 1, "loss": 0}[result]
    names = set(rows)
    for seed in {f[0] for f in fixtures}:
        for a in names:
            for b in names - {a}:
                if fixtures[(seed, a, b)] != 1:
                    raise ValueError("赛程不完整或重复：每个种子需覆盖全部选手的两两换边对局")
    return dict(rows)


def aggregate(data, expected_rounds=None):
    if set(data) != set(STAGES):
        raise ValueError("必须提供且仅提供三个赛段的完整结果")
    stages = {stage: stage_scores(data[stage]) for stage in STAGES}
    names = set(stages[STAGES[0]])
    if any(set(rows) != names for rows in stages.values()):
        raise ValueError("三个赛段的选手名单必须相同")
    counts = {row["played"] for rows in stages.values() for row in rows.values()}
    if len(counts) != 1:
        raise ValueError("三个赛段必须完成相同轮数和相同场数")
    if expected_rounds is not None:
        if type(expected_rounds) is not int or expected_rounds < 1:
            raise ValueError("赛前公布的轮数必须是正整数")
        if counts != {2 * expected_rounds * (len(names) - 1)}:
            raise ValueError("完成场数与赛前公布的轮数不符")
    ranked = []
    for name in names:
        detail = {}
        total = Fraction(0)
        for stage in STAGES:
            row = stages[stage][name]
            average = Fraction(row["points"], row["played"])
            total += average / 3
            detail[stage] = {**row, "average": float(average), "average_exact": str(average)}
        ranked.append({"bot": name, "stages": detail, "total": float(total), "total_exact": str(total)})
    ranked.sort(key=lambda row: (-Fraction(row["total_exact"]), row["bot"]))
    previous = None
    rank = 0
    for index, row in enumerate(ranked, 1):
        exact = Fraction(row["total_exact"])
        if exact != previous:
            rank = index
        row["rank"] = rank
        previous = exact
    return {"scoring": "mean of three stage-average W3-D1-L0 points", "range": [0, 3],
            "tie_policy": "shared rank; names only order display", "leaderboard": ranked}


def write_results(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "overall.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for row in result["leaderboard"]:
        cells = [str(row["rank"]), html.escape(row["bot"])]
        cells += [f"{row['stages'][stage]['average']:.4f}" for stage in STAGES]
        cells += [f"{row['total']:.4f}"]
        rows.append("<tr>" + "".join("<td>" + v + "</td>" for v in cells) + "</tr>")
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>平台射击赛总榜</title>
<style>body{font:16px/1.7 system-ui,sans-serif;margin:40px auto;padding:0 20px;max-width:960px;color:#263142;background:#f5f6f8}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}.table{overflow:auto}</style>
<h1>平台射击 AI 竞赛 · 总榜</h1><p>每场胜 3、平 1、负 0；各赛段先计算场均积分，再等权平均。总分范围 0–3。总分相同并列。</p>
<div class="table"><table><thead><tr><th>名次</th><th>AI 选手</th><th>round1</th><th>round2</th><th>finals</th><th>总分</th></tr></thead><tbody>'''
    page += "".join(rows) + "</tbody></table></div><p>显示保留四位小数；排名按未舍入精确值计算。相同显示值不一定代表实际同分。</p></html>"
    (output / "overall.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="汇总三个赛段的等权场均胜平负积分")
    parser.add_argument("results", type=Path, help="包含 round1、round2、finals 子目录的结果目录")
    parser.add_argument("--rounds", required=True, type=int, help="赛前公布的每赛段地图轮数，用于检查是否漏赛")
    parser.add_argument("--out", type=Path, help="默认写入输入目录下的 overall 子目录")
    args = parser.parse_args()
    try:
        data = {stage: json.loads((args.results / stage / "leaderboard.json").read_text(encoding="utf-8")) for stage in STAGES}
        result = aggregate(data, args.rounds)
        output = args.out or args.results / "overall"
        write_results(result, output)
        print("总榜已写入 " + str(output.resolve()))
        return 0
    except (OSError, ValueError) as error:
        print("不能生成总榜：" + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
