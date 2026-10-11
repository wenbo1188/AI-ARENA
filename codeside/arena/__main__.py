"""命令行入口。

  python -m arena match  bots/chaser_bot.py bots/random_bot.py --html replays/demo.html
  python -m arena tournament bots/*.py --rounds 2 --out results/
  python -m arena games

  python -m arena doc football                         打印给参赛模型看的接口文档
  python -m arena submit football 我的AI bot.py          手动提交并试跑校验
  python -m arena generate football --config models.json 让大模型读文档写代码并提交
  python -m arena submissions football                 查看提交和校验结果
  python -m arena tournament --submissions             所有通过校验的提交打循环赛
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .bot import BotSpec
from .games import GAMES, get_game
from .submissions import list_submissions, save_submission, spec_for, validate
from .runner import _pad, format_leaderboard, run_match, run_tournament, save_replay


def _print_report(rep: dict) -> int:
    if rep["passed"]:
        print("校验通过")
        return 0
    print("校验未通过：")
    for p in rep["problems"]:
        print("  " + p.replace("\n", "\n    "))
    return 1


def parse_specs(items: list[str]) -> list[BotSpec]:
    return _dedupe([BotSpec.parse(s) for s in items])


def _dedupe(specs: list[BotSpec]) -> list[BotSpec]:
    seen: dict[str, int] = {}
    for s in specs:  # 同名机器人自动加后缀，避免排行榜混在一起
        if s.name in seen:
            seen[s.name] += 1
            s.name = f"{s.name}#{seen[s.name]}"
        else:
            seen[s.name] = 1
    return specs


def parse_game_opts(items: list[str]) -> dict:
    opts = {}
    for item in items or []:
        k, v = item.split("=", 1)
        try:
            opts[k] = json.loads(v)
        except json.JSONDecodeError:
            opts[k] = v
    return opts


def main(argv=None):
    ap = argparse.ArgumentParser(prog="arena", description="AI 竞技场")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--game", default="codeside", help="游戏名（默认 codeside）")
        p.add_argument("--time-limit-ms", type=float, default=1000, help="每回合思考时限，毫秒（默认 1000）")
        p.add_argument("--init-time-limit-ms", type=float, default=None, help=argparse.SUPPRESS)
        p.add_argument("--total-time-ms", type=float, help="整局 CPU 时间预算，毫秒；默认 20×最大 tick 数+20000")
        p.add_argument("--official-time", action="store_true",
                       help=argparse.SUPPRESS)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("-o", "--opt", action="append", metavar="KEY=VALUE",
                       help="覆盖游戏参数，例如 -o stage=finals -o ticks=3600")

    p = sub.add_parser("match", help="打一场比赛")
    p.add_argument("bots", nargs="+", help="机器人：bot.py / 名字=bot.py / 名字=任意命令")
    p.add_argument("--replay", help="保存回放 JSON")
    p.add_argument("--html", help="保存可视化回放 HTML")
    p.add_argument("-v", "--verbose", action="store_true")
    common(p)

    p = sub.add_parser("tournament", help="循环赛（每对机器人主客场各打一次）并输出排行榜")
    p.add_argument("bots", nargs="*", help="额外加入的机器人（例如基准程序）")
    p.add_argument("--submissions", action="store_true", help="加入所有通过校验的提交")
    p.add_argument("--rounds", type=int, default=1, help="循环几轮")
    p.add_argument("--out", default="results", help="回放和排行榜输出目录")
    p.add_argument("--parallel", type=int, default=1, help="同时进行的比赛数")
    common(p)

    sub.add_parser("games", help="列出可用游戏")

    p = sub.add_parser("rerender", help="用最新的回放页面重新生成已有的 HTML 回放（不重打比赛）")
    p.add_argument("paths", nargs="+", help="回放 HTML 文件或所在目录")

    p = sub.add_parser("doc", help="打印某个游戏给参赛者看的接口文档")
    p.add_argument("game")

    p = sub.add_parser("submit", help="提交代码并试跑校验")
    p.add_argument("game")
    p.add_argument("name", help="参赛名")
    p.add_argument("path", help="bot.py，或包含 bot.py / command.txt 的目录")
    p.add_argument("--model", help="记录是哪个模型写的")
    p.add_argument("--time-limit-ms", type=float, default=1000)

    p = sub.add_parser("validate", help="重新校验已有的提交")
    p.add_argument("game")
    p.add_argument("names", nargs="*", help="不写则校验全部")
    p.add_argument("--time-limit-ms", type=float, default=1000)

    p = sub.add_parser("submissions", help="列出提交")
    p.add_argument("game")

    p = sub.add_parser("generate", help="让大模型读接口文档、写代码、试跑，失败自动把报错发回去修改")
    p.add_argument("game")
    p.add_argument("--config", help="模型列表 JSON 文件（见 models.example.json）")
    p.add_argument("--only", nargs="*", help="只跑配置里这些参赛名")
    p.add_argument("--name", help="单个模型：参赛名")
    p.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    p.add_argument("--model", help="单个模型：模型 id")
    p.add_argument("--base-url", help="OpenAI 兼容接口地址")
    p.add_argument("--api-key-env", help="密钥所在的环境变量名")
    p.add_argument("--attempts", type=int, default=3, help="写代码+修复的最多次数")
    p.add_argument("--improve", type=int, default=0, help="通过后再让模型根据比分自我改进几轮")
    p.add_argument("--time-limit-ms", type=float, default=1000)

    a = ap.parse_args(argv)
    # 把输出路径都转成绝对路径（共享目录下当前目录句柄可能失效）
    for attr in ("replay", "html", "out", "path", "config"):
        if getattr(a, attr, None):
            setattr(a, attr, os.path.abspath(getattr(a, attr)))
    if a.cmd == "games":
        for name, cls in GAMES.items():
            print(f"{name}\t{cls.num_players} 方\t{(cls.__doc__ or '').strip().splitlines()[0]}")
        return

    if a.cmd == "rerender":
        from .runner import rerender_html
        n = 0
        for path in a.paths:
            path = os.path.abspath(path)
            files = [os.path.join(path, f) for f in sorted(os.listdir(path))] if os.path.isdir(path) else [path]
            for f in files:
                if f.endswith(".html") and rerender_html(f):
                    n += 1
        print(f"已重新生成 {n} 个回放")
        return

    if a.cmd == "doc":
        print(get_game(a.game).doc())
        return
    if a.cmd == "submit":
        path = save_submission(a.game, a.name, src=a.path, meta={"model": a.model} if a.model else None)
        print(f"已保存到 {path}，试跑中 ...")
        return _print_report(validate(a.game, a.name, time_limit_ms=a.time_limit_ms))
    if a.cmd == "validate":
        names = a.names or [s["name"] for s in list_submissions(a.game)]
        bad = 0
        for n in names:
            print(f"{n}:")
            bad += _print_report(validate(a.game, n, time_limit_ms=a.time_limit_ms)) or 0
        return 1 if bad else 0
    if a.cmd == "submissions":
        for s in list_submissions(a.game):
            v = s["meta"].get("validation")
            state = "未校验" if not v else ("通过" if v["passed"] else "未通过")
            print(_pad(s["name"], 24, left=True) + _pad(state, 8, left=True)
                  + _pad(s["meta"].get("model") or "-", 28, left=True) + s["meta"].get("submitted_at", ""))
        return
    if a.cmd == "generate":
        from .llm import generate
        if a.config:
            with open(a.config, encoding="utf-8") as f:
                cfgs = json.load(f)
            if a.only:
                cfgs = [c for c in cfgs if c["name"] in a.only]
        else:
            if not a.model:
                ap.error("需要 --config 或 --model")
            cfgs = [{"name": a.name or a.model, "provider": a.provider, "model": a.model}]
            if a.base_url:
                cfgs[0]["base_url"] = a.base_url
            if a.api_key_env:
                cfgs[0]["api_key_env"] = a.api_key_env
        summary = []
        for cfg in cfgs:
            try:
                rep = generate(a.game, cfg, attempts=a.attempts, improve=a.improve, time_limit_ms=a.time_limit_ms)
                summary.append((cfg["name"], "通过" if rep.get("passed") else "未通过"))
            except Exception as e:  # 一个模型出错不影响其他模型
                print(f"[{cfg['name']}] 出错: {type(e).__name__}: {e}")
                summary.append((cfg["name"], f"出错: {e}"))
        print()
        for n, st in summary:
            print(_pad(n, 24, left=True) + st)
        return

    match_kwargs = dict(time_limit_ms=a.time_limit_ms, init_time_limit_ms=a.init_time_limit_ms,
                        total_time_ms="official" if a.official_time else a.total_time_ms,
                        **parse_game_opts(a.opt))
    specs = parse_specs(a.bots)
    if a.cmd == "tournament" and a.submissions:
        subs = list_submissions(a.game, passed_only=True)
        specs += [spec_for(s["path"], s["name"]) for s in subs]
        specs = _dedupe(specs)
    if a.cmd == "tournament" and len(specs) < 2:
        ap.error("至少需要两个参赛者（通过校验的提交或额外机器人）")

    if a.cmd == "match":
        res = run_match(a.game, specs, seed=a.seed, verbose=a.verbose, **match_kwargs)
        print(" vs ".join(res.bots), "->", " : ".join(f"{s:g}" for s in res.scores))
        for s in res.stats:
            print(f"  {s['name']}: 超时 {s['timeouts']} 次, 平均 {s['avg_ms']} ms, 最长 {s['max_ms']} ms"
                  + (f", 已崩溃（{s['crash_reason'] or '未知原因'}）" if s["crashed"] else ""))
            if s["crashed"] and s["stderr_tail"]:
                print("    stderr: " + "\n    ".join(s["stderr_tail"]))
        save_replay(res, a.replay, a.html)
        if a.html:
            print(f"回放: {a.html}")
    else:
        board = run_tournament(a.game, specs, rounds=a.rounds, out_dir=a.out, parallel=a.parallel,
                               seed=a.seed, **match_kwargs)
        print()
        print(format_leaderboard(board, a.game))
        print(f"\n回放和 leaderboard.json 在 {a.out}/")


if __name__ == "__main__":
    sys.exit(main())
