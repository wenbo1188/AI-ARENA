"""3D 足球（复刻 Russian AI Cup 2018 CodeBall）。

规则、常数、物理和数据结构都按官方《Developer Guide》和 github.com/MailRuChamps/raic-2018 实现：
- 开局把官方的 Rules 对象发给参赛程序，每个 tick 发官方的 Game 对象，参赛程序回复 {机器人 id: Action}。
- 坐标按"己方视角"转换：己方球门永远在 z < 0 一侧（2 号玩家收到的 x、z 取反）。
- 官方三个阶段：round1（2v2 无氮气）、round2（2v2 有氮气）、finals（3v3 有氮气）。
"""
from __future__ import annotations

import math
import random
from typing import Any

from ...game import Game
from .physics import ARENA, RULES, World

STAGES = {
    "round1": {"team_size": 2, "nitro": False},
    "round2": {"team_size": 2, "nitro": True},
    "finals": {"team_size": 3, "nitro": True},
}
DEFAULTS = {
    "stage": "round2",         # 官方阶段：round1 / round2 / finals，决定每队人数和是否有氮气
    "team_size": None,         # 单独覆盖每队人数
    "nitro": None,             # 单独覆盖是否有氮气
    "ticks": 20000,            # 官方 max_tick_count
    "disable_random": False,   # 官方 local runner 的 --disable-random
}
# 物理微步数用规则常数 MICROTICKS_PER_TICK 调整，例如 -o MICROTICKS_PER_TICK=20 可以加速模拟


class Football(Game):
    """3D 机器人足球（复刻 CodeBall 2018），进球多者胜。"""

    name = "football"
    num_players = 2
    baselines = ["bots/random_bot.py", "bots/chaser_bot.py"]
    validation_options = {"ticks": 1800}

    @classmethod
    def doc(cls) -> str:
        """接口文档里嵌入完整的物理参考代码，保证和实际实现一致。"""
        import os
        with open(os.path.join(os.path.dirname(__file__), "physics.py"), encoding="utf-8") as f:
            src = f.read()
        return super().doc().replace("{{PHYSICS_SOURCE}}", src.rstrip())

    def __init__(self, seed: int = 0, **options: Any):
        super().__init__(seed, **options)
        unknown = set(options) - set(DEFAULTS) - set(RULES) - set(ARENA)
        if unknown:
            raise ValueError(f"未知的足球参数: {sorted(unknown)}")
        cfg = {**DEFAULTS, **{k: v for k, v in options.items() if k in DEFAULTS}}
        if cfg["stage"] not in STAGES:
            raise ValueError(f"stage 只能是 {', '.join(STAGES)}")
        for k, v in STAGES[cfg["stage"]].items():
            if cfg[k] is None:
                cfg[k] = v
        self.cfg = cfg
        self.rules = {**RULES, **{k: v for k, v in options.items() if k in RULES}}
        self.arena_cfg = {**ARENA, **{k: v for k, v in options.items() if k in ARENA}}
        self.team_size = int(cfg["team_size"])
        self.rng = random.Random(seed)
        self.world = World(self.rules, self.arena_cfg, self.team_size, bool(cfg["nitro"]),
                           int(self.rules["MICROTICKS_PER_TICK"]), self.rng, bool(cfg["disable_random"]))
        self._tick = 0
        self.score = [0, 0]
        self.crashed = [False, False]
        self.reset_in = 0          # 进球后倒计时，归零时重新开球
        self.goal_event = None

    # ---------- 基本 ----------
    @property
    def tick(self) -> int:
        return self._tick

    def is_over(self) -> bool:
        return self._tick >= int(self.cfg["ticks"]) or all(self.crashed)

    def scores(self) -> list[float]:
        return list(self.score)

    def official_time_budget_ms(self) -> float:
        """官方总时间预算：20 ms × 比赛 tick 数 + 20 秒。"""
        return 20 * int(self.cfg["ticks"]) + 20000

    @classmethod
    def match_rules(cls):
        return {"strict": True, "cpu_budget": False, "tick_limit_ms": 20000, "memory_mb": 256}

    def action_errors(self, player, msg):
        acts = msg.get("actions")
        if not isinstance(acts, dict):
            return ["actions 必须为对象"]
        owned = {str(r.id) for r in self.world.robots if r.team == player}
        fields = {"target_velocity_x", "target_velocity_y", "target_velocity_z", "jump_speed", "use_nitro"}
        for key, act in acts.items():
            if key not in owned:
                return ["actions 包含非己方机器人 ID"]
            if not isinstance(act, dict) or set(act) - fields:
                return ["动作必须为对象，且只能包含声明的动作字段"]
            for name, value in act.items():
                if name == "use_nitro":
                    if type(value) is not bool:
                        return ["use_nitro 必须为布尔值"]
                elif type(value) not in (int, float) or not (-1e308 <= value <= 1e308):
                    return [name + " 必须为有限数值"]
        return []

    # ---------- 视角 ----------
    @staticmethod
    def _flip(team, x, z):
        return (-x, -z) if team == 1 else (x, z)

    def _robot_json(self, viewer, rb):
        """官方 Robot 对象（坐标已转换成 viewer 的视角）。"""
        x, z = self._flip(viewer, rb.x, rb.z)
        vx, vz = self._flip(viewer, rb.vx, rb.vz)
        if rb.touch:
            nx, nz = self._flip(viewer, rb.tnx, rb.tnz)
            tn = (nx, rb.tny, nz)
        else:
            tn = (None, None, None)
        return {"id": rb.id, "player_id": rb.team + 1, "is_teammate": rb.team == viewer,
                "x": x, "y": rb.y, "z": z, "velocity_x": vx, "velocity_y": rb.vy, "velocity_z": vz,
                "radius": rb.radius, "nitro_amount": rb.nitro, "touch": rb.touch,
                "touch_normal_x": tn[0], "touch_normal_y": tn[1], "touch_normal_z": tn[2]}

    # ---------- 协议 ----------
    def init_message(self, player: int) -> dict:
        """官方 Rules 对象。"""
        return {"rules": {"max_tick_count": int(self.cfg["ticks"]), "arena": dict(self.arena_cfg),
                          "team_size": self.team_size,
            "stage": self.cfg["stage"], "seed": self.seed, **self.rules}}

    def observe(self, player: int) -> dict:
        """官方 Game 对象。"""
        w = self.world
        b = w.ball
        bx, bz = self._flip(player, b.x, b.z)
        bvx, bvz = self._flip(player, b.vx, b.vz)
        packs = []
        for i, p in enumerate(w.packs):
            x, z = self._flip(player, p.x, p.z)
            packs.append({"id": i + 1, "x": x, "y": p.y, "z": z, "radius": p.radius,
                          "nitro_amount": self.rules["NITRO_PACK_AMOUNT"],
                          "respawn_ticks": None if p.alive else p.respawn_ticks})
        return {"game": {
            "current_tick": self._tick,
            "players": [{"id": t + 1, "me": t == player, "strategy_crashed": self.crashed[t], "score": self.score[t]}
                        for t in range(2)],
            "robots": [self._robot_json(player, r) for r in w.robots],
            "nitro_packs": packs,
            "ball": {"x": bx, "y": b.y, "z": bz, "velocity_x": bvx, "velocity_y": b.vy, "velocity_z": bvz,
                     "radius": b.radius},
        }}

    @staticmethod
    def _num(v, lo=-1e6, hi=1e6):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return max(lo, min(hi, f))

    def _apply(self, team, msg):
        """msg 是参赛程序的回复：{"actions": {"<机器人 id>": Action}}。没给到的机器人用默认 Action（全 0）。"""
        acts = msg.get("actions") if isinstance(msg, dict) else None
        if not isinstance(acts, dict):
            acts = {}
        for r in self.world.robots:
            if r.team != team:
                continue
            a = acts.get(str(r.id), acts.get(r.id))
            if not isinstance(a, dict):
                a = {}
            x, z = self._flip(team, self._num(a.get("target_velocity_x", 0)), self._num(a.get("target_velocity_z", 0)))
            r.a_tvx, r.a_tvy, r.a_tvz = x, self._num(a.get("target_velocity_y", 0)), z
            r.a_jump = self._num(a.get("jump_speed", 0), 0.0, self.rules["ROBOT_MAX_JUMP_SPEED"])
            r.a_nitro = bool(a.get("use_nitro")) and bool(self.cfg["nitro"])

    def set_crashed(self, player: int) -> None:
        self.crashed[player] = True

    def step(self, actions: list[Any]) -> None:
        for team in range(2):
            self._apply(team, actions[team])
        self.goal_event = None
        scored = self.world.tick()
        self._tick += 1
        if self.reset_in > 0:
            self.reset_in -= 1
            if self.reset_in == 0:
                self.world.reset()
        elif scored is not None:
            self.score[scored] += 1
            self.goal_event = scored
            self.reset_in = int(self.rules["RESET_TICKS"])

    # ---------- 回放 ----------
    def frame(self) -> dict:
        w = self.world
        r2 = lambda v: round(v, 3)                     # 毫米精度：0.1 米会让慢动作回放里球和机器人一顿一顿的
        f = {
            "t": self._tick,
            "s": list(self.score),
            "b": [r2(w.ball.x), r2(w.ball.y), r2(w.ball.z)],
            "r": [[r2(r.x), r2(r.y), r2(r.z), round(r.nitro), int(r.nitro_used)] for r in w.robots],
        }
        if w.packs:
            f["n"] = [int(p.alive) for p in w.packs]
        if self.goal_event is not None:
            f["g"] = self.goal_event
        return f

    def replay_meta(self) -> dict:
        w = self.world
        return {
            "arena": dict(self.arena_cfg),
            "ball_radius": self.rules["BALL_RADIUS"],
            "robot_radius": self.rules["ROBOT_RADIUS"],
            "team_size": self.team_size,
            "stage": self.cfg["stage"],
            "teams": [r.team for r in w.robots],
            "packs": [[p.x, p.y, p.z] for p in w.packs],
            "pack_respawn": self.rules["NITRO_PACK_RESPAWN_TICKS"],
            "reset_ticks": self.rules["RESET_TICKS"],
            "ticks": int(self.cfg["ticks"]),
            "tps": self.rules["TICKS_PER_SECOND"],
        }

    @staticmethod
    def render_html(replay: dict) -> str:
        from .viewer import render
        return render(replay)
