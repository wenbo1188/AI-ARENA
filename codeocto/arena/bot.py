"""机器人进程管理：每个机器人是一个独立子进程，通过 stdin/stdout 逐行收发 JSON。

协议（每行一个 JSON 对象）：
  arena -> bot  {"type": "init", ...游戏信息}
  bot  -> arena {"ready": true}                      （必须回复 ready:true）
  arena -> bot  {"type": "turn", "tick": t, ...观测}
  bot  -> arena {"tick": t, ...动作}                 （必须回显 tick）
  arena -> bot  {"type": "end", "scores": [...]}

初始化失败停止策略；普通 tick 超时或协议错误仅本 tick 默认，后续可以恢复。
整局计时口径、每步上限和内存限制由游戏规则指定。
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

from .resources import ProcessResources


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
    cpu_ms: float = 0.0
    used_ms: float = 0.0      # 整局占用的思考时间（含超时），用于总时间预算；严格规则下是进程 CPU 时间
    turns: int = 0
    initialized: bool = False
    last_error: str = ""
    crashed: bool = False
    crash_reason: str = ""
    stderr_tail: list[str] = field(default_factory=list)


#: 机器人进程的内存上限（字节），0 表示不限制
MEMORY_LIMIT = 256 * 1024 * 1024


def _bot_env() -> dict:
    """只给机器人最基本的环境变量，避免把 API 密钥等泄露给提交的代码。"""
    keep = ("PATH", "LANG", "LC_ALL", "HOME", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _limit_resources(pid: int) -> None:
    """Linux 上限制进程内存（其他系统忽略）。真正的隔离请在容器/沙箱里运行竞技场。"""
    if not MEMORY_LIMIT:
        return
    try:
        import resource
        resource.prlimit(pid, resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ImportError, AttributeError, ValueError, OSError):
        pass


class BotProcess:
    """strict=False 是原来的宽松规则；strict=True 时 total_time_ms 按进程 CPU 时间监控（后台线程每 5 ms 采样一次），
    普通 tick 协议错误只影响当前动作，stdout 单行和收发队列有上限，内存上限是 memory_bytes。"""

    def __init__(self, spec: BotSpec, seat: int, strict: bool = True, total_time_ms: float | None = None,
                 memory_bytes: int | None = None):
        self.spec = spec
        self.seat = seat
        self.strict = strict
        self.total_time_ms = total_time_ms
        self.stats = BotStats()
        self._stop = threading.Event()
        self._sample_lock = threading.Lock()
        self._lines: "queue.Queue[tuple[str | None, float]]" = queue.Queue(maxsize=16 if strict else 0)
        self._writes: "queue.Queue[dict]" = queue.Queue(maxsize=4)
        self.last_arrival = 0.0  # 最近一条被接受的回复到达的时间（time.monotonic）
        self.resources = None
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
            start_new_session=strict and sys.platform.startswith("linux"),
        )
        if strict:
            try:
                self.resources = ProcessResources(self.proc, memory_bytes or MEMORY_LIMIT)
            except Exception:
                self.proc.kill()
                self.proc.wait()
                raise
        else:
            _limit_resources(self.proc.pid)
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        if strict:
            threading.Thread(target=self._write_stdin, daemon=True).start()
            if total_time_ms is not None:
                threading.Thread(target=self._monitor_cpu, daemon=True).start()

    # ---------- 严格规则：CPU 时间 ----------
    def sample_cpu(self):
        if not self.resources:
            return
        with self._sample_lock:
            try:
                self.stats.cpu_ms = max(self.stats.cpu_ms, self.resources.cpu_ms())
                if self.total_time_ms is not None:
                    self.stats.used_ms = self.stats.cpu_ms
            except (OSError, ValueError):
                # 进程被回收后 /proc 里就没有它了
                if self.proc.poll() is None:
                    self.kill("无法读取进程 CPU 时间")
            if self.total_time_ms is not None and self.stats.used_ms > self.total_time_ms:
                self.kill(f"超出整局 CPU 时间预算 {self.total_time_ms:g} ms")

    def _monitor_cpu(self):
        while not self._stop.wait(0.005):
            self.sample_cpu()
            if self.stats.crashed:
                break

    # ---------- 收发 ----------
    def _enqueue(self, line):
        try:
            self._lines.put_nowait((line, time.monotonic()))
        except queue.Full:
            self.kill("stdout 输出队列超限")

    def _read_stdout(self):
        if not self.strict:
            for line in self.proc.stdout:
                self._lines.put((line, time.monotonic()))
            self._lines.put((None, time.monotonic()))  # EOF
            return
        try:
            while not self._stop.is_set():
                line = self.proc.stdout.readline(65537)
                if not line:
                    break
                if len(line) > 65536:
                    self.kill("stdout 单行超出 65536 字符")
                    break
                self._enqueue(line)
        except (OSError, UnicodeError, ValueError):
            self.kill("stdout 读取失败")
        self._enqueue(None)

    def _read_stderr(self):
        try:
            while not self._stop.is_set():
                line = self.proc.stderr.readline(4096)
                if not line:
                    break
                tail = self.stats.stderr_tail
                tail.append(line.rstrip("\n"))
                if len(tail) > 50:
                    del tail[0]
        except (OSError, UnicodeError, ValueError):
            pass

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
        """发送一条消息，返回开始计时的时刻（time.monotonic）。严格规则下由写线程发出，不会卡住裁判。"""
        start = time.monotonic()
        if self.stats.crashed:
            return start
        if self.strict:
            try:
                self._writes.put_nowait(msg)
            except queue.Full:
                self.kill("输入消息积压")
            return start
        try:
            self.proc.stdin.write(json.dumps(msg, separators=(",", ":")) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.stats.crashed = True
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
            if self.resources:
                self.resources.terminate()
            else:
                self.proc.kill()
        except OSError:
            pass

    def close(self) -> None:
        if not self.strict:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self._stop.set()
            return
        self._stop.set()
        self.sample_cpu()
        # 先结束进程：写线程卡在 stdin 上时关闭 stdin 可能死锁
        self.resources.terminate()
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
        self.resources.close()
