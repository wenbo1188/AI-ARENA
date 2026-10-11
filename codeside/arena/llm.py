"""让大模型读接口文档、写参赛代码，并根据校验结果自动修改后提交。

支持两类接口：
  - anthropic：Claude（需要 pip install anthropic，密钥读 ANTHROPIC_API_KEY）
  - openai：任何 OpenAI 兼容的 /chat/completions 接口（DeepSeek、通义千问、Kimi、GLM、
    本地 vLLM/Ollama 等），只用标准库发请求，base_url 和密钥环境变量可配置
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request

from .games import get_game
from .submissions import save_submission, submission_dir, validate

SYSTEM = ("你是一名参加 AI 编程竞赛的选手。请仔细阅读比赛接口文档，写出尽可能强的参赛程序。"
          "只输出一个完整的 ```python 代码块，不要输出其他解释。")

FIRST_TURN = """下面是比赛的接口文档：

<doc>
{doc}
</doc>

请写出你的参赛程序（单个 Python 3 文件，只用标准库）。目标是赢得比赛，而不只是能跑。"""

FIX_TURN = """你的程序没有通过提交前的试跑，问题如下：

{problems}

请修复问题后重新给出完整代码（同样只输出一个 ```python 代码块）。"""

IMPROVE_TURN = """你的程序通过了试跑，和基准程序的比分如下：

{results}

如果你认为还能明显提高胜率，请给出改进后的完整代码；否则原样输出上一版代码。只输出一个 ```python 代码块。"""


# 模型配置（dict）：
#   name         参赛名（排行榜上显示）
#   provider     "anthropic" 或 "openai"（OpenAI 兼容接口）
#   model        模型 id
#   base_url     OpenAI 兼容接口地址，例如 https://api.deepseek.com/v1
#   api_key_env  存放密钥的环境变量名
#   max_tokens / effort / timeout / extra（额外请求参数）可选


def chat(cfg: dict, messages: list[dict]) -> str:
    provider = cfg.get("provider", "anthropic")
    if provider == "anthropic":
        return _chat_anthropic(cfg, messages)
    if provider == "openai":
        return _chat_openai(cfg, messages)
    raise ValueError(f"未知 provider {provider!r}，可选 anthropic / openai")


def _chat_anthropic(cfg: dict, messages: list[dict]) -> str:
    import anthropic

    key_env = cfg.get("api_key_env")
    client = anthropic.Anthropic(api_key=os.environ[key_env]) if key_env else anthropic.Anthropic()
    params = dict(
        model=cfg.get("model", "claude-opus-5-5"),
        max_tokens=int(cfg.get("max_tokens", 64000)),
        system=SYSTEM,
        messages=messages,
        output_config={"effort": cfg.get("effort", "high")},
        **cfg.get("extra", {}),
    )
    # 被安全策略拒绝时由服务端自动换模型重试
    with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                     **params) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("模型拒绝了请求")
    return "".join(b.text for b in msg.content if b.type == "text")


def _chat_openai(cfg: dict, messages: list[dict]) -> str:
    base = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get(cfg.get("api_key_env", "OPENAI_API_KEY"), "")
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": SYSTEM}] + messages,
        **({"max_tokens": int(cfg["max_tokens"])} if "max_tokens" in cfg else {}),
        **cfg.get("extra", {}),
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
    )
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=float(cfg.get("timeout", 600))) as r:
                data = json.load(r)
            return data["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            last = RuntimeError(f"HTTP {e.code}: {e.read()[:500].decode(errors='replace')}")
            if e.code not in (408, 429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 ** attempt * 3)
    raise last


def extract_code(text: str) -> str | None:
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len)
    if "import" in text and "stdin" in text:  # 没加代码块标记
        return text
    return None


def _goal_diff(report: dict) -> float:
    return sum(m["scores"][m["seat"]] - m["scores"][1 - m["seat"]] for m in report["matches"])


def _results_text(report: dict) -> str:
    lines = []
    for m in report["matches"]:
        mine, theirs = m["scores"][m["seat"]], m["scores"][1 - m["seat"]]
        lines.append(f"- 对 {m['opponent']}（{'先' if m['seat'] == 0 else '后'}手）: {mine:g} : {theirs:g}，"
                     f"平均思考 {m['stats']['avg_ms']} ms")
    return "\n".join(lines)


def generate(game: str, cfg: dict, attempts: int = 3, improve: int = 0, time_limit_ms: float = 1000,
             log=print) -> dict:
    """生成参赛代码：写代码 -> 试跑 -> 有问题把报错发回去让它改，最多 attempts 次；
    通过后可以再让它根据比分自我改进 improve 轮（只保留仍能通过的版本）。"""
    name = cfg["name"]
    doc = get_game(game).doc()
    diff_label = get_game(game).score_labels()["diff_long"]
    messages = [{"role": "user", "content": FIRST_TURN.format(doc=doc)}]
    best = None
    fixes_left, improve_left = attempts, improve
    n = 0
    while True:
        n += 1
        log(f"[{name}] 第 {n} 次请求模型 {cfg.get('model')} ...")
        t0 = time.time()
        reply = chat(cfg, messages)
        log(f"[{name}] 模型回复用时 {time.time() - t0:.0f}s，{len(reply)} 字符")
        messages.append({"role": "assistant", "content": reply})
        code = extract_code(reply)
        # 改进轮先放在临时名下试跑，不合格就不覆盖已通过的版本
        target = name + ".candidate" if best else name
        if code:
            meta = {"model": cfg.get("model"), "provider": cfg.get("provider", "anthropic"), "round": n}
            save_submission(game, target, code=code, meta=meta)
            report = validate(game, target, time_limit_ms=time_limit_ms)
        else:
            report = {"passed": False, "problems": ["没有找到 ```python 代码块"], "matches": []}

        if report["passed"] and best and _goal_diff(report) < _goal_diff(best):
            log(f"[{name}] 改进版对基准程序的{diff_label}更少（{_goal_diff(report):+g} < {_goal_diff(best):+g}），保留上一版")
            shutil.rmtree(submission_dir(game, target), ignore_errors=True)
            break
        if report["passed"]:
            log(f"[{name}] 试跑通过，对基准程序{diff_label} {_goal_diff(report):+g}")
            if best:
                shutil.rmtree(submission_dir(game, name))
                os.rename(submission_dir(game, target), submission_dir(game, name))
            best = report
            if improve_left == 0:
                break
            improve_left -= 1
            messages.append({"role": "user", "content": IMPROVE_TURN.format(results=_results_text(report))})
        else:
            log(f"[{name}] 未通过: " + " | ".join(p.splitlines()[0] for p in report["problems"]))
            if best:
                shutil.rmtree(submission_dir(game, target), ignore_errors=True)
                break
            fixes_left -= 1
            if fixes_left <= 0:
                break
            messages.append({"role": "user", "content": FIX_TURN.format(problems="\n\n".join(report["problems"]))})

    path = submission_dir(game, name)
    if os.path.isdir(path):
        log_msgs = [{"role": "user", "content": "(接口文档)"}] + messages[1:]
        with open(os.path.join(path, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(log_msgs, f, ensure_ascii=False, indent=2)
    return best or {"passed": False}
