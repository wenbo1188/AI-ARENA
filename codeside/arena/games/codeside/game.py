"""CodeSide 2019（Russian AI Cup 2019）：2D 横版平台射击。

规则、常数、关卡生成和模拟都移植自官方仓库 github.com/MailRuChamps/raic-2019 的 app-src（Rust 源码）和 docs/Rules.tex。
- 开局把官方的 Properties 和 Level 发给参赛程序（之后不再变化，不在每回合重复发送）；
- 每个 tick 发官方的 PlayerView {my_id, game}，参赛程序回复 {单位 id: UnitAction}；
- 坐标不做视角转换，和原版一样用绝对坐标，用 my_id 区分敌我（地图左右对称）。
官方三个阶段：round1（1v1，simple 关卡）、round2（2v2，simple）、finals（2v2，complex 关卡）。
"""
from __future__ import annotations

import copy
import math
import random
from typing import Any

from ...game import Game
from . import levels
from .sim import PROPERTIES, WEAPON_TYPES, World

STAGES = {
    "round1": {"team_size": 1, "level": "simple"},
    "round2": {"team_size": 2, "level": "simple"},
    "finals": {"team_size": 2, "level": "complex"},
}
DEFAULTS = {
    "stage": "round2",     # 官方阶段：round1 / round2 / finals
    "level": None,         # 覆盖关卡：simple / complex / level.txt / empty / 自定义 .txt 文件路径
    "team_size": None,     # 覆盖每队人数
    "ticks": None,         # 覆盖 max_tick_count（官方 3600）
}
# 其他 Properties 里的标量常数也能用 -o 覆盖，例如 -o updates_per_tick=20 可以加速模拟（官方 100）

MINE_STATES = ("PREPARING", "IDLE", "TRIGGERED", "EXPLODED")
ITEM_KINDS = {"HealthPack": 0, "Mine": 1}


class CodeSide(Game):
    """2D 横版射击（复刻 CodeSide 2019），伤害 + 击杀得分多者胜。"""

    name = "codeside"
    num_players = 2
    baselines = ["bots/codeside/random_bot.py", "bots/codeside/quickstart_bot.py"]
    validation_options = {"ticks": 1200}

    @classmethod
    def doc(cls) -> str:
        """接口文档里嵌入模拟源码和官方快速开始模板，保证和实际实现一致。"""
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, "sim.py"), encoding="utf-8") as f:
            sim_src = f.read()
        with open(os.path.join(here, "..", "..", "..", "bots", "codeside", "quickstart_bot.py"), encoding="utf-8") as f:
            qs_src = f.read()
        return (super().doc().replace("{{SIM_SOURCE}}", sim_src.rstrip())
                .replace("{{QUICKSTART_SOURCE}}", qs_src.rstrip()))

    def __init__(self, seed: int = 0, **options: Any):
        super().__init__(seed, **options)
        scalar_props = {k for k, v in PROPERTIES.items() if isinstance(v, (int, float))}
        unknown = set(options) - set(DEFAULTS) - scalar_props
        if unknown:
            raise ValueError(f"未知的 CodeSide 参数: {sorted(unknown)}")
        cfg = {**DEFAULTS, **{k: v for k, v in options.items() if k in DEFAULTS}}
        if cfg["stage"] not in STAGES:
            raise ValueError(f"stage 只能是 {', '.join(STAGES)}")
        for k, v in STAGES[cfg["stage"]].items():
            if cfg[k] is None:
                cfg[k] = v
        props = copy.deepcopy(PROPERTIES)
        for k in scalar_props & set(options):
            props[k] = type(PROPERTIES[k])(options[k])
        props["team_size"] = int(cfg["team_size"])
        if cfg["ticks"] is not None:
            props["max_tick_count"] = int(cfg["ticks"])
        self.cfg = cfg
        self.props = props
        self.rng = random.Random(seed)
        tiles, spawn = levels.create(str(cfg["level"]), self.rng)
        if len(spawn) < 2 * props["team_size"]:
            raise ValueError("关卡的出生点不够")
        self.world = World(props, tiles, spawn, self.rng)
        self._initial_units = [[u.id, u.player_id] for u in self.world.units]
        self.crashed = [False, False]
        self._events: list = []
        self._last_loot = None

    # ---------- 基本 ----------
    @property
    def tick(self) -> int:
        return self.world.current_tick

    def is_over(self) -> bool:
        return self.world.finished() or all(self.crashed)

    def scores(self) -> list[float]:
        return list(self.world.scores)

    @classmethod
    def official_tick_limit_ms(cls) -> float:
        """官方单 tick 思考上限 1 秒。"""
        return 1000

    @classmethod
    def score_labels(cls) -> dict:
        return {"for": "得分", "against": "失分", "diff": "分差", "for_long": "总得分", "diff_long": "分差"}

    def official_time_budget_ms(self) -> float:
        """官方总时间：20 ms × max_tick_count + 20 秒（官方单 tick 上限是 1 秒）。"""
        return 20 * int(self.props["max_tick_count"]) + 20000

    def set_crashed(self, player: int) -> None:
        self.crashed[player] = True

    # ---------- 协议 ----------
    def init_message(self, player: int) -> dict:
        return {"my_id": self.world.player_ids[player], "stage": self.cfg["stage"], "seed": self.seed,
                "properties": self.props, "level": {"tiles": self.world.tiles}}

    def observe(self, player: int) -> dict:
        w = self.world
        return {"player_view": {"my_id": w.player_ids[player], "game": {
            "current_tick": w.current_tick,
            "players": [{"id": pid, "score": s} for pid, s in zip(w.player_ids, w.scores)],
            "units": [u.to_json() for u in w.units],
            "bullets": [b.to_json() for b in w.bullets],
            "mines": [m.to_json() for m in w.mines],
            "loot_boxes": [b.to_json() for b in w.loot_boxes],
        }}}

    @staticmethod
    def _num(v, lim=1e6):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return max(-lim, min(lim, f))

    def _parse(self, player: int, msg) -> dict:
        """{"actions": {"<单位 id>": UnitAction}}。只接受自己单位的动作，其余忽略（官方也是忽略并警告）。"""
        acts = msg.get("actions") if isinstance(msg, dict) else None
        if not isinstance(acts, dict):
            return {}
        pid = self.world.player_ids[player]
        out = {}
        for u in self.world.units:
            if u.player_id != pid:
                continue
            a = acts.get(str(u.id), acts.get(u.id))
            if not isinstance(a, dict):
                continue
            aim = a.get("aim")
            if isinstance(aim, dict):
                ax, ay = self._num(aim.get("x", 0)), self._num(aim.get("y", 0))
            elif isinstance(aim, (list, tuple)) and len(aim) == 2:
                ax, ay = self._num(aim[0]), self._num(aim[1])
            else:
                ax = ay = 0.0
            out[u.id] = {"velocity": self._num(a.get("velocity", 0)), "jump": bool(a.get("jump")),
                         "jump_down": bool(a.get("jump_down")), "ax": ax, "ay": ay,
                         "shoot": bool(a.get("shoot")), "reload": bool(a.get("reload")),
                         "swap_weapon": bool(a.get("swap_weapon")), "plant_mine": bool(a.get("plant_mine"))}
        return out

    def step(self, actions: list[Any]) -> None:
        merged = {}
        for p in range(2):
            if not self.crashed[p] and actions[p] is not None:
                merged.update(self._parse(p, actions[p]))
        self._events = self.world.tick(merged)

    # ---------- 回放 ----------
    def frame(self) -> dict:
        w = self.world
        r2 = lambda v: round(v, 2)
        units = []
        for u in w.units:
            flags = (u.on_ground | u.on_ladder << 1 | u.stand << 2 | u.walked_right << 3
                     | u.jump_state.can_jump << 4)
            wp = u.weapon
            units.append([u.id, r2(u.x), r2(u.y), u.health, flags, u.mines,
                          WEAPON_TYPES.index(wp.typ) if wp else -1,
                          wp.magazine if wp else 0,
                          r2(wp.last_angle) if wp and wp.last_angle is not None else None,
                          wp.last_fire_tick if wp else None,
                          r2(wp.fire_timer) if wp and wp.fire_timer is not None else 0,
                          r2(wp.spread) if wp else 0])
        f = {"t": w.current_tick, "s": list(w.scores), "u": units}
        if w.bullets:
            f["b"] = [[r2(b.x), r2(b.y), r2(math.atan2(b.vy, b.vx)), WEAPON_TYPES.index(b.weapon_type)]
                      for b in w.bullets]
        if w.mines:
            f["m"] = [[r2(m.x), r2(m.y), MINE_STATES.index(m.state), m.player_id] for m in w.mines]
        loot = [[b.x, b.y, ITEM_KINDS.get(b.item["type"], 0) if b.item["type"] != "Weapon"
                 else 2 + WEAPON_TYPES.index(b.item["weapon_type"])] for b in w.loot_boxes]
        if loot != self._last_loot:
            f["l"] = loot
            self._last_loot = loot
        ev = self._compact_events()
        if ev:
            f["e"] = ev
        return f

    def _compact_events(self) -> list:
        """把本 tick 的事件合并成回放用的短列表（跳板每次更新都会触发，这里去重）。"""
        out, seen = [], set()
        for e in self._events:
            kind = e[0]
            if kind == "explosion":
                out.append(["x", round(e[1], 2), round(e[2], 2), e[3]])
            elif kind == "shot":
                out.append(["s", e[1], WEAPON_TYPES.index(e[2])])
            elif kind == "hit":
                out.append(["h", e[1], WEAPON_TYPES.index(e[2])])
            elif kind == "wall":
                out.append(["w", round(e[1], 2), round(e[2], 2), WEAPON_TYPES.index(e[3])])
            elif kind == "death":
                out.append(["d", e[1], round(e[2], 2), round(e[3], 2)])
            elif kind != "blast_hit":
                key = (kind,) + tuple(e[1:])
                if key in seen:
                    continue
                seen.add(key)
                if kind == "pad":
                    out.append(["p", e[1], e[2]])
                elif kind == "heal":
                    out.append(["H", e[1]])
                elif kind in ("pickup", "pickup_mine", "swap"):
                    out.append(["P", e[1]])
                elif kind == "plant":
                    out.append(["M", e[1]])
            if kind == "blast_hit":
                out.append(["B", e[1]])
        return out

    def replay_meta(self) -> dict:
        w = self.world
        code = {"EMPTY": ".", "WALL": "#", "PLATFORM": "^", "LADDER": "H", "JUMP_PAD": "T"}
        return {
            "stage": self.cfg["stage"],
            "level": str(self.cfg["level"]),
            "tiles": ["".join(code[t] for t in col) for col in w.tiles],
            "team_size": self.props["team_size"],
            "players": w.player_ids,
            "units": self._initial_units,
            "max_health": self.props["unit_max_health"],
            "unit_size": [self.props["unit_size"]["x"], self.props["unit_size"]["y"]],
            "magazine": [self.props["weapon_params"][t]["magazine_size"] for t in WEAPON_TYPES],
            "ticks": int(self.props["max_tick_count"]),
            "tps": self.props["ticks_per_second"],
        }

    @staticmethod
    def render_html(replay: dict) -> str:
        from .viewer import render
        return render(replay)
