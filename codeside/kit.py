"""选手开发入口：仅依赖 Python 标准库。运行任意 bot 前请确认代码可信。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import zipfile

from arena.bot import BotProcess, BotSpec
from arena.protocol import action_errors
from arena.games.codeside.game import CodeSide
from arena.runner import run_match, save_replay

ROOT = Path(__file__).resolve().parent
STAGES = ("round1", "round2", "finals")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def spec(path, name):
    path = path.resolve(strict=True)
    return BotSpec(name, [sys.executable, "-u", str(path)], str(path.parent))


def budget(args):
    return dict(time_limit_ms=args.time_ms)


def protocol_probe(path, stage, seat, seed, time_ms):
    """短程逐条检查协议。计分比赛仍使用原模拟器。"""
    game = CodeSide(seed=seed, stage=stage)
    total = game.official_time_budget_ms()
    bot = BotProcess(spec(path, "candidate"), seat, total_time_ms=total)
    errors = []
    try:
        start = bot.send({"type": "init", "time_limit_ms": time_ms, "total_time_ms": total,
                  "time_budget_type": "cpu_user_system", "memory_limit_bytes": 256 * 1024 * 1024,
                  **game.init_message(seat)})
        first_deadline = start + time_ms / 1000
        bot.send({"type": "turn", "tick": 0, **game.observe(seat)})
        ready = bot.receive(first_deadline, None)
        if not isinstance(ready, dict) or ready.get("ready") is not True:
            return ["init 必须回复 {\"ready\": true}"]
        for tick in range(12):
            view = game.observe(seat)
            owned = {str(u["id"]) for u in view["player_view"]["game"]["units"]
                     if u["player_id"] == view["player_view"]["my_id"]}
            deadline = first_deadline if tick == 0 else bot.send({"type": "turn", "tick": tick, **view}) + time_ms / 1000
            msg = bot.receive(deadline, tick)
            if msg is None:
                bot.kill("协议自测回复超时或进程崩溃")
                errors.append(bot.stats.crash_reason)
                break
            errors.extend(action_errors(msg, owned))
            if errors:
                break
            actions = [None, None]
            actions[seat] = msg
            game.step(actions)
        if bot.stats.invalid:
            errors.append("stdout 含非协议 JSON 对象")
        if bot.stats.crashed:
            errors.append("进程提前退出: " + bot.stats.crash_reason)
        bot.send({"type": "end", "scores": game.scores()})
    finally:
        bot.close()
    return errors


def check(args):
    me = args.bot.resolve(strict=True)
    compile(me.read_text(encoding="utf-8-sig"), str(me), "exec")
    report = {"kit_version": "1.2-dev", "bot_sha256": digest(me), "python": sys.version,
              "ticks_per_match": args.ticks, "time_ms": args.time_ms,
              "time_budget_type": "cpu_user_system", "matches": [], "problems": []}
    for index, stage in enumerate(STAGES):
        for seat in (0, 1):
            seed = (12, 21, 34)[index]
            label = f"{stage} / {'左' if seat == 0 else '右'}侧"
            errors = protocol_probe(me, stage, seat, seed, report["time_ms"])
            if errors:
                report["problems"].extend(label + ": " + e for e in errors)
                print(label + " 协议检查失败", flush=True)
                continue
            specs = [spec(ROOT / "bots/codeside/quickstart_bot.py", "baseline")] * 2
            specs[seat] = spec(me, "candidate")
            result = run_match("codeside", specs, seed=seed, stage=stage, ticks=args.ticks, **budget(args))
            stats = result.stats[seat]
            report["matches"].append({"stage": stage, "seat": seat, "seed": seed,
                                      "ticks": result.ticks, "scores": result.scores, "stats": stats})
            if stats["crashed"] or stats["invalid_lines"] or stats["timeouts"]:
                report["problems"].append(label + ": 崩溃、非法输出或超时")
            # 基准故障会使这场检查无效，不能静默通过。
            other = result.stats[1 - seat]
            if other["crashed"] or other["invalid_lines"] or other["timeouts"]:
                report["problems"].append(label + ": 基准程序异常，请空闲机器上重新检查")
            print(f"{label}: {result.scores}, 超时 {stats['timeouts']}, 崩溃 {stats['crashed']}", flush=True)
    report["passed"] = not report["problems"] and len(report["matches"]) == 6
    write_json(ROOT / "results/check.json", report)
    print("自测通过（不代表正式比赛准入或强度认证）" if report["passed"] else "自测失败，查看 results/check.json")
    return 0 if report["passed"] else 1


def match(args):
    specs = [spec(args.bot, "candidate"), spec(args.opponent, "baseline")]
    if args.seat == "right":
        specs.reverse()
    result = run_match("codeside", specs, seed=args.seed, stage=args.stage, ticks=args.ticks, **budget(args))
    dest = ROOT / "results" / f"{args.stage}-{args.seed}-{args.seat}"
    save_replay(result, str(dest) + ".json", str(dest) + ".html")
    print(json.dumps({"scores": result.scores, "ticks": result.ticks, "stats": result.stats}, ensure_ascii=False, indent=2))
    print("回放: " + str(dest) + ".html")
    return int(any(s["crashed"] or s["invalid_lines"] for s in result.stats))


def pack(args):
    bot = args.bot.resolve(strict=True)
    meta = json.loads(args.meta.read_text(encoding="utf-8-sig"))
    name = meta.get("participant_name", "").strip()
    if not name or name == "请填写选手名称":
        raise ValueError("请先填写 entry/meta.json 的 participant_name")
    report = json.loads((ROOT / "results/check.json").read_text(encoding="utf-8"))
    if (not report.get("passed") or report.get("bot_sha256") != digest(bot)
            or report.get("ticks_per_match", 0) < 180 or report.get("kit_version") != "1.2-dev"
            or report.get("time_ms") != 1000 or report.get("time_budget_type") != "cpu_user_system"):
        raise ValueError("请先用当前 bot.py 完成至少 180 tick 的六场自测")
    safe = re.sub(r"[^\w-]+", "_", name)[:40]
    dest = ROOT / "dist" / f"{safe}-{digest(bot)[:12]}.zip"
    dest.parent.mkdir(exist_ok=True)
    payload = {**meta, "game": "codeside", "kit_version": "1.2-dev", "bot_sha256": digest(bot)}
    # 同一代码版本的已有提交不覆盖。
    with zipfile.ZipFile(dest, "x", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bot.py", bot.read_bytes())
        z.writestr("meta.json", json.dumps(payload, ensure_ascii=False, indent=2))
        z.writestr("selfcheck.json", json.dumps(report, ensure_ascii=False, indent=2))
        z.writestr("SHA256.txt", digest(bot) + "  bot.py\n")
    print("提交包: " + str(dest))
    return 0


def main():
    p = argparse.ArgumentParser(description="平台射击赛选手工具；仅运行可信代码")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("match", "check", "pack"):
        parser = sub.add_parser(name)
        parser.add_argument("--bot", type=Path, default=ROOT / "entry/bot.py")
        if name == "pack":
            parser.add_argument("--meta", type=Path, default=ROOT / "entry/meta.json")
            continue
        parser.add_argument("--ticks", type=int, default=180 if name == "check" else 3600)
        parser.add_argument("--time-ms", type=float, default=1000, help="单 tick 现实时间上限；非默认值仅供压力测试")
        parser.add_argument("--budget-mode", choices=("total",), default="total", help=argparse.SUPPRESS)
        parser.add_argument("--official-time", action="store_true", help=argparse.SUPPRESS)
        if name == "match":
            parser.add_argument("--opponent", type=Path, default=ROOT / "bots/codeside/quickstart_bot.py")
            parser.add_argument("--stage", choices=STAGES, default="round1")
            parser.add_argument("--seed", type=int, default=12)
            parser.add_argument("--seat", choices=("left", "right"), default="left")
    args = p.parse_args()
    if hasattr(args, "budget_mode"):
        args.official_time = args.official_time or args.budget_mode == "total"
    if hasattr(args, "ticks") and (args.ticks < 1 or not math.isfinite(args.time_ms) or args.time_ms <= 0):
        p.error("ticks 和 time-ms 必须为正数")
    try:
        return {"match": match, "check": check, "pack": pack}[args.command](args)
    except (OSError, ValueError, SyntaxError) as exc:
        print("操作失败: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
