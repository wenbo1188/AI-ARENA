"""对局调度：单场比赛 + 循环赛排行榜。"""
from __future__ import annotations

import itertools
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from .bot import BotProcess, BotSpec
from .games import get_game
from .protocol import action_errors


@dataclass
class MatchResult:
    bots: list[str]
    scores: list[float]
    ticks: int
    replay: dict
    stats: list[dict]

    @property
    def winner(self) -> int | None:
        best = max(self.scores)
        if self.scores.count(best) > 1:
            return None
        return self.scores.index(best)


def run_match(
    game_name: str,
    specs: list[BotSpec],
    seed: int = 0,
    time_limit_ms: float = 1000,
    init_time_limit_ms: float | None = None,
    total_time_ms: float | str | None = None,
    verbose: bool = False,
    **game_options,
) -> MatchResult:
    """每 tick 现实时间上限 + 每进程整局 CPU 预算；None 自动采用游戏预算。

    init 与首个 tick 共用首次响应窗口。init_time_limit_ms 仅保留旧调用兼容，
    不允许额外初始化宽限；自定义时限用于本地压力测试。
    """
    game = get_game(game_name)(seed=seed, **game_options)
    if len(specs) != game.num_players:
        raise ValueError(f"{game_name} 需要 {game.num_players} 个机器人，给了 {len(specs)} 个")
    if total_time_ms is None or total_time_ms == "official":
        if not hasattr(game, "official_time_budget_ms"):
            raise ValueError(f"{game_name} 没有官方的总时间规则")
        if total_time_ms == "official":
            time_limit_ms = game.official_tick_limit_ms()
        total_time_ms = game.official_time_budget_ms()
    if any(not math.isfinite(v) or v <= 0 for v in (time_limit_ms, total_time_ms)):
        raise ValueError("单 tick 时限和 CPU 总预算必须为正的有限数值")
    if init_time_limit_ms is not None and init_time_limit_ms != time_limit_ms:
        raise ValueError("init 与首个 tick 共用时限，不能另设初始化宽限")

    bots = []
    frames = []
    try:
        for seat, spec in enumerate(specs):
            bots.append(BotProcess(spec, seat, total_time_ms=total_time_ms))
        initial_deadlines = []
        for i, bot in enumerate(bots):
            start = bot.send({"type": "init", "time_limit_ms": time_limit_ms, "total_time_ms": total_time_ms,
                      "time_budget_type": "cpu_user_system", "memory_limit_bytes": 256 * 1024 * 1024,
                      **game.init_message(i)})
            initial_deadlines.append(start + time_limit_ms / 1000)
            # Queue the first turn immediately: a slow opponent's ready response
            # must not consume this bot's first response window.
            bot.send({"type": "turn", "tick": 0, **game.observe(i)})
        for bot, deadline in zip(bots, initial_deadlines):
            if bot.receive(deadline, tick=None) is None and not bot.stats.crashed:
                bot.stats.timeouts += 1
                bot.kill("初始化超出首次响应窗口")

        frames.append(game.frame())
        while not game.is_over():
            t = game.tick
            sent_at = []
            for i, bot in enumerate(bots):
                sent_at.append(initial_deadlines[i] - time_limit_ms / 1000 if t == 0 else
                               bot.send({"type": "turn", "tick": t, **game.observe(i)}))
            # 所有机器人并行思考，各自从收到消息起计时
            actions = []
            for i, (bot, start) in enumerate(zip(bots, sent_at)):
                st = bot.stats
                deadline = start + time_limit_ms / 1000
                if t == 0:
                    deadline = min(deadline, initial_deadlines[i])
                invalid_before = st.invalid
                msg = bot.receive(deadline, tick=t)
                if msg is not None and game_name == "codeside":
                    view = game.observe(i)["player_view"]
                    owned = {str(u["id"]) for u in view["game"]["units"] if u["player_id"] == view["my_id"]}
                    errors = action_errors(msg, owned)
                    if errors:
                        st.invalid += 1
                        st.last_error = "协议错误：" + errors[0]
                        msg = None
                # 按回复实际到达的时间计时（各机器人并行思考，这里只是依次收取）
                end = bot.last_arrival if msg is not None else min(time.monotonic(), deadline)
                elapsed = max(0.0, (end - start) * 1000)
                if msg is None:
                    if not st.crashed:
                        if st.invalid == invalid_before:
                            st.timeouts += 1
                else:
                    st.turns += 1
                    st.total_ms += elapsed
                    st.max_ms = max(st.max_ms, elapsed)
                if st.crashed and hasattr(game, "set_crashed"):
                    game.set_crashed(i)
                actions.append(msg)
            game.step(actions)
            frames.append(game.frame())
            if verbose and game.tick % 100 == 0:
                print(f"  tick {game.tick} score {game.scores()}", flush=True)

        scores = game.scores()
        for bot in bots:
            bot.send({"type": "end", "scores": scores})
    finally:
        for bot in bots:
            bot.close()

    stats = []
    for bot in bots:
        s = bot.stats
        stats.append({
            "name": bot.spec.name,
            "timeouts": s.timeouts,
            "invalid_lines": s.invalid,
            "initialized": s.initialized,
            "accepted_turns": s.turns,
            "crashed": s.crashed,
            "crash_reason": s.crash_reason,
            "used_ms": round(s.used_ms),
            "cpu_ms": round(s.used_ms, 3),
            "cpu_backend": bot.resources.backend,
            "avg_ms": round(s.total_ms / s.turns, 2) if s.turns else None,
            "max_ms": round(s.max_ms, 2),
            "stderr_tail": s.stderr_tail[-10:],
        })
    replay = {
        "game": game_name,
        "seed": seed,
        "bots": [s.name for s in specs],
        "scores": scores,
        "time_limit_ms": time_limit_ms,
        "total_time_ms": total_time_ms,
        "time_budget_type": "cpu_user_system",
        "memory_limit_bytes": 256 * 1024 * 1024,
        "meta": game.replay_meta(),
        "stats": stats,
        "frames": frames,
    }
    return MatchResult([s.name for s in specs], scores, game.tick, replay, stats)


def save_replay(result: MatchResult, path_json: str | None, path_html: str | None) -> None:
    if path_json:
        os.makedirs(os.path.dirname(path_json) or ".", exist_ok=True)
        with open(path_json, "w", encoding="utf-8") as f:
            json.dump(result.replay, f, separators=(",", ":"))
    if path_html:
        html = get_game(result.replay["game"]).render_html(result.replay)
        if html:
            os.makedirs(os.path.dirname(path_html) or ".", exist_ok=True)
            with open(path_html, "w", encoding="utf-8") as f:
                f.write(html)


def _play_fixture(job):
    game_name, sa, sb, seed, idx, out_dir, match_kwargs = job
    res = run_match(game_name, [sa, sb], seed=seed, **match_kwargs)
    if out_dir:
        base = os.path.join(out_dir, _replay_name(idx, [sa.name, sb.name]))
        save_replay(res, None, base + ".html")
    res.replay = None  # 回放已写盘，不必传回主进程
    return idx, res


def run_tournament(
    game_name: str,
    specs: list[BotSpec],
    rounds: int = 1,
    out_dir: str | None = None,
    parallel: int = 1,
    seed: int = 0,
    **match_kwargs,
) -> list[dict]:
    """两人游戏的循环赛：每对机器人互换主客场各打 rounds 场。胜 3 分、平 1 分。"""
    game_cls = get_game(game_name)
    if game_cls.num_players != 2:
        raise ValueError("循环赛目前只支持两方对抗的游戏")
    if len(specs) < 2 or rounds < 1:
        raise ValueError("循环赛至少需要两位选手，rounds 至少为 1")
    if len({s.name for s in specs}) != len(specs):
        raise ValueError("循环赛选手名称不能重复")

    if out_dir:
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
    fixtures = []
    for r in range(rounds):
        for a, b in itertools.permutations(range(len(specs)), 2):
            fixtures.append((len(fixtures), a, b, seed + r))

    table = {s.name: {"bot": s.name, "played": 0, "win": 0, "draw": 0, "loss": 0,
                      "for": 0.0, "against": 0.0, "points": 0, "timeouts": 0} for s in specs}
    results = []

    # 同一轮所有对阵使用同一个种子，换边仍使用同一张地图。
    jobs = [(game_name, specs[a], specs[b], map_seed, idx, out_dir, match_kwargs)
            for idx, a, b, map_seed in fixtures]
    fixture_seeds = {idx: map_seed for idx, _, _, map_seed in fixtures}
    # 物理模拟是纯 Python 计算，用多进程才能真正并行
    with ProcessPoolExecutor(max_workers=max(1, parallel)) as pool:
        for idx, res in pool.map(_play_fixture, jobs):
            na, nb = res.bots
            sa, sb = res.scores
            print(f"[{idx + 1}/{len(fixtures)}] {na} {sa:g} : {sb:g} {nb}", flush=True)
            results.append({"match": idx, "seed": fixture_seeds[idx], "bots": res.bots,
                            "scores": res.scores, "stats": res.stats})
            for name, mine, theirs, st in ((na, sa, sb, res.stats[0]), (nb, sb, sa, res.stats[1])):
                row = table[name]
                row["played"] += 1
                row["for"] += mine
                row["against"] += theirs
                row["timeouts"] += st["timeouts"]
                if mine > theirs:
                    row["win"] += 1
                    row["points"] += 3
                elif mine == theirs:
                    row["draw"] += 1
                    row["points"] += 1
                else:
                    row["loss"] += 1

    board = sorted(table.values(), key=lambda r: (-r["points"], -(r["for"] - r["against"]), -r["for"]))
    if out_dir:
        with open(os.path.join(out_dir, "leaderboard.json"), "w", encoding="utf-8") as f:
            json.dump({"leaderboard": board, "matches": results}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(leaderboard_html(game_name, board, sorted(results, key=lambda r: r["match"]), specs))
    return board


def leaderboard_html(game_name: str, board: list[dict], results: list[dict], specs: list[BotSpec]) -> str:
    import html as H
    e = lambda v: H.escape(str(v))
    L = get_game(game_name).score_labels()
    rows = "".join(
        f"<tr><td>{i}</td><td class=n>{e(r['bot'])}</td><td>{r['played']}</td><td>{r['win']}</td><td>{r['draw']}</td>"
        f"<td>{r['loss']}</td><td>{r['for']:g}</td><td>{r['against']:g}</td><td>{r['for'] - r['against']:+g}</td>"
        f"<td><b>{r['points']}</b></td><td>{r['timeouts']}</td></tr>" for i, r in enumerate(board, 1))
    matches = "".join(
        f"<tr><td>{m['match'] + 1}</td><td class=n>{e(m['bots'][0])}</td><td><b>{m['scores'][0]:g} : {m['scores'][1]:g}</b></td>"
        f"<td class=n>{e(m['bots'][1])}</td><td><a href=\"{e(_replay_name(m['match'], m['bots']))}.html\">回放</a></td></tr>"
        for m in results)
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>竞技场排行榜</title>
<style>
:root{{--bg:#f6f7f9;--fg:#1d232b;--muted:#667085;--card:#fff;--line:#d0d5dd;--acc:#2563eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14171c;--fg:#e6e8eb;--muted:#98a2b3;--card:#1d2129;--line:#344054;--acc:#60a5fa}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
main{{max-width:960px;margin:0 auto;padding:16px}} h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px}}
.t{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;background:var(--card);border-radius:8px;overflow:hidden}}
th,td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
th:nth-child(2),td.n{{text-align:left}} a{{color:var(--acc)}} .m{{color:var(--muted)}}
</style></head><body><main>
<h1>排行榜 · {e(game_name)}</h1><p class=m>胜 3 分、平 1 分、负 0 分，同分比{e(L["diff_long"])}、再比{e(L["for_long"])}。</p>
<div class=t><table><tr><th>#</th><th>参赛者</th><th>场</th><th>胜</th><th>平</th><th>负</th><th>{e(L["for"])}</th><th>{e(L["against"])}</th><th>{e(L["diff"])}</th><th>积分</th><th>超时</th></tr>{rows}</table></div>
<h2>全部比赛</h2>
<div class=t><table><tr><th>#</th><th>主队</th><th>比分</th><th>客队</th><th></th></tr>{matches}</table></div>
</main></body></html>"""


def _replay_name(idx: int, bots: list[str]) -> str:
    import re
    safe = lambda s: re.sub(r"[^\w.\-]+", "_", s)
    return f"{idx:03d}_{safe(bots[0])}_vs_{safe(bots[1])}"


def _w(text: str) -> int:
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text, width: int, left=False) -> str:
    text = str(text)
    fill = " " * max(0, width - _w(text))
    return text + fill if left else fill + text


def format_leaderboard(board: list[dict], game_name: str | None = None) -> str:
    L = get_game(game_name).score_labels() if game_name else {"for": "进", "against": "失", "diff": "净胜"}
    cols = ["场", "胜", "平", "负", L["for"], L["against"], L["diff"], "积分", "超时"]
    name_w = max([8] + [_w(r["bot"]) for r in board]) + 2
    lines = [_pad("#", 3) + "  " + _pad("机器人", name_w, left=True) + "".join(_pad(c, 6) for c in cols)]
    for i, r in enumerate(board, 1):
        gd = r["for"] - r["against"]
        vals = [r["played"], r["win"], r["draw"], r["loss"], f"{r['for']:g}", f"{r['against']:g}",
                f"{gd:+g}", r["points"], r["timeouts"]]
        lines.append(_pad(i, 3) + "  " + _pad(r["bot"], name_w, left=True) + "".join(_pad(v, 6) for v in vals))
    return "\n".join(lines)


def rerender_html(path: str) -> bool:
    """从已有的回放 HTML 里取出比赛数据，用当前版本的回放页面重新生成。不是回放文件则返回 False。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    start = text.find("const R = ")
    if start < 0:
        return False
    start += len("const R = ")
    end = text.find(";\n", start)
    try:
        replay = json.loads(text[start:end].replace("<\\/", "</"))
    except json.JSONDecodeError:
        return False
    html = get_game(replay["game"]).render_html(replay)
    if not html:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return True
