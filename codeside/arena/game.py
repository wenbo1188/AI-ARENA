"""通用游戏接口。新增小游戏只需实现 Game 子类并在 games/__init__.py 里注册。"""
from __future__ import annotations

import inspect
import os
from abc import ABC, abstractmethod
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Game(ABC):
    #: 游戏名（命令行 --game 用）
    name: str = ""
    #: 每局参赛机器人数（足球 = 2 支队伍）
    num_players: int = 2

    #: 提交校验时用来试跑的基准机器人（相对项目根目录的路径）
    baselines: list[str] = []
    #: 提交校验时的游戏参数（比如缩短比赛）
    validation_options: dict = {}

    @classmethod
    def doc(cls) -> str:
        """给参赛者（包括大模型）看的接口文档：游戏目录下的 DOC.md。"""
        path = os.path.join(os.path.dirname(inspect.getfile(cls)), "DOC.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def __init__(self, seed: int = 0, **options: Any):
        self.seed = seed
        self.options = options

    @abstractmethod
    def init_message(self, player: int) -> dict:
        """开局时发给第 player 个机器人的信息（规则参数、己方身份等）。"""

    @abstractmethod
    def observe(self, player: int) -> dict:
        """本回合发给第 player 个机器人的观测（不含 type/tick，由 runner 补上）。"""

    @abstractmethod
    def step(self, actions: list[Any]) -> None:
        """推进一回合。actions[i] 是第 i 个机器人的回复；超时/崩溃/非法时为 None。"""

    @abstractmethod
    def is_over(self) -> bool: ...

    @abstractmethod
    def scores(self) -> list[float]:
        """每个机器人的得分（用来判胜负）。"""

    @property
    @abstractmethod
    def tick(self) -> int: ...

    @abstractmethod
    def frame(self) -> dict:
        """当前状态的一帧，写进回放。"""

    @classmethod
    def official_tick_limit_ms(cls) -> float:
        """--official-time 时单个 tick 的思考时限（毫秒）。默认 20000（CodeBall 原版），其他游戏可覆盖。"""
        return 20000

    @classmethod
    def score_labels(cls) -> dict:
        """排行榜和日志里"得分"相关的文字。默认是足球的说法，分数含义不同的游戏可覆盖。
        for / against / diff 用在排行榜表头，for_long / diff_long 用在说明文字和日志里。"""
        return {"for": "进", "against": "失", "diff": "净胜", "for_long": "进球数", "diff_long": "净胜球"}

    def replay_meta(self) -> dict:
        """回放头部信息（场地尺寸等），供可视化使用。"""
        return {}

    @staticmethod
    def render_html(replay: dict) -> str | None:
        """把回放渲染成可独立打开的 HTML；不支持可视化的游戏返回 None。"""
        return None
