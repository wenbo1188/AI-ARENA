"""参赛提交的管理和校验。

目录结构：
  submissions/<游戏名>/<参赛者名>/
      bot.py         提交的代码（或任意文件 + command.txt 写启动命令）
      meta.json      来源（哪个模型）、校验结果等
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
import time

from .bot import BotSpec
from .game import ROOT
from .games import get_game
from .runner import run_match

SUBMISSIONS_DIR = os.environ.get("ARENA_SUBMISSIONS", os.path.join(ROOT, "submissions"))

#: 校验标准
MAX_TIMEOUT_RATE = 0.02


def safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\-]+", "_", name.strip()).strip("._")
    if not name:
        raise ValueError("参赛者名不能为空")
    return name[:64]


def submission_dir(game: str, name: str) -> str:
    return os.path.join(SUBMISSIONS_DIR, game, safe_name(name))


def load_meta(path: str) -> dict:
    try:
        with open(os.path.join(path, "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_meta(path: str, meta: dict) -> None:
    with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def spec_for(path: str, name: str | None = None) -> BotSpec:
    name = name or os.path.basename(path)
    cmd_file = os.path.join(path, "command.txt")
    if os.path.exists(cmd_file):
        with open(cmd_file, encoding="utf-8") as f:
            command = shlex.split(f.read().strip())
    else:
        command = [sys.executable, "-u", "bot.py"]
    return BotSpec(name=name, command=command, cwd=path)


def save_submission(game: str, name: str, *, code: str | None = None, src: str | None = None,
                    meta: dict | None = None) -> str:
    """保存一份提交。code 是 Python 源码；src 是文件或目录路径（目录里放 bot.py 或 command.txt）。"""
    get_game(game)
    path = submission_dir(game, name)
    if os.path.exists(path):
        shutil.rmtree(path)
    if src and os.path.isdir(src):
        shutil.copytree(src, path)
    else:
        os.makedirs(path)
        if src:
            shutil.copy(src, os.path.join(path, "bot.py"))
        else:
            with open(os.path.join(path, "bot.py"), "w", encoding="utf-8") as f:
                f.write(code or "")
    save_meta(path, {"name": safe_name(name), "game": game, "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     **(meta or {})})
    return path


def validate(game: str, name: str, time_limit_ms: float = 1000, verbose: bool = True) -> dict:
    """和基准机器人试跑（主客场各一场）。崩溃、任一超时或协议错误均判不通过。"""
    game_cls = get_game(game)
    path = submission_dir(game, name)
    if not os.path.isdir(path):
        raise FileNotFoundError(f"没有找到提交 {path}")
    me = spec_for(path, safe_name(name))
    problems, matches = [], []
    for base in game_cls.baselines:
        opp = BotSpec.parse(os.path.join(ROOT, base))
        for seat in range(game_cls.num_players):
            specs = [opp] * game_cls.num_players
            specs[seat] = me
            res = run_match(game, specs, seed=len(matches), time_limit_ms=time_limit_ms,
                            **game_cls.validation_options)
            st = res.stats[seat]
            turns = res.ticks
            rate = st["timeouts"] / max(1, turns)
            label = f"对 {opp.name}（{'先' if seat == 0 else '后'}手）"
            matches.append({"opponent": opp.name, "seat": seat, "scores": res.scores, "stats": st})
            if st["crashed"]:
                problems.append(f"{label}: 程序崩溃或提前退出。stderr 最后几行:\n" + "\n".join(st["stderr_tail"]))
            elif st["timeouts"]:
                problems.append(f"{label}: {turns} 个回合里超时 {st['timeouts']} 次（最长 {st['max_ms']} ms，"
                                f"时限 {time_limit_ms} ms）")
            if st["invalid_lines"]:
                problems.append(f"{label}: 标准输出里有 {st['invalid_lines']} 行不是 JSON 对象（调试信息请写到 stderr）")
            if verbose:
                mine, theirs = res.scores[seat], res.scores[1 - seat] if game_cls.num_players == 2 else None
                print(f"  {label}: {mine:g} : {theirs:g}，超时 {st['timeouts']}，平均 {st['avg_ms']} ms"
                      + ("，崩溃" if st["crashed"] else ""), flush=True)
            if st["crashed"]:
                break
        if problems:
            break
    report = {"passed": not problems, "problems": problems, "matches": matches,
              "validated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    meta = load_meta(path)
    meta["validation"] = report
    save_meta(path, meta)
    return report


def list_submissions(game: str, passed_only: bool = False) -> list[dict]:
    base = os.path.join(SUBMISSIONS_DIR, game)
    out = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            continue
        meta = load_meta(path)
        passed = bool(meta.get("validation", {}).get("passed"))
        if passed_only and not passed:
            continue
        out.append({"name": name, "path": path, "passed": passed, "meta": meta})
    return out
