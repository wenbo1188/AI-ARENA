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
    time_limit_ms: float | None = None,
    init_time_limit_ms: float = 3000,
    total_time_ms: float | str | None = None,
    verbose: bool = False,
    **game_options,
) -> MatchResult:
    """time_limit_ms 是单个 tick 的思考时限（None = 游戏默认，见 Game.match_rules）；total_time_ms 是整局的总时间预算
    （超出判为崩溃），传 "official" 表示按游戏自己的官方规则计算（足球：20 ms × tick 数 + 20 秒，单 tick 最多 20 秒）。
    init_time_limit_ms 只用于宽松规则；严格规则下 init 和第 0 回合共用一个单 tick 时限。"""
    game = get_game(game_name)(seed=seed, **game_options)
    if len(specs) != game.num_players:
        raise ValueError(f"{game_name} 需要 {game.num_players} 个机器人，给了 {len(specs)} 个")
    rules = game.match_rules()
    strict, cpu = bool(rules.get("strict")), bool(rules.get("cpu_budget"))
    if time_limit_ms is None:
        time_limit_ms = rules.get("tick_limit_ms", 100)
    if total_time_ms == "official" or (total_time_ms is None and strict):
        if not hasattr(game, "official_time_budget_ms"):
            raise ValueError(f"{game_name} 没有官方的总时间规则")
        if total_time_ms == "official":
            time_limit_ms = game.official_tick_limit_ms()
        total_time_ms = game.official_time_budget_ms()
    if any(v is not None and not (math.isfinite(v) and v > 0) for v in (time_limit_ms, total_time_ms)):
        raise ValueError("单 tick 时限和总时间预算必须为正的有限数值")
    memory = rules["memory_mb"] * 1024 * 1024 if rules.get("memory_mb") else None

    bots = []
    frames = []
    try:
        for seat, spec in enumerate(specs):
            bots.append(BotProcess(spec, seat, strict=strict, total_time_ms=total_time_ms if cpu else None,
                                   memory_bytes=memory))
        init_extra = {"time_budget_type": "cpu_user_system" if cpu else "wall", "memory_limit_bytes": memory} if strict else {}
        first_deadline = []
        first_start = []
        for i, bot in enumerate(bots):
            start = bot.send({"type": "init", "time_limit_ms": time_limit_ms, "total_time_ms": total_time_ms,
                              **init_extra, **game.init_message(i)})
            if strict:
                # init 和第 0 回合共用一个窗口；第 0 回合马上发出，对手准备得慢不会占用自己的时间
                first_start.append(start)
                first_limit = min(time_limit_ms, total_time_ms) if not cpu and total_time_ms is not None else time_limit_ms
                first_deadline.append(start + first_limit / 1000)
                bot.send({"type": "turn", "tick": 0, **game.observe(i)})
        if strict:
            for bot, deadline in zip(bots, first_deadline):
                if bot.receive(deadline, tick=None) is None and not bot.stats.crashed:
                    bot.stats.timeouts += 1
                    bot.kill("初始化超出首次响应窗口")
        else:
            # 开局：发送规则信息，等待就绪（时限更宽）
            deadline = time.monotonic() + init_time_limit_ms / 1000
            for bot in bots:
                bot.receive(deadline, tick=None)

        frames.append(game.frame())
        while not game.is_over():
            t = game.tick
            sent_at = []
            for i, bot in enumerate(bots):
                if strict and t == 0:
                    sent_at.append(first_start[i])
                else:
                    sent_at.append(bot.send({"type": "turn", "tick": t, **game.observe(i)}))
            # 所有机器人并行思考，各自从收到消息起计时
            actions = []
            for i, (bot, start) in enumerate(zip(bots, sent_at)):
                st = bot.stats
                limit = time_limit_ms
                if total_time_ms is not None and not cpu:
                    limit = min(limit, max(0.0, total_time_ms - st.used_ms))
                deadline = start + limit / 1000
                msg = bot.receive(deadline, tick=t)
                if msg is not None:
                    errors = game.action_errors(i, msg)
                    if errors:
                        st.invalid += 1
                        if strict:
                            bot.kill("协议错误：" + errors[0])
                        msg = None
                # 按回复实际到达的时间计时（各机器人并行思考，这里只是依次收取）
                end = bot.last_arrival if msg is not None else min(time.monotonic(), deadline)
                elapsed = max(0.0, (end - start) * 1000)
                if not st.crashed and not cpu:
                    st.used_ms += elapsed
                if msg is None:
                    if not st.crashed:
                        if total_time_ms is not None and not cpu and st.used_ms >= total_time_ms:
                            bot.kill(f"超出整局总时间预算 {total_time_ms / 1000:g} 秒")
                        else:
                            st.timeouts += 1
                            if strict:
                                bot.kill(f"tick {t} 超出单 tick 时限 {time_limit_ms:g} ms")
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
            "crashed": s.crashed,
            "crash_reason": s.crash_reason,
            "used_ms": round(s.used_ms),
            "avg_ms": round(s.total_ms / s.turns, 2) if s.turns else None,
            "max_ms": round(s.max_ms, 2),
            **({"cpu_ms": round(s.cpu_ms, 3), "cpu_backend": bot.resources.backend} if bot.resources else {}),
            "stderr_tail": s.stderr_tail[-10:],
        })
    replay = {
        "game": game_name,
        "seed": seed,
        "bots": [s.name for s in specs],
        "scores": scores,
        "time_limit_ms": time_limit_ms,
        "total_time_ms": total_time_ms,
        **({"time_budget_type": "cpu_user_system" if cpu else "wall", "memory_limit_bytes": memory} if strict else {}),
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

    # 同一轮所有对阵用同一张地图（同一个种子），换边也是同一张
    jobs = [(game_name, specs[a], specs[b], map_seed, idx, out_dir, match_kwargs) for idx, a, b, map_seed in fixtures]
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
