"""机器人进程管理：每个机器人是一个独立子进程，通过 stdin/stdout 逐行收发 JSON。

协议（每行一个 JSON 对象）：
  arena -> bot  {"type": "init", ...游戏信息}
  bot  -> arena {"ready": true}                      （可选，任何一行都视为就绪）
  arena -> bot  {"type": "turn", "tick": t, ...观测}
  bot  -> arena {"tick": t, ...动作}                 （必须回显 tick）
  arena -> bot  {"type": "end", "scores": [...]}

严格规则下初始化必须回 ready:true，超时、非法JSON、tick不匹配会停止策略。
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
    crashed: bool = False
    crash_reason: str = ""
    stderr_tail: list[str] = field(default_factory=list)


#: 机器人进程的内存上限（字节），0 表示不限制
MEMORY_LIMIT = int(os.environ.get("ARENA_BOT_MEMORY_MB", "1024")) * 1024 * 1024


def _bot_env() -> dict:
    """只给机器人最基本的环境变量，避免把 API 密钥等泄露给提交的代码。"""
    keep = ("PATH", "LANG", "LC_ALL", "HOME", "SYSTEMROOT", "TMPDIR", "TEMP", "TMP")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONUNBUFFERED"] = "1"
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
    协议错误直接终止进程，stdout 单行和收发队列有上限，内存上限是 memory_bytes。"""

    def __init__(self, spec: BotSpec, seat: int, strict: bool = False, total_time_ms: float | None = None,
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

    def _protocol_error(self, reason: str) -> None:
        self.stats.invalid += 1
        if self.strict:
            self.kill("协议错误：" + reason)

    def receive(self, deadline: float, tick: int | None) -> dict | None:
        """返回 deadline（time.monotonic 时间）之前到达、tick 匹配的回复；没有则返回 None。"""
        while not self.stats.crashed:
            try:
                # 等另一位选手时，这位选手的回复可能早已按时到达：先取已经在队列里的
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
            if arrived > deadline:
                return None  # 迟到；宽松规则下这一行算作丢弃
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("non-finite JSON")))
            except (ValueError, RecursionError):
                self._protocol_error("stdout 不是合法 JSON")
                continue
            if not isinstance(msg, dict):
                self._protocol_error("回复必须为 JSON 对象")
                continue
            if self.strict:
                if tick is None and msg.get("ready") is not True:
                    self._protocol_error("init 回复缺少 ready:true")
                    return None
                if tick is not None and not (type(msg.get("tick")) is int and msg["tick"] == tick):
                    self._protocol_error("tick 缺失或不匹配")
                    return None
                self.sample_cpu()
                if self.stats.crashed:
                    return None
            elif tick is not None and msg.get("tick") != tick:
                continue  # 上一回合迟到的回复，丢弃
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
