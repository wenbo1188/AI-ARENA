"""八方旅人 II 风格 4v4 旅人对决。

两个机器人各控制一支队伍：先从 8 名旅人中选 4 人（选人阶段），然后按速度轮流行动，
护盾/弱点/击破、BP 加成、潜力、神技等机制参考《八方旅人 II》。
每个 tick 是一次决策（选人，或某个角色的一次行动），两个机器人每个 tick 都会收到观测并且都要回复，
但只有 your_turn 为 true 的一方的回复会被采用。
"""
from __future__ import annotations

import random
from typing import Any

from ...game import Game
from .battle import MAX_BOOST, MAX_BP, Battle
from . import loadout as LO
from .data import ARENA_HP_BONUS, CONCOCT, ESTIMATED, LATENT, LATENT_SKILLS, SKILLS, TRAVELERS, TRAVELER_SKILLS, TYPE_ZH, TYPES

DEFAULTS = {
    "team_size": 4,
    "pick_mode": "blind",   # blind：双方同时盲选，可以选到相同角色；draft：蛇形轮流选，选过的对方不能再选
    "max_rounds": 30,       # 超过回合数按剩余 HP 比例之和判胜负
    "loadout": 1,           # 1：选人后有一步赛前配置（副职、技能、支援技能、道具）；0：跳过，全员无配置
}
DRAFT_ORDER = [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0]


def _rel(obj, player: int):
    """把事件里的 [队伍, id] 换成己方视角：0 = 自己，1 = 对手。"""
    if isinstance(obj, dict):
        return {k: (v ^ player if k in ("winner", "team") and v in (0, 1) else _rel(v, player))
                for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in obj) and obj[0] in (0, 1):
            return [obj[0] ^ player, obj[1]]
        return [_rel(x, player) for x in obj]
    return obj


class Octopath(Game):
    """八方旅人 II 风格 4v4 回合制队伍对决，消灭对方全员获胜。"""

    name = "octopath"
    num_players = 2
    baselines = ["bots/octopath/random_bot.py", "bots/octopath/greedy_bot.py"]
    validation_options = {}

    @classmethod
    def doc(cls) -> str:
        """DOC.md 里的数据表从 data.py 生成，保证文档和实际数值一致。"""
        stat_cols = ["hp", "sp", "pa", "pd", "ea", "ed", "acc", "eva", "crit", "spd"]
        rows = ["| key | 旅人 | 职业 | " + " | ".join(stat_cols) + " | 武器 | 护盾 | 弱点 | 技能 |",
                "|" + "---|" * (len(stat_cols) + 7)]
        for k, t in TRAVELERS.items():
            rows.append(f"| `{k}` | {t['name']} | {t['job']} {t['job_en']} | " + " | ".join(str(t[c]) for c in stat_cols)
                        + f" | {', '.join(t['weapons'])} | {t['shields']} | {', '.join(t['weak'])} | "
                        + ", ".join(f"`{x}`" for x in TRAVELER_SKILLS[k]) + (", `concoct`" if k == "castti" else "") + " |")
        travelers = "\n".join(rows)

        def fmt(sid, sk):
            parts = []
            for f in ("kind", "type", "power", "hits", "boost", "levels", "shield_break", "hit_ratios", "ability_ratios", "invocation_values", "tier_parameters"):
                if sk.get(f) is not None and f in sk:
                    parts.append(f"{f}={sk[f]}")
            if sk.get("spell"):
                parts.append("spell")
            if sk.get("heal"):
                parts.append(f"heal=按属防与技能档位计算")
            star = "★" if sk.get("divine") else ""
            return (f"| `{sid}` | {star}{sk['name']} {sk['zh']} | {sk['sp']} | {sk['target']} | "
                    f"{'; '.join(parts)} | {sk['desc']} |")

        lines = []
        for k, t in TRAVELERS.items():
            lines.append(f"\n**{t['name']}（{t['job']}）**\n")
            lines.append("| id | 名称 | SP | target | 参数 | 说明 |\n|---|---|---|---|---|---|")
            for sid in TRAVELER_SKILLS[k]:
                lines.append(fmt(sid, SKILLS[sid]))
            for sid, sk in LATENT_SKILLS.items():
                if sk["job"] == k:
                    lines.append(fmt(sid, sk) + "")
        lines.append("\n所有旅人通用：`attack` 普通攻击（物理，所用武器类型，威力 1.0，每 1 BP 多打 1 下），`defend` 防御。")
        lines.append("潜力专用招式（光的 tenretsu / hien / sougetsu，欧修缇的 beast_claw / beast_fang / beast_roar）只能在同一次行动发动潜力时使用，不消耗 SP。")
        skills = "\n".join(lines)
        concoct = "| recipe | 名称 | 效果 |\n|---|---|---|\n" + "\n".join(
            f"| `{k}` | {v['zh']} | {v['desc']} |" for k, v in CONCOCT.items())
        stat_zh = {"hp": "HP", "sp": "SP", "pa": "物攻", "pd": "物防", "ea": "属攻", "ed": "属防", "acc": "命中", "eva": "回避",
                   "crit": "暴击", "spd": "速度"}
        jobs = ["| 职业 | 副职加成 | 武器 | 初始技能（免费） | 神技 | 对战里无效果的技能 | 支援技能（第 1～4 个） |", "|---|---|---|---|---|---|---|"]
        for j, zh in LO.JOB_ZH.items():
            sk = LO.JOB_SKILLS[j]
            jobs.append(f"| `{j}` {zh} | " + "，".join(f"{stat_zh[k]}+{v}%" for k, v in LO.JOB_BONUS[j].items())
                        + f" | {', '.join(LO.JOB_WEAPONS[j])} | " + ", ".join(
                            f"`{x}`" + ("（无效果）" if x in LO.NONBATTLE_SKILLS else "") for x in LO.free_skills(j))
                        + " | " + ", ".join(f"`{x}`" for x in sk if SKILLS[x].get("divine")) + " | "
                        + (", ".join(f"`{x}` {LO.NONBATTLE_SKILLS[x]['zh']}" for x in LO.job_grid(j)
                                     if x in LO.NONBATTLE_SKILLS) or "—") + " | "
                        + ", ".join(f"`{x}`" for x in LO.job_supports(j)) + " |")
        sups = ["| id | 职业 | 第几个 | 名称 | 效果 |", "|---|---|---|---|---|"]
        for k, v in LO.SUPPORTS.items():
            eff = v["desc"] + (f"（*估计*：{v['est']}）" if v.get("est") else "")
            if not v.get("battle", True):
                eff = "~~" + v["desc"] + "~~ 不能装备"
            sups.append(f"| `{k}` | {LO.JOB_ZH[v['job']]} | {v['n']} | {v['zh']} {v['name']} | {eff} |")
        tgt_zh = {"ally": "单个己方", "allies": "全体己方", "ko": "倒下的己方", "enemy": "单个敌人", "enemies": "全体敌人"}
        items = ["| id | 名称 | 目标 | 效果 | 价格 |", "|---|---|---|---|---|"] + [
            f"| `{k}` | {v['zh']} {v['name']} | {tgt_zh[v['target']]} | {v['desc']}"
            + f" | {v['price']}" + (f"（*{v['src']}*）" if v.get("src") else "") + " |" for k, v in LO.ITEMS.items()]
        return (super().doc().replace("{{ARENA_HP_BONUS}}", str(ARENA_HP_BONUS)).replace("{{TRAVELERS_TABLE}}", travelers)
                .replace("{{JOBS_TABLE}}", "\n".join(jobs)).replace("{{SUPPORTS_TABLE}}", "\n".join(sups))
                .replace("{{ITEMS_TABLE}}", "\n".join(items)).replace("{{ITEMS_NOTE}}", LO.ITEMS_NOTE)
                .replace('"gold": GOLD', f'"gold": {LO.BUDGET["gold"]}')
                .replace("{{SKILLS_TABLE}}", skills).replace("{{CONCOCT_TABLE}}", concoct))

    def __init__(self, seed: int = 0, **options: Any):
        super().__init__(seed, **options)
        unknown = set(options) - set(DEFAULTS) - set(ESTIMATED)
        if unknown:
            raise ValueError(f"未知的 octopath 参数: {sorted(unknown)}")
        self.cfg = {**DEFAULTS, **{k: v for k, v in options.items() if k in DEFAULTS}}
        self.overrides = {k: v for k, v in options.items() if k in ESTIMATED}
        self.cfg["loadout"] = str(self.cfg["loadout"]).lower() not in ("0", "false", "off", "no")
        if self.cfg["pick_mode"] not in ("blind", "draft"):
            raise ValueError("pick_mode 只能是 blind 或 draft")
        self.team_size = int(self.cfg["team_size"])
        if not 1 <= self.team_size <= (4 if self.cfg["pick_mode"] == "draft" else 8):
            raise ValueError("team_size 超出范围")
        self.rng = random.Random(seed)
        self._tick = 0
        self.picks: list[list[str]] = [[], []]
        self.loadouts: list[list[dict]] | None = None   # 配置阶段结束后：每队每人一份规范化后的配置
        self.loadout_log: list[dict] = []
        self.bags: list[dict] = [{}, {}]               # 配置阶段买的道具（开战时的道具袋）
        self.battle: Battle | None = None
        self.last_events: list[dict] = []
        self.last_action = None
        self.last_actor = None
        self.pick_log: list[dict] = []
        self.fallbacks = [0, 0]

    @classmethod
    def match_rules(cls):
        return {"strict": True, "cpu_budget": True, "tick_limit_ms": 1000, "memory_mb": 256}

    def official_time_budget_ms(self):
        return 60000

    @classmethod
    def official_tick_limit_ms(cls):
        return 1000

    def action_errors(self, player, msg):
        if player not in self.to_move():
            return []
        if self.phase == "pick":
            need = self.team_size if self.cfg["pick_mode"] == "blind" else 1
            return [] if self._valid_pick(player, msg, need) is not None else ["选人名单不合法"]
        if self.phase == "loadout":
            lo = msg.get("loadout")
            if not isinstance(lo, (list, dict)):
                return ["loadout 必须为数组或对象；允许空数组表示不配置"]
            entries = lo.values() if isinstance(lo, dict) else lo
            for entry in entries:
                if not isinstance(entry, dict):
                    return ["每份配置必须为对象"]
                if "sub_job" in entry and entry["sub_job"] is not None and not isinstance(entry["sub_job"], str):
                    return ["sub_job 必须为字符串或 null"]
                for field in ("learn", "supports"):
                    if field in entry and (not isinstance(entry[field], list) or any(not isinstance(x, str) for x in entry[field])):
                        return [field + " 必须为字符串数组"]
            bag = msg.get("items", {})
            if not isinstance(bag, dict) or any(type(v) is not int or v < 0 for v in bag.values()):
                return ["items 必须为道具 ID 到非负整数数量的对象"]
            return []
        act = msg.get("action")
        if not isinstance(act, dict):
            return ["action 必须为对象"]
        fields = {"skill", "boost", "target", "targets", "latent", "weapon", "recipe", "item"}
        if set(act) - fields:
            return ["action 包含未定义字段"]
        for field in ("skill", "weapon", "recipe", "item"):
            if field in act and not isinstance(act[field], str):
                return [field + " 必须为字符串"]
        if "latent" in act and type(act["latent"]) is not bool:
            return ["latent 必须为布尔值"]
        if "boost" in act and type(act["boost"]) is not int:
            return ["boost 必须为整数"]
        if "target" in act and act["target"] is not None and type(act["target"]) is not int:
            return ["target 必须为整数或 null"]
        if "targets" in act and (not isinstance(act["targets"], list) or any(type(x) is not int for x in act["targets"])):
            return ["targets 必须为整数数组"]
        return []

    # ---------------- 基本 ----------------
    @property
    def tick(self) -> int:
        return self._tick

    @property
    def phase(self) -> str:
        if self.battle is None:
            return "loadout" if self._picks_done() else "pick"
        return "over" if self.battle.over else "battle"

    def is_over(self) -> bool:
        return self.battle is not None and self.battle.over

    def scores(self) -> list[float]:
        if not self.is_over():
            return [0, 0]
        w = self.battle.winner
        return [0.5, 0.5] if w == -1 else [1 if w == 0 else 0, 1 if w == 1 else 0]

    def _picks_done(self) -> bool:
        return all(len(x) == self.team_size for x in self.picks)

    def _picker(self) -> list[int]:
        if self.cfg["pick_mode"] == "blind":
            return [0, 1]
        n = len(self.picks[0]) + len(self.picks[1])
        return [DRAFT_ORDER[n]]

    def to_move(self) -> list[int]:
        if self.battle is None:
            return [0, 1] if self._picks_done() else self._picker()
        if self.battle.over or self.battle.current is None:
            return []
        return [self.battle.current.team]

    # ---------------- 协议 ----------------
    def init_message(self, player: int) -> dict:
        travelers = {}
        for k, t in TRAVELERS.items():
            travelers[k] = {**t, "skills": TRAVELER_SKILLS[k], "latent_power": {"name": LATENT[k][0], "desc": LATENT[k][1]},
                            "latent_skills": [s for s, v in LATENT_SKILLS.items() if v["job"] == k]}
        skills = {k: {kk: vv for kk, vv in v.items()} for k, v in {**SKILLS, **LATENT_SKILLS}.items()}
        return {
            "game": self.name,
            "you": player,
            "team_size": self.team_size,
            "pick_mode": self.cfg["pick_mode"],
            "max_rounds": int(self.cfg["max_rounds"]),
            "max_bp": MAX_BP, "max_boost": MAX_BOOST,
            "arena_rules": {"hp_bonus": ARENA_HP_BONUS, "hp_bonus_order": "after_loadout", "divine_first_round": True},
            "travelers": travelers,
            "skills": skills,
            "concoct_recipes": CONCOCT,
            "types": TYPES,
            "constants": {**ESTIMATED, **self.overrides},
            "loadout_enabled": bool(self.cfg["loadout"]),
            "loadout_rules": LO.info(),
        }

    def observe(self, player: int) -> dict:
        mine = player in self.to_move()
        if self.battle is None and self._picks_done():
            return {
                "phase": "loadout", "your_turn": True,
                "my_picks": list(self.picks[player]),
                # 盲配：只有轮流选人（draft）时才知道对手是谁；对手的配置战斗开始时才公开
                "opponent_picks": list(self.picks[1 - player]) if self.cfg["pick_mode"] == "draft" else [],
                "budget": dict(LO.BUDGET),
            }
        if self.battle is None:
            taken = set(self.picks[1 - player]) if self.cfg["pick_mode"] == "draft" else set()
            need = self.team_size if self.cfg["pick_mode"] == "blind" else 1
            return {
                "phase": "pick", "your_turn": mine, "pick_count": need if mine else 0,
                "pick_mode": self.cfg["pick_mode"],
                "available": [k for k in TRAVELERS if k not in taken and k not in self.picks[player]],
                "my_picks": list(self.picks[player]),
                "opponent_picks": list(self.picks[1 - player]) if self.cfg["pick_mode"] == "draft" else [],
            }
        b = self.battle
        cur = b.current
        obs = {
            "phase": "battle",
            "round": b.round,
            "your_turn": mine,
            "actor": cur.id if (mine and cur) else None,
            "me": [b.unit_view(u) for u in b.teams[player]],
            "opponents": [b.unit_view(u) for u in b.teams[1 - player]],
            "current": [cur.team ^ player, cur.id] if cur else None,
            "queue": [[u.team ^ player, u.id] for u, _ in b.queue if u.alive and not u.broken],
            "next_round_order": [[u.team ^ player, u.id] for u in b.predicted_order()],
            "last_events": _rel(self.last_events, player),
            "my_items": dict(b.bags[player]),
            "opponent_items": dict(b.bags[1 - player]),
        }
        if mine and cur:
            obs["available_skills"] = [
                {"id": s, "sp": (SKILLS.get(s) or LATENT_SKILLS.get(s) or {}).get("sp", 0),
                 "usable": b.usable(cur, s, latent=True)}
                for s in b.skill_list(cur)
            ]
            obs["usable_items"] = [k for k in b.bags[player] if b.item_usable(cur, k)]
        return obs

    # ---------------- 推进 ----------------
    def _valid_pick(self, player: int, msg, need: int) -> list[str] | None:
        p = msg.get("pick") if isinstance(msg, dict) else None
        if isinstance(p, str):
            p = [p]
        if not isinstance(p, list) or len(p) != need:
            return None
        taken = set(self.picks[1 - player]) if self.cfg["pick_mode"] == "draft" else set()
        out = []
        for k in p:
            if not isinstance(k, str):
                return None
            k = k.lower()
            if k not in TRAVELERS or k in taken or k in out or k in self.picks[player]:
                return None
            out.append(k)
        return out

    def step(self, actions: list[Any]) -> None:
        self.last_events = []
        self.last_action = None
        self.last_actor = None
        if self.battle is None and not self._picks_done():
            need = self.team_size if self.cfg["pick_mode"] == "blind" else 1
            for p in self._picker():
                got = self._valid_pick(p, actions[p], need)
                auto = got is None
                if auto:
                    self.fallbacks[p] += 1
                    taken = set(self.picks[1 - p]) if self.cfg["pick_mode"] == "draft" else set()
                    pool = [k for k in TRAVELERS if k not in taken and k not in self.picks[p]]
                    got = self.rng.sample(pool, need)
                self.picks[p] += got
                self.pick_log.append({"team": p, "picks": got, "auto": auto})
                self.last_events.append({"e": "pick", "team": p, "picks": got, "auto": int(auto)})
            if self._picks_done() and not self.cfg["loadout"]:
                self.loadouts = [[LO.empty() for _ in p] for p in self.picks]
                self._start_battle()
        elif self.battle is None:
            self.loadouts = [[], []]
            for p in (0, 1):
                msg = actions[p].get("loadout") if isinstance(actions[p], dict) else None
                lo, notes = LO.validate(self.picks[p], msg)
                bag, inotes = LO.validate_items(actions[p].get("items") if isinstance(actions[p], dict) else None)
                notes += inotes
                self.bags[p] = bag
                if msg is None:
                    self.fallbacks[p] += 1
                self.loadouts[p] = lo
                self.loadout_log.append({"team": p, "missing": int(msg is None), "notes": notes, "items": bag})
                self.last_events.append({"e": "loadout", "team": p, "notes": notes})
            self._start_battle()
        else:
            b = self.battle
            cur = b.current
            msg = actions[cur.team]
            act = msg.get("action") if isinstance(msg, dict) else None
            if not isinstance(act, dict):
                self.fallbacks[cur.team] += 1
                act = None
            self.last_actor = cur.ref()
            self.last_action = b.act(act)
            if self.last_action.get("fallback"):
                self.fallbacks[cur.team] += 1
            self.last_events = b.events
        self._tick += 1

    def _start_battle(self):
        self.battle = Battle(self.picks, self.rng, max_rounds=int(self.cfg["max_rounds"]), loadouts=self.loadouts,
                             bags=self.bags, **self.overrides)
        self.last_events += self.battle.events

    # ---------------- 回放 ----------------
    def frame(self) -> dict:
        f = {"t": self._tick, "ev": self.last_events}
        if self.battle is None:
            f["picks"] = [list(p) for p in self.picks]
            return f
        b = self.battle
        f["r"] = b.round
        f["u"] = [[[x.hp, x.sp, x.bp, x.shields, int(x.broken), int(x.alive), int(x.latent),
                    [[k, v] for k, v in sorted(x.up.items())], [[k, v] for k, v in sorted(x.down.items())],
                    [[k, v] for k, v in sorted(x.st.items())], x.tier[0] if x.tier[1] else 1,
                    x.materials if x.key == "castti" else -1]
                   for x in team] for team in b.teams]
        f["q"] = [u.ref() for u, _ in b.queue if u.alive and not u.broken]
        f["bag"] = [dict(x) for x in b.bags]
        if b.current is not None:
            f["cur"] = b.current.ref()
        if self.last_action is not None:
            f["a"] = {"u": self.last_actor, **self.last_action}
        if b.over:
            f["win"] = b.winner
        return f

    def replay_meta(self) -> dict:
        # x: 1 = 神技，2 = 潜力技（回放里用更华丽的技能特写）
        names = {k: {"name": v["name"], "zh": v["zh"], **({"x": 1} if v.get("divine") else {})} for k, v in SKILLS.items()}
        names.update({k: {"name": v["name"], "zh": v["zh"], "x": 2} for k, v in LATENT_SKILLS.items()})
        names["attack"] = {"name": "Attack", "zh": "攻击"}
        names["defend"] = {"name": "Defend", "zh": "防御"}
        names["concoct"] = {"name": "Concoct", "zh": "调合"}
        names["item"] = {"name": "Item", "zh": "道具"}
        return {
            "picks": [list(p) for p in self.picks],
            "arena_rules": {"hp_bonus": ARENA_HP_BONUS, "hp_bonus_order": "after_loadout", "divine_first_round": True},
            "loadouts": self.loadouts,
            "unit_max": [[[u.max_hp, u.max_sp] for u in t] for t in self.battle.teams] if self.battle else None,
            "loadout_log": self.loadout_log,
            "supports": {k: {"name": v["name"], "zh": v["zh"], "desc": v["desc"]} for k, v in LO.SUPPORTS.items()},
            "jobs_zh": LO.JOB_ZH,
            "items": {k: {"name": v["name"], "zh": v["zh"], "desc": v["desc"], "fx": v["fx"], "target": v["target"]}
                      for k, v in LO.ITEMS.items()},
            "bags": self.bags,
            "pick_mode": self.cfg["pick_mode"],
            "pick_log": self.pick_log,
            "travelers": {k: {f: v[f] for f in ("name", "job", "job_en", "hp", "sp", "shields", "weak", "weapons")}
                          for k, v in TRAVELERS.items()},
            "latent": {k: v[0] for k, v in LATENT.items()},
            "skills": names,
            "recipes": {k: v["zh"] for k, v in CONCOCT.items()},
            "type_zh": TYPE_ZH,
            "fallbacks": self.fallbacks,
            "max_rounds": int(self.cfg["max_rounds"]),
        }

    @staticmethod
    def render_html(replay: dict) -> str:
        from .viewer import render
        return render(replay)
