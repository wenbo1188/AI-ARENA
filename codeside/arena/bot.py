"""机器人进程管理：每个机器人是一个独立子进程，通过 stdin/stdout 逐行收发 JSON。

协议（每行一个 JSON 对象）：
  arena -> bot  {"type": "init", ...游戏信息}
  bot  -> arena {"ready": true}
  arena -> bot  {"type": "turn", "tick": t, ...观测}
  bot  -> arena {"tick": t, ...动作}                 （必须回显 tick）
  arena -> bot  {"type": "end", "scores": [...]}

普通 tick 错误可恢复；初始化失败、崩溃或整局预算耗尽后默认接管，不重启。
机器人写到 stderr 的内容会被收集到日志里，便于调试。
"""
from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from .resources import MEMORY_LIMIT, ProcessResources


@dataclass
class BotSpec:
    name: str
    command: list[str]
    cwd: str | None = None

    @staticmethod
    def parse(text: str) -> "BotSpec":
        """支持三种写法：
        path/to/bot.py            -> 用当前 python 运行，名字取文件名
        name=path/to/bot.py       -> 指定名字
        name=任意命令 带 参数      -> 任意语言/可执行程序
        """
        name = None
        if "=" in text.split()[0]:
            name, text = text.split("=", 1)
        parts = shlex.split(text)
        if len(parts) == 1 and parts[0].endswith(".py"):
            parts = [sys.executable, "-u", parts[0]]
        # 脚本路径转成绝对路径，之后不再依赖当前目录
        parts = [os.path.abspath(p) if os.path.splitext(p)[1] in (".py", ".js", ".rb", ".jar") and os.path.exists(p)
                 else p for p in parts]
        if name is None:
            scripts = [p for p in parts if os.path.splitext(p)[1] in (".py", ".js", ".rb", ".jar")]
            name = os.path.splitext(os.path.basename(scripts[-1] if scripts else parts[0]))[0]
        return BotSpec(name=name, command=parts, cwd=_cwd())


def _cwd() -> str | None:
    try:
        return os.getcwd()
    except OSError:
        return None


@dataclass
class BotStats:
    timeouts: int = 0
    invalid: int = 0
    max_ms: float = 0.0
    total_ms: float = 0.0     # 按时回复的 tick 的总用时
    used_ms: float = 0.0      # 进程累计 CPU 时间（用户态 + 内核态），包含启动
    turns: int = 0
    initialized: bool = False
    last_error: str = ""
    crashed: bool = False
    crash_reason: str = ""
    stderr_tail: list[str] = field(default_factory=list)


def _bot_env() -> dict:
    """只给机器人最基本的环境变量，避免把 API 密钥等泄露给提交的代码。"""
    keep = ("PATH", "LANG", "LC_ALL", "HOME", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class BotProcess:
    def __init__(self, spec: BotSpec, seat: int, total_time_ms: float = 92000):
        self.spec = spec
        self.seat = seat
        self.stats = BotStats()
        self.total_time_ms = total_time_ms
        self._stop = threading.Event()
        self._sample_lock = threading.Lock()
        self._lines: "queue.Queue[tuple[str | None, float]]" = queue.Queue(maxsize=16)
        self._writes = queue.Queue(maxsize=4)
        self.last_arrival = 0.0  # 最近一条被接受的回复到达的时间（time.monotonic）
        self.proc = subprocess.Popen(
            spec.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1,
            cwd=spec.cwd,
            env=_bot_env(),
            start_new_session=sys.platform.startswith("linux"),
        )
        try:
            self.resources = ProcessResources(self.proc)
        except Exception:
            self.proc.kill()
            self.proc.wait()
            raise
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._writer = threading.Thread(target=self._write_stdin, daemon=True)
        self._writer.start()
        self._monitor = threading.Thread(target=self._monitor_cpu, daemon=True)
        self._monitor.start()

    def sample_cpu(self):
        with self._sample_lock:
            try:
                self.stats.used_ms = max(self.stats.used_ms, self.resources.cpu_ms())
            except (OSError, ValueError):
                # Linux /proc disappears once a process has been reaped.
                if self.proc.poll() is None:
                    self.kill("无法读取进程 CPU 时间")
            if self.stats.used_ms > self.total_time_ms:
                self.kill(f"超出整局 CPU 时间预算 {self.total_time_ms:g} ms")

    def _monitor_cpu(self):
        while not self._stop.wait(0.005):
            self.sample_cpu()
            if self.stats.crashed:
                break

    def _enqueue(self, line):
        try:
            self._lines.put_nowait((line, time.monotonic()))
        except queue.Full:
            self.kill("stdout 输出队列超限")

    def _read_stdout(self):
        try:
            while not self._stop.is_set():
                line = self.proc.stdout.readline(65537)
                if not line:
                    break
                if len(line) > 65536:
                    self.kill("stdout 单行超出 65536 字符")
                    break
                self._enqueue(line)
        except (OSError, UnicodeError):
            self.kill("stdout 读取失败")
        self._enqueue(None)

    def _read_stderr(self):
        while not self._stop.is_set():
            line = self.proc.stderr.readline(4096)
            if not line:
                break
            tail = self.stats.stderr_tail
            tail.append(line.rstrip("\n"))
            if len(tail) > 50:
                del tail[0]

    def _write_stdin(self):
        try:
            while not self._stop.is_set():
                try:
                    msg = self._writes.get(timeout=0.05)
                except queue.Empty:
                    continue
                self.proc.stdin.write(json.dumps(msg, separators=(",", ":")) + "\n")
                self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            if not self._stop.is_set():
                self.kill("stdin 管道关闭")

    def send(self, msg: dict) -> float:
        start = time.monotonic()
        if self.stats.crashed:
            return start
        try:
            self._writes.put_nowait(msg)
        except queue.Full:
            self.kill("输入消息积压")
        return start

    def receive(self, deadline: float, tick: int | None) -> dict | None:
        """One bad current reply defaults this tick; stale replies never poison recovery.

        Initialization errors are terminal. Arrival timestamps, rather than the
        referee's receive order, determine whether a reply was on time.
        """
        self.stats.last_error = ""
        while not self.stats.crashed:
            try:
                line, arrived = self._lines.get_nowait()
            except queue.Empty:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                try:
                    line, arrived = self._lines.get(timeout=remaining)
                except queue.Empty:
                    return None
            if line is None:
                self.kill(self.stats.crash_reason or "进程退出")
                return None
            try:
                msg = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
                if not isinstance(msg, dict):
                    raise ValueError("回复必须为对象")
            except (ValueError, RecursionError):
                # A malformed line has no tick; only penalize the current window.
                if arrived > deadline:
                    return None
                self.stats.invalid += 1
                self.stats.last_error = "stdout 不是合法 JSON 对象"
                if tick is None:
                    self.kill("初始化协议错误")
                return None
            reply_tick = msg.get("tick")
            if tick is not None and type(reply_tick) is int and reply_tick < tick:
                continue  # discard even if this stale reply arrived in a later window
            if arrived > deadline:
                # Preserve a future tick so it cannot be lost to receive ordering.
                # Future responses are illegal; they never control the current tick.
                return None
            if tick is None:
                if msg.get("ready") is not True:
                    self.stats.invalid += 1
                    self.stats.last_error = "init 回复缺少 ready:true"
                    self.kill("初始化协议错误")
                    return None
                self.stats.initialized = True
            elif type(reply_tick) is not int or reply_tick != tick:
                self.stats.invalid += 1
                self.stats.last_error = "tick 缺失或不匹配"
                return None
            self.sample_cpu()
            if self.stats.crashed:
                return None
            self.last_arrival = arrived
            return msg
        return None

    def kill(self, reason: str) -> None:
        """判定崩溃并结束进程（例如超出总时间预算）。"""
        if self.stats.crashed:
            return
        self.stats.crashed = True
        self.stats.crash_reason = reason
        try:
            self.resources.terminate()
        except OSError:
            pass

    def close(self) -> None:
        self._stop.set()
        self._monitor.join(timeout=1)
        self.sample_cpu()
        # Kill first: closing stdin while its writer is blocked can deadlock.
        self.resources.terminate()
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._writer.join(timeout=1)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
        self.resources.close()
