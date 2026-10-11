"""八方旅人 II 风格的回合制队伍对战引擎（纯逻辑，不涉及进程通信）。

一个"决策"= 某个角色的一次行动。引擎维护本回合的行动队列，按速度排序；
每次 act() 结算一个行动，然后自动推进到下一个需要做决策的角色（中间处理回合开始/结束）。
"""
from __future__ import annotations

import random
import math

from .data import ARENA_HP_BONUS, VERIFIED_VALUES, CONCOCT, ESTIMATED, JOB_SKILLS, LATENT_SKILLS, SKILLS, TRAVELERS, TRAVELER_SKILLS
from .loadout import ITEMS, JOB_WEAPONS, apply_stats, empty, free_skills

STATS = ["pa", "pd", "ea", "ed", "spd", "crit", "acc", "eva"]
MAX_BP = 5
MAX_BOOST = 3
DMG_CAP = 9999


class Unit:
    def __init__(self, team: int, uid: int, key: str, materials: int, lo: dict | None = None):
        t = TRAVELERS[key]
        lo = lo or empty()
        self.lo = lo
        self.team, self.id, self.key = team, uid, key
        self.name = t["name"]
        st = apply_stats(key, lo)
        self.base = {s: st[s] for s in STATS}
        self.max_hp, self.max_sp = st["hp"] + ARENA_HP_BONUS, st["sp"]
        self.hp, self.sp = self.max_hp, self.max_sp
        self.sup = set(lo.get("supports") or [])
        self.bp = 2 if "boost_start" in self.sup else 1
        self.max_shields = t["shields"]
        self.shields = self.max_shields
        self.weak = list(t["weak"])
        self.weapons = list(t["weapons"])
        self.sub_job = lo.get("sub_job")
        self.skills = list(TRAVELER_SKILLS[key])
        if self.sub_job:
            self.weapons += [w for w in JOB_WEAPONS[self.sub_job] if w not in self.weapons]
            known = set(free_skills(self.sub_job)) | set(lo.get("learn") or [])
            self.skills += [s for s in JOB_SKILLS[self.sub_job] if s in known]
        self.rise = "rise_again" in self.sup
        self.alive = True
        self.broken = False
        self.recover_round = 0
        self.up: dict[str, int] = {}     # 属性上升剩余回合
        self.down: dict[str, int] = {}   # 属性下降剩余回合
        self.st: dict[str, int] = {}     # 其他状态：剩余回合或次数
        self.latent_capacity = 125 if key in ("ochette","agnea","temenos","hikari") else 100
        self.latent = 100.0 if "full_power" in self.sup else 0.0
        self.materials = materials if key == "castti" else 0
        self.boosted_this_round = False
        self.defending = False
        self.first_next = False
        self.stim = 0
        self.tier = [1, 0]               # [魔法阶数, 剩余次数]
        if "preventative_measures" in self.sup:
            self.st["ward"] = 3

    def ref(self):
        return [self.team, self.id]

    def stat(self, s: str, cfg) -> float:
        v = float(self.base[s])
        if self.up.get(s):
            v *= cfg["buff_mult"]
        if self.down.get(s):
            v *= cfg["debuff_mult"]
        return v


POSITIVE_STATUSES = ["counter", "sidestep", "sacred", "regen", "immune", "taunt", "extra", "spread", "charity"]


class Battle:
    def __init__(self, picks: list[list[str]], rng: random.Random, max_rounds: int = 30,
                 loadouts: list[list[dict]] | None = None, bags: list[dict] | None = None, **overrides):
        self.cfg = {**ESTIMATED, **{k: v for k, v in overrides.items() if k in ESTIMATED}}
        self.rng = rng
        self.max_rounds = max_rounds
        lo = loadouts or [[None] * len(p) for p in picks]
        self.teams = [[Unit(t, i, k, int(self.cfg["materials"]), lo[t][i]) for i, k in enumerate(p)]
                      for t, p in enumerate(picks)]
        self.bags = [dict(b) for b in (bags or [{}, {}])]   # 每队的道具袋 {道具 id: 剩余个数}
        self.round = 0
        self.queue: list[tuple[Unit, str]] = []   # (单位, 行动类型 normal/extra)
        self.acted_order = 0                      # 本回合已经行动的人数（奇袭用）
        self.current: Unit | None = None
        self.current_kind = "normal"
        self.winner: int | None = None            # 0/1，平局 -1
        self.over = False
        self.events: list[dict] = []
        self.pending_double: Unit | None = None
        self.pending_kind = "double"
        self._src: Unit | None = None             # 当前行动者（支援技能"强化回合数增加"等用）
        self._extras_done = False
        self.hien_round = set()
        self.hien_pending = []
        self._start_round()
        self._advance()

    # ------------------------------------------------------------------ 工具
    def units(self):
        return self.teams[0] + self.teams[1]

    def alive(self, team: int):
        return [u for u in self.teams[team] if u.alive]

    def ev(self, **e):
        self.events.append(e)

    def predicted_order(self) -> list[Unit]:
        """下回合的预计顺序（不含随机浮动，只按当前速度和优先级）。"""
        cand = [u for u in self.units() if u.alive and (not u.broken or u.recover_round <= self.round + 1)]
        return sorted(cand, key=lambda u: (self._group(u), -u.stat("spd", self.cfg), u.team, u.id))

    def _group(self, u: Unit) -> int:
        if u.first_next:
            return 0
        if u.st.get("leghold"):
            return 2
        return 1

    # ------------------------------------------------------------------ 回合流程
    def _start_round(self):
        self.round += 1
        self.acted_order = 0
        self.ev(e="round", r=self.round)
        for u in self.units():
            if u.alive and u.broken and u.recover_round <= self.round:
                u.broken = False
                u.shields = u.max_shields
                self.ev(e="recover", t=u.ref())
            if self.round > 1 and u.alive and not u.broken:
                # 上一回合用过加成的角色本回合不回复 BP（原作规则）
                if not u.boosted_this_round and u.bp < MAX_BP:
                    u.bp += 1
            u.boosted_this_round = False
        cand = [u for u in self.units() if u.alive and not u.broken]
        j = self.cfg["speed_jitter"]
        keyed = []
        for u in cand:
            spd = u.stat("spd", self.cfg) * (1 + self.rng.uniform(-j, j))
            keyed.append(((self._group(u), -spd), u))
        keyed.sort(key=lambda x: x[0])
        order = [u for _, u in keyed]
        for u in list(order):
            if u.stim:
                i = order.index(u)
                order.pop(i)
                order.insert(max(0, i - u.stim), u)
                u.stim = 0
        for u in order:
            u.first_next = False
        self.round_action_count = len(order)
        self.queue = [(u, "normal") for u in order]
        self.ev(e="order", o=[u.ref() for u in order])

    def _end_round(self):
        # 艾尔弗里克的祝福：回合末额外行动
        extras = [u for u in self.units() if u.alive and not u.broken and u.st.get("extra")]
        if extras and not self._extras_done:
            self._extras_done = True
            for u in extras:
                u.st["extra"] -= 1
                if u.st["extra"] <= 0:
                    del u.st["extra"]
            self.queue = [(u, "extra") for u in extras]
            return False
        pending = [x for x in self.hien_pending if x.alive and not x.broken]
        self.hien_pending = []
        if pending:
            self.queue = [(x, "hien") for x in pending]
            return False
        if self.round >= self.max_rounds:
            self._finish_by_hp()
            return True
        self._extras_done = False
        self._start_round()
        return False

    def _finish_by_hp(self):
        score = [sum(u.hp / u.max_hp for u in self.teams[t]) for t in (0, 1)]
        self.over = True
        if abs(score[0] - score[1]) < 1e-9:
            self.winner = -1
        else:
            self.winner = 0 if score[0] > score[1] else 1
        self.ev(e="end", winner=self.winner, reason="rounds", hp=[round(s, 3) for s in score])

    def _check_win(self) -> bool:
        a0, a1 = bool(self.alive(0)), bool(self.alive(1))
        if a0 and a1:
            return False
        self.over = True
        self.winner = -1 if (not a0 and not a1) else (0 if a0 else 1)
        self.ev(e="end", winner=self.winner, reason="ko")
        return True

    def _advance(self):
        """找到下一个要行动的角色。"""
        self.current = None
        while not self.over:
            if self.pending_double is not None:
                u = self.pending_double
                self.pending_double = None
                if u.alive and not u.broken:
                    self.current, self.current_kind = u, self.pending_kind
                    return
            while self.queue:
                u, kind = self.queue.pop(0)
                if u.alive and not u.broken:
                    self.current, self.current_kind = u, kind
                    return
            if self._end_round():
                return

    # ------------------------------------------------------------------ 行动合法性
    def skill_list(self, u: Unit) -> list[str]:
        return ["attack", "defend"] + u.skills + (["concoct"] if u.key == "castti" else []) + \
            [k for k, s in LATENT_SKILLS.items() if s["job"] == u.key] + (["item"] if self.bags[u.team] else [])

    def usable(self, u: Unit, sid: str, latent: bool = False) -> bool:
        if sid in ("attack", "defend"):
            return True
        if sid == "item":
            return any(self.item_usable(u, k) for k in self.bags[u.team])
        if sid == "concoct":
            return u.key == "castti" and (u.materials > 0 or (latent and u.latent >= 100))
        if sid in LATENT_SKILLS:
            return LATENT_SKILLS[sid]["job"] == u.key and latent and u.latent >= 100
        if sid not in u.skills:
            return False
        if SKILLS[sid].get("divine"):
            # 神技必须以最大加成（3 BP）发动（原作规则）；商人潜力会先把 BP 补满
            bp_ok = u.bp >= MAX_BOOST or (latent and u.key == "partitio" and u.latent >= 100)
            if not bp_ok:
                return False
        return u.sp >= SKILLS[sid]["sp"]

    def item_usable(self, u: Unit, iid) -> bool:
        if not isinstance(iid, str) or self.bags[u.team].get(iid, 0) <= 0:
            return False
        if ITEMS[iid]["target"] == "ko":
            return any(not x.alive for x in self.teams[u.team])
        return True

    # ------------------------------------------------------------------ 主入口
    def act(self, action: dict | None) -> dict:
        """结算当前角色的行动；返回实际执行的（规范化后的）行动。"""
        u = self.current
        assert u is not None and not self.over
        self.events = []
        a = action if isinstance(action, dict) else {}
        sid = a.get("skill", "attack")
        if not isinstance(sid, str):
            sid = "attack"
        want_latent = bool(a.get("latent")) and u.latent >= 100
        fallback = False
        if not self.usable(u, sid, want_latent) or (sid == "item" and not self.item_usable(u, a.get("item"))):
            sid, fallback = "attack", True
        try:
            boost = int(a.get("boost", 0) or 0)
        except (TypeError, ValueError):
            boost = 0
        boost = max(0, min(MAX_BOOST, boost))

        self.ev(e="turn", u=u.ref(), kind=self.current_kind)
        u.defending = False
        self._src = u
        self._boost = 0
        self._inspired: set = set()

        # 潜力
        flags = set()
        if want_latent:
            u.latent = 0.0
            self.ev(e="latent", u=u.ref(), name=u.key)
            if u.key == "partitio":
                u.bp = MAX_BP
                self.ev(e="bp", t=u.ref(), v=u.bp)
            elif u.key == "throne":
                self.pending_double, self.pending_kind = u, "double"
            else:
                flags.add(u.key)

        spec = SKILLS.get(sid) or LATENT_SKILLS.get(sid)
        if spec and spec.get("divine"):
            boost = MAX_BOOST
        elif spec and not spec.get("boost"):
            boost = 0
        if sid in ("defend", "item"):
            boost = 0   # 道具不能增幅（原作规则）
        boost = min(boost, u.bp)
        if sid == "concoct" and "castti" in flags:
            boost = 0  # 潜力调合按最大加成生效，不花 BP
        self._boost = boost
        if boost:
            u.bp -= boost
            u.boosted_this_round = True
            self.ev(e="boost", u=u.ref(), n=boost)
        if sid == "concoct" and "castti" in flags:
            boost = MAX_BOOST

        self._dodged: set = set()
        self._phys_taken: dict = {}
        target = a.get("target")
        if not isinstance(target, int) or isinstance(target, bool):
            target = None
        tl = a.get("targets")
        self._targets = [x for x in tl if isinstance(x, int) and not isinstance(x, bool)][:8] if isinstance(tl, list) else []
        norm = {"skill": sid, "boost": boost, "target": target, "latent": want_latent}
        if fallback:
            norm["fallback"] = True

        if sid == "attack":
            w = a.get("weapon") if a.get("weapon") in u.weapons else u.weapons[0]
            norm["weapon"] = w
            self.ev(e="skill", u=u.ref(), s="attack", w=w)
            targets = self._enemy_targets(u, target, spread="agnea" in flags or bool(u.st.get("spread")))
            self._attack_hits(u, targets, {"kind": "phys", "type": w, "power": 1.0, "hits": 1 + boost}, flags)
        elif sid == "defend":
            u.defending = True
            u.first_next = True
            self.ev(e="skill", u=u.ref(), s="defend")
        elif sid == "item":
            iid = a["item"]
            norm["item"] = iid
            bag = self.bags[u.team]
            bag[iid] -= 1
            if bag[iid] <= 0:
                del bag[iid]
            self.ev(e="skill", u=u.ref(), s="item", it=iid)
            self._item(u, iid, target)
        elif sid == "concoct":
            recipe = a.get("recipe") if a.get("recipe") in CONCOCT else "elixir"
            norm["recipe"] = recipe
            if "castti" not in flags:
                u.materials -= 1
            self.ev(e="skill", u=u.ref(), s="concoct", r=recipe)
            self._concoct(u, recipe, boost, target)
        else:
            if spec.get("sp"):
                u.sp -= spec["sp"]
            self.ev(e="skill", u=u.ref(), s=sid)
            self._skill(u, sid, spec, boost, target, flags)
            # 支援技能「顺便战斗」：不造成伤害的技能后 50% 追加一次普通攻击
            if "kind" not in spec and "incidental_attack" in u.sup and u.alive and self.alive(1 - u.team) \
                    and self.rng.random() < 0.5:
                self.ev(e="sup", u=u.ref(), k="incidental_attack")
                w = u.weapons[0]
                self.ev(e="skill", u=u.ref(), s="attack", w=w)
                foe = target if spec["target"] in ("enemy", "chosen") else None
                self._attack_hits(u, self._enemy_targets(u, foe), {"kind": "phys", "type": w, "power": 1.0,
                                                                     "hits": 1}, set())

        # 反击：本次行动中受到物理伤害的角色各反击一次
        for t, dmg in list(self._phys_taken.values()):
            if t.alive and dmg > 0 and t.st.get("counter") and u.alive:
                t.st["counter"] -= 1
                if t.st["counter"] <= 0:
                    del t.st["counter"]
                self.ev(e="counter", u=t.ref(), t=u.ref())
                self._hit(t, u, "phys", "sword", 1.0, {"temenos"}, {"invocation":2,"ratio":1.5,"hit_ratio":20}, set())
        # 行动后：持续恢复、中毒、状态回合数递减
        if u.alive:
            if u.st.get("regen"):
                self._heal(u, u.max_hp * self.cfg["regen_pct"])
            if u.st.get("poison"):
                pct = self.cfg["poison_pct"]
                d = int(u.max_hp * pct)
                u.hp -= d
                self.ev(e="poison", t=u.ref(), d=d)
                if u.hp > 0 and u.st.get("poison_weak") and not u.broken:
                    self._reduce_shields(None, u, 1)
                if u.hp <= 0:
                    self._ko(u)
            self._tick_durations(u)
            self._gain_latent(u, self.cfg["latent_per_action"])
        self.acted_order += 1
        self._check_win()
        if not self.over:
            self._advance()
        return norm

    def _gain_latent(self, u: Unit, amount: float):
        if "latent_power_plus" in u.sup:
            amount *= 1.2
        u.latent = min(100.0, u.latent + amount * 100 / u.latent_capacity)

    def _tick_durations(self, u: Unit):
        for d in (u.up, u.down):
            for k in list(d):
                d[k] -= 1
                if d[k] <= 0:
                    del d[k]
        for k in ("poison", "poison_weak", "immune", "taunt", "regen", "leghold", "spread", "charity"):
            if u.st.get(k):
                u.st[k] -= 1
                if u.st[k] <= 0:
                    del u.st[k]

    # ------------------------------------------------------------------ 目标
    def _enemy_targets(self, u: Unit, target, spread=False) -> list[Unit]:
        foes = self.alive(1 - u.team)
        if not foes:
            return []
        if spread:
            return foes
        taunters = [f for f in foes if f.st.get("taunt")]
        if taunters:
            return [taunters[0]]
        for f in foes:
            if f.id == target:
                return [f]
        return [foes[0]]

    def _ally_target(self, u: Unit, target, allow_ko=False, other=False) -> Unit | None:
        team = self.teams[u.team]
        cands = [x for x in team if (allow_ko or x.alive) and not (other and x is u)]
        for x in cands:
            if x.id == target:
                return x
        if not cands:
            return None
        if allow_ko:
            ko = [x for x in cands if not x.alive]
            if ko:
                return ko[0]
        if other:
            return cands[0]
        return u if u in cands else cands[0]

    # ------------------------------------------------------------------ 伤害
    def _hit(self, src: Unit, dst: Unit, kind: str, typ, power: float, flags: set, extra: dict | None = None,
             dodged: set | None = None) -> int:
        extra = extra or {}
        cfg = self.cfg
        if not dst.alive:
            return 0
        if kind == "phys":
            if dodged is not None and dst.id in dodged:
                self.ev(e="hit", u=src.ref(), t=dst.ref(), d=0, ty=typ, miss=1)
                return 0
            if dst.st.get("sidestep"):
                dst.st["sidestep"] -= 1
                if dst.st["sidestep"] <= 0:
                    del dst.st["sidestep"]
                if dodged is not None:
                    dodged.add(dst.id)
                self.ev(e="hit", u=src.ref(), t=dst.ref(), d=0, ty=typ, miss=1, dodge=1)
                return 0
            hit_ratio = extra.get("hit_ratio", 20 if "invocation" not in extra and power == 1 else 0)
            hit_pct = 50 * (3 - dst.stat("eva", cfg) / max(1, src.stat("acc", cfg))) + hit_ratio
            miss = 1 - max(0.2, min(1.0, round(hit_pct, 3) / 100))
            if "ever_evasive" in dst.sup:
                miss += 0.20
            if not dst.broken and self.rng.random() < miss:
                self.ev(e="hit", u=src.ref(), t=dst.ref(), d=0, ty=typ, miss=1)
                return 0
            atk = float(src.base["pa"])
            df = float(dst.base["pd"])
        else:
            atk, df = float(src.base["ea"]), float(dst.base["ed"])
        if extra.get("fixed"):
            dmg = extra["fixed"] * self.rng.uniform(0.95, 1.05)   # 道具：固定伤害，不看双方属性
        else:
            invocation = extra.get("invocation", 1.0)
            ratio = extra.get("ratio", 0.8 if power == 1.0 else power)
            dmg = (min(999, atk) * invocation - min(999, df) / 2) * ratio * cfg["level_multiplier"]
            at, de = ("pa", "pd") if kind == "phys" else ("ea", "ed")
            if src.up.get(at): dmg *= 1.5
            if src.down.get(at): dmg *= 2 / 3
            if dst.down.get(de): dmg *= 1.5
            if dst.up.get(de): dmg *= 2 / 3
            dmg *= extra.get("damage_bonus", 1.0)
            dmg *= self.rng.uniform(cfg["damage_random_min"], cfg["damage_random_max"])
        weak = typ is not None and typ in dst.weak
        fixed = bool(extra.get("fixed"))   # 道具的固定伤害不乘弱点、击破、防御倍率（打中弱点照样削盾）
        if weak and not dst.broken and not fixed:
            dmg *= cfg["weak_mult"]
        crit = False
        if kind == "phys":
            cc = extra.get("crit_chance")
            if cc is None:
                cc = max(0, min(1, (src.stat("crit", cfg) - dst.stat("spd", cfg)) / 200))
            if self.rng.random() < cc:
                crit = True
                dmg *= extra.get("crit_mult", cfg["crit_mult"])
        if dst.broken and not fixed:
            dmg *= cfg["break_mult"]
        if dst.defending and not fixed:
            dmg *= cfg["defend_mult"]
        dmg = max(1, dmg)
        if dst.st.get("sacred"):
            dmg *= (100 - dst.st.pop("sacred")) / 100
        dmg = int(max(0, min((99999 if "deal_more_damage" in src.sup else DMG_CAP), dmg)))
        before = dst.hp
        dst.hp -= dmg
        if extra.get("mercy") and dst.hp <= 0:
            dst.hp = 1
        tough = dst.hp <= 0 and "hang_tough" in dst.sup and before >= dst.max_hp * 0.25
        e = {"e": "hit", "u": src.ref(), "t": dst.ref(), "d": dmg, "ty": typ}
        if weak:
            e["w"] = 1
        if crit:
            e["c"] = 1
        self.events.append(e)
        if tough:
            dst.hp = 1
            self.ev(e="sup", u=dst.ref(), k="hang_tough")
        self._gain_latent(dst, math.floor(min(dmg, before) / dst.max_hp * cfg["latent_per_dmg"]))
        shield_hits = (1 if (weak or "temenos" in flags) else 0) + extra.get("shield_break", 0)
        if kind == "phys" and dmg > 0 and dst.hp > 0 and "ensnare" in dst.sup and src.alive \
                and self.rng.random() < 0.5:
            self.ev(e="sup", u=dst.ref(), k="ensnare")
            self._buff(src, self.rng.choice(["pa", "pd", "ea", "ed", "spd"]), 2, up=False)
        if dst.hp <= 0:
            self._ko(dst)
        elif shield_hits and not dst.broken:
            self._reduce_shields(src, dst, shield_hits)
        return dmg

    def _reduce_shields(self, src: Unit, dst: Unit, n: int):
        dst.shields = max(0, dst.shields - n)
        self.ev(e="shield", t=dst.ref(), v=dst.shields)
        if dst.shields == 0:
            dst.broken = True
            dst.recover_round = self.round + 2
            dst.defending = False
            self.queue = [(x, k) for x, k in self.queue if x is not dst]
            if self.pending_double is dst:
                self.pending_double = None
            if src is not None:
                self._gain_latent(src, self.cfg["latent_per_break"])
            self.ev(e="break", t=dst.ref())
            if src is not None and src.alive:
                self._break_supports(src)

    def _break_supports(self, src: Unit):
        if "bolstering_break" in src.sup:
            self.ev(e="sup", u=src.ref(), k="bolstering_break")
            self._buff(src, "pa", 2)
        if "inspiriting_break" in src.sup:
            gain = min(src.max_sp - src.sp, 20)
            src.sp += gain
            self.ev(e="sup", u=src.ref(), k="inspiriting_break")
            self.ev(e="sp", t=src.ref(), v=gain)
        if "salt_the_wound" in src.sup and src is self.current and self.current_kind != "salt" \
                and self.pending_double is None and not src.broken and self.rng.random() < 0.5:
            self.ev(e="sup", u=src.ref(), k="salt_the_wound")
            self.pending_double, self.pending_kind = src, "salt"

    def _ko(self, u: Unit):
        u.hp = 0
        u.alive = False
        u.broken = False
        u.bp = 0
        u.up.clear()
        u.down.clear()
        u.st.clear()
        u.defending = False
        u.tier = [1, 0]
        self.queue = [(x, k) for x, k in self.queue if x is not u]
        if self.pending_double is u:
            self.pending_double = None
        self.ev(e="ko", t=u.ref())
        if u.rise:
            u.rise = False
            self.ev(e="sup", u=u.ref(), k="rise_again")
            self._revive(u, u.max_hp * 0.25)

    def _attack_hits(self, u: Unit, targets: list[Unit], hit: dict, flags: set):
        dmg_by = {}
        for t in targets:
            for _ in range(hit.get("hits", 1)):
                d = self._hit(u, t, hit["kind"], hit["type"], hit["power"], flags, hit, self._dodged)
                dmg_by[id(t)] = dmg_by.get(id(t), 0) + d
                if hit["kind"] == "phys" and d > 0:
                    prev = self._phys_taken.get(id(t), (t, 0))[1]
                    self._phys_taken[id(t)] = (t, prev + d)
        return dmg_by

    # ------------------------------------------------------------------ 恢复与状态
    def _heal(self, t: Unit, amount: float):
        if not t.alive:
            return
        amount = int(min(DMG_CAP, amount))
        v = min(amount, t.max_hp - t.hp)
        t.hp += v
        self.ev(e="heal", t=t.ref(), v=v)

    def _revive(self, t: Unit, amount: float):
        if t.alive:
            return self._heal(t, amount)
        t.alive = True
        t.hp = max(1, min(t.max_hp, int(amount)))
        t.shields = t.max_shields
        t.broken = False
        self.ev(e="revive", t=t.ref(), v=t.hp)

    def _buff(self, t: Unit, stat: str, rounds: int, up=True):
        src = self._src
        if not up and t.st.get("ward"):
            t.st["ward"] -= 1
            if t.st["ward"] <= 0:
                del t.st["ward"]
            self.ev(e="status", t=t.ref(), k="ward", blocked=stat)
            return
        if up and src is not None and src.team == t.team:
            if "the_show_goes_on" in src.sup:
                rounds += 1
            if "invigorate_and_inspire" in src.sup and t.id not in self._inspired:
                self._inspired.add(t.id)
                self._gain_latent(t, 5 * (1 + self._boost))
        d = t.up if up else t.down
        d[stat] = max(d.get(stat, 0), rounds)
        self.ev(e="buff", t=t.ref(), st=stat, up=int(up), r=rounds)

    def _poison(self, src: Unit, t: Unit, rounds: int):
        if not t.alive:
            return
        if t.st.get("immune"):
            self.ev(e="status", t=t.ref(), k="immune")
            return
        t.st["poison"] = max(t.st.get("poison", 0), rounds)
        self.ev(e="status", t=t.ref(), k="poison", r=rounds)

    def _dispel(self, t: Unit, n: int | None = None) -> int:
        items = [("up", k) for k in list(t.up)] + [("st", k) for k in POSITIVE_STATUSES if t.st.get(k)]
        if t.tier[1] > 0:
            items.append(("tier", None))
        if n is not None:
            items = items[:n]
        for where, k in items:
            if where == "up":
                del t.up[k]
            elif where == "st":
                del t.st[k]
            else:
                t.tier = [1, 0]
        if items:
            self.ev(e="dispel", t=t.ref(), n=len(items))
        return len(items)

    # ------------------------------------------------------------------ 技能
    def _spell_tier(self, u: Unit, spec) -> int:
        if spec.get("spell") and u.tier[1] > 0:
            tier = u.tier[0]
            u.tier[1] -= 1
            if u.tier[1] <= 0:
                u.tier = [1, 0]
            return tier
        return 1

    def _skill(self, u: Unit, sid: str, spec: dict, boost: int, target, flags: set):
        cfg = self.cfg
        lv = boost  # 档位下标 0..3
        tgt_kind = spec["target"]
        spread = ("agnea" in flags or bool(u.st.get("spread"))) and not spec.get("divine")
        tier = self._spell_tier(u, spec)
        mult = 1 + boost if spec.get("boost") == "power" else 1

        # ---------- 伤害技能 ----------
        if "kind" in spec:
            hit = {"kind": spec["kind"], "type": spec["type"], "power": spec["power"] * mult,
                   "hits": spec.get("hits", 1), "mercy": spec.get("mercy"), "use_spd": spec.get("use_spd"),
                   "shield_break": spec.get("shield_break", 0)}
            rec = VERIFIED_VALUES.get(sid)
            if rec:
                row = rec["levels"][boost]
                damage = next((e for e in row["effects"] if "DAMAGE" in e["effect"] and "SP_DAMAGE" not in e["effect"]), None)
                if damage:
                    hit.update(invocation=damage["value"]/100, ratio=row["ratio"], crit_mult=row["crit"], hit_ratio=row["hit_ratio"])
                if rec.get("tiers"):
                    hit.update(rec["tiers"][tier-1][boost])
            if sid == "aebers_reckoning":
                hit["damage_bonus"] = 0.84 + u.stat("spd", cfg) / 500
            if sid == "surprise_attack":
                hit["damage_bonus"] = 2 - min(self.acted_order / max(1,self.round_action_count-1), 1)
            if spec.get("boost") == "crit":
                hit["crit_chance"] = spec["levels"][lv] / 100
            if tgt_kind == "chosen":
                n = spec["levels"][lv]
                picks = self._targets or ([target] if target is not None else [])
                for i in range(n):
                    want = picks[min(i, len(picks) - 1)] if picks else None
                    ts = self._enemy_targets(u, want)
                    if not ts:
                        break
                    self._attack_hits(u, ts, {**hit, "hits": 1}, flags)
                return
            if tgt_kind == "random":
                n = spec["levels"][lv]
                if isinstance(n, list):
                    n = self.rng.randint(n[0], n[1])
                if tier > 1:
                    hit["power"] *= 1 + 0.5 * (tier - 1) if not rec else 1
                total = 0
                for _ in range(n):
                    foes = self.alive(1 - u.team)
                    if not foes:
                        break
                    t = self.rng.choice(foes)
                    typ = self.rng.choice(["fire", "ice", "lightning"]) if spec["type"] == "random_fil" else spec["type"]
                    total += self._attack_hits(u, [t], {**hit, "type": typ, "hits": 1}, flags).get(id(t), 0)
                return
            if tgt_kind == "enemies":
                if "osvald" in flags and spec.get("spell"):
                    targets = self._enemy_targets(u, target)
                    hit["damage_bonus"] = hit.get("damage_bonus", 1) * 2
                else:
                    targets = self.alive(1 - u.team)
                if tier > 1:
                    hit["hits"] = hit["hits"] * tier
            else:
                targets = self._enemy_targets(u, target, spread=spread)
                if tier > 1:
                    hit["power"] *= 1 + 0.5 * (tier - 1) if not rec else 1
            if sid == "enervating_slash":
                factors = [1,1.75,2.25,2.75,3,3.25,3.5,3.65,3.8,3.9,4]
                dmg_by = {}
                for t in targets:
                    bonus = factors[min(10, self._dispel(t))]
                    dmg_by.update(self._attack_hits(u, [t], {**hit, "damage_bonus": bonus}, flags))
            elif sid == "sougetsu":
                dmg_by = self._attack_hits(u, targets, {**hit,"hits":1,"type":"sword"}, flags)
                for k,v in self._attack_hits(u, targets, {**hit,"hits":1,"type":"polearm"}, flags).items():
                    dmg_by[k] = dmg_by.get(k,0) + v
            else:
                dmg_by = self._attack_hits(u, targets, hit, flags)
            total = sum(dmg_by.values())
            if sid == "hp_thief":
                self._heal(u, total * 0.5)
            elif sid == "mystical_staff":
                gain = min(u.max_sp - u.sp, int(total * 0.1))
                u.sp += gain
                self.ev(e="sp", t=u.ref(), v=gain)
            elif sid == "poison_axe":
                for t in targets:
                    self._poison(u, t, 2)
            elif sid == "cleaving_blow" and targets:
                self._buff(u, "pa", 3)
                t = targets[0]
                self._buff(u, "pd" if t.base["pa"] >= t.base["ea"] else "ed", 3)
            elif sid == "beast_roar":
                for t in targets:
                    if t.alive:
                        self._buff(t, "pa", 2, up=False)
            elif sid == "hien" and u.alive and not u.broken:
                key = (self.round, u.team, u.id)
                if key not in self.hien_round:
                    self.hien_round.add(key)
                    self.hien_pending.append(u)
            return

        # ---------- 非伤害技能 ----------
        def dur():
            return spec["levels"][lv]

        def ally(**kw):
            t = self._ally_target(u, target, **kw)
            if t is None:
                return []
            if spread and tgt_kind != "self":
                return [x for x in self.teams[u.team] if x.alive or kw.get("allow_ko")]
            return [t]

        if sid == "beast_roar":
            for t in self.alive(1-u.team):
                self._buff(t,"pd",3+boost,up=False)
                self._buff(t,"ed",3+boost,up=False)
                if not t.broken:
                    self._reduce_shields(u,t,1)
        elif sid == "abide":
            self._buff(u, "pa", dur())
        elif sid == "stout_wall":
            self._buff(u, "pd", dur())
        elif sid == "swift_step":
            self._buff(u, "spd", dur())
        elif sid == "incite":
            u.st["taunt"] = dur()
            self.ev(e="status", t=u.ref(), k="taunt", r=dur())
        elif sid == "vengeful_blade":
            u.st["counter"] = dur()
            self.ev(e="status", t=u.ref(), k="counter", r=dur())
        elif sid == "sidestep":
            u.st["sidestep"] = dur()
            self.ev(e="status", t=u.ref(), k="sidestep", r=dur())
        elif sid == "rest":
            self._heal(u, self._healing_amount(u, sid, boost))
            gain = min(u.max_sp - u.sp, 25 * (boost + 1))
            u.sp += gain
            self.ev(e="sp", t=u.ref(), v=gain)
            u.st.pop("poison", None)
        elif sid == "donate_bp":
            for t in ally(other=True):
                if t is u:
                    continue
                t.bp = min(MAX_BP, t.bp + dur())
                self.ev(e="bp", t=t.ref(), v=t.bp)
        elif sid in ("armor_corrosive", "shackle_foe", "leghold_trap", "weak_to_poison", "abating_orb"):
            targets = self._enemy_targets(u, target, spread=spread)
            for t in targets:
                if sid == "armor_corrosive":
                    self._buff(t, "pd", dur(), up=False)
                elif sid == "shackle_foe":
                    self._buff(t, "pa", dur(), up=False)
                elif sid == "leghold_trap":
                    t.st["leghold"] = dur()
                    self.ev(e="status", t=t.ref(), k="leghold", r=dur())
                elif sid == "weak_to_poison":
                    t.st["poison_weak"] = dur()
                    self.ev(e="status", t=t.ref(), k="poison_weak", r=dur())
                else:
                    self._dispel(t, dur())
        elif sid == "healing_touch":
            tm = 1 + 0.5 * (tier - 1)
            amt = self._healing_amount(u, sid, boost, tier)
            targets = self._ally_target(u, target, allow_ko=True)
            group = self.teams[u.team] if (spread or u.st.get("charity")) else ([targets] if targets else [])
            for t in group:
                self._revive(t, amt)
        elif sid == "rehabilitate":
            for t in ally():
                t.st["immune"] = dur()
                t.st.pop("poison", None)
                self.ev(e="status", t=t.ref(), k="immune", r=dur())
        elif sid == "replenish_health":
            for t in ally():
                t.st["regen"] = dur()
                self.ev(e="status", t=t.ref(), k="regen", r=dur())
        elif sid == "dohters_charity":
            for t in ally():
                t.st["charity"] = 3
                self.ev(e="status", t=t.ref(), k="charity", r=3)
        elif sid == "take_aim":
            for t in self.alive(u.team):
                self._buff(t, "crit", dur())
                self._buff(t, "acc", dur())
        elif sid == "heal_wounds":
            amt = self._healing_amount(u, sid, boost, tier)
            for t in self.alive(u.team):
                self._heal(t, amt)
        elif sid == "prayer_to_the_flame":
            for t in ally():
                self._buff(t, "pd", dur())
                self._buff(t, "ed", dur())
        elif sid == "sacred_shield":
            for t in ally():
                t.st["sacred"] = dur()
                self.ev(e="status", t=t.ref(), k="sacred", r=dur())
        elif sid == "revive":
            for t in self.teams[u.team]:
                if not t.alive:
                    self._revive(t, self._healing_amount(u, sid, boost, tier))
        elif sid == "aelfrics_blessing":
            for t in ally():
                t.st["extra"] = 3
                self.ev(e="status", t=t.ref(), k="extra", r=3)
        elif sid == "stroke_of_genius":
            for _ in range(dur()):
                s = self.rng.choice(["pa", "pd", "ea", "ed", "spd"])
                self._buff(u, s, u.up.get(s, 0) + 3)
        elif sid == "advance_magic":
            for t in ally():
                n = 2 + boost + int("advanced_magic_master" in u.sup)
                if t.tier[0] <= 2 or t.tier[1] == 0:
                    t.tier = [2, n]
                self.ev(e="status", t=t.ref(), k="tier2", r=n)
        elif sid == "alephans_wisdom":
            for t in ally():
                n = 4 if "advanced_magic_master" in u.sup else 3
                t.tier = [3, n]
                self.ev(e="status", t=t.ref(), k="tier3", r=n)
        elif sid == "lion_dance":
            for t in ally():
                self._buff(t, "pa", dur())
        elif sid == "peacock_strut":
            for t in ally():
                self._buff(t, "ea", dur())
        elif sid == "stimulate":
            for t in ally(other=True):
                if t is u:
                    continue
                n = dur()
                idx = next((i for i, (x, _) in enumerate(self.queue) if x is t), None)
                if idx is not None:
                    item = self.queue.pop(idx)
                    self.queue.insert(max(0, idx - n), item)
                else:
                    t.stim = n
                self.ev(e="status", t=t.ref(), k="stimulate", r=n)
        elif sid == "bewildering_grace":
            for _ in range(dur()):
                self._grace(u)
        elif sid == "sealticges_seduction":
            for t in ally():
                t.st["spread"] = 3
                self.ev(e="status", t=t.ref(), k="spread", r=3)

    def _healing_amount(self, u, sid, boost, tier=1):
        rec = VERIFIED_VALUES[sid]
        if rec.get("tiers"):
            v = rec["tiers"][tier-1][boost]
            ratio, invocation = v["ratio"], v["invocation"]
        else:
            row = rec["levels"][boost]
            ratio = row["ratio"]
            invocation = next(e["value"]/100 for e in row["effects"] if e["effect"] in ("HP_RECOVERY","REVIVE"))
        return max(1, u.base["ed"] * invocation * ratio * self.cfg["level_multiplier"] * self._heal_mult(u) * self.rng.uniform(0.98,1.02))

    @staticmethod
    def _heal_mult(u: Unit) -> float:
        return 1.3 if "resilience" in u.sup else 1.0

    def _grace(self, u: Unit):
        effects = ["heal", "sp", "damage", "atk_up", "def_down", "bp", "hurt_self", "heal_foes"]
        weights = [3, 2, 3, 2, 2, 2, 1, 1]
        eff = self.rng.choices(effects, weights)[0]
        self.ev(e="grace", u=u.ref(), k=eff)
        mine, foes = self.alive(u.team), self.alive(1 - u.team)
        if eff == "heal":
            for t in mine:
                self._heal(t, t.max_hp * 0.2)
        elif eff == "sp":
            for t in mine:
                g = min(t.max_sp - t.sp, 15)
                t.sp += g
                self.ev(e="sp", t=t.ref(), v=g)
        elif eff == "damage":
            self._attack_hits(u, foes, {"kind": "elem", "type": None, "power": 1.2, "hits": 1}, set())
        elif eff == "atk_up":
            for t in mine:
                self._buff(t, "pa", 3)
                self._buff(t, "ea", 3)
        elif eff == "def_down":
            for t in foes:
                self._buff(t, "pd", 3, up=False)
                self._buff(t, "ed", 3, up=False)
        elif eff == "bp":
            for t in mine:
                t.bp = min(MAX_BP, t.bp + 1)
                self.ev(e="bp", t=t.ref(), v=t.bp)
        elif eff == "hurt_self":
            for t in mine:
                d = int(t.max_hp * 0.08)
                t.hp = max(1, t.hp - d)
                self.ev(e="hit", u=u.ref(), t=t.ref(), d=d, ty=None)
        elif eff == "heal_foes":
            for t in foes:
                self._heal(t, t.max_hp * 0.1)

    def _concoct(self, u: Unit, recipe: str, boost: int, target):
        mult = 1 + boost
        allies = self.teams[u.team]
        charity = bool(u.st.get("charity"))
        if recipe == "elixir":
            for t in [x for x in allies if x.alive]:
                self._heal(t, t.max_hp * 0.15 * mult)
        elif recipe == "phoenix":
            group = allies if charity else [self._ally_target(u, target, allow_ko=True)]
            for t in group:
                if t is not None:
                    self._revive(t, t.max_hp * 0.25 * mult)
        elif recipe == "toxin":
            foes = self.alive(1 - u.team)
            self._attack_hits(u, foes, {"kind": "elem", "type": None, "power": 0.5 * mult, "hits": 1}, set())
            for t in foes:
                self._poison(u, t, 3)
        elif recipe == "firebomb":
            self._attack_hits(u, self.alive(1 - u.team), {"kind": "elem", "type": "fire", "power": 0.9 * mult,
                                                          "hits": 1}, set())

    def _item(self, u: Unit, iid: str, target):
        spec = ITEMS[iid]
        fx, kind = spec["fx"], spec["target"]
        if kind == "ko":
            ko = [x for x in self.teams[u.team] if not x.alive]
            ts = [next((x for x in ko if x.id == target), ko[0])] if ko else []
        elif kind == "ally":
            ts = [self._ally_target(u, target)]
        elif kind == "allies":
            ts = self.alive(u.team)
        elif kind == "enemy":
            ts = self._enemy_targets(u, target)
        else:
            ts = self.alive(1 - u.team)
        for t in [x for x in ts if x is not None]:
            if "revive" in fx:
                self._revive(t, fx["revive"])
            if "dmg" in fx:
                self._hit(u, t, "elem", fx.get("type"), 0, set(), {"fixed": fx["dmg"]})
                continue
            if "hp" in fx:
                self._heal(t, fx["hp"])
            if "hp_pct" in fx:
                self._heal(t, t.max_hp * fx["hp_pct"])
            if ("sp" in fx or "sp_pct" in fx) and t.alive:
                g = min(t.max_sp - t.sp, int(fx.get("sp", 0) + t.max_sp * fx.get("sp_pct", 0)))
                t.sp += g
                self.ev(e="sp", t=t.ref(), v=g)
            if fx.get("cure") and t.alive:
                n = int(bool(t.st.pop("poison", 0))) + int(bool(t.st.pop("poison_weak", 0)))
                if n:
                    self.ev(e="cure", t=t.ref(), n=n)
            if fx.get("bp") and t.alive:
                t.bp = min(MAX_BP, t.bp + fx["bp"])
                self.ev(e="bp", t=t.ref(), v=t.bp)
            for st in fx.get("buff", []):
                if t.alive:
                    self._buff(t, st, fx.get("rounds", 2))

    # ------------------------------------------------------------------ 观测
    def unit_view(self, u: Unit, full=True) -> dict:
        cfg = self.cfg
        v = {
            "id": u.id, "traveler": u.key, "name": u.name, "alive": u.alive,
            "hp": u.hp, "max_hp": u.max_hp, "sp": u.sp, "max_sp": u.max_sp, "bp": u.bp,
            "shields": u.shields, "max_shields": u.max_shields, "weaknesses": list(u.weak),
            "broken": u.broken, "broken_until_round": u.recover_round if u.broken else None,
            "latent": round(u.latent, 1), "latent_capacity": u.latent_capacity, "latent_ready": u.latent >= 100,
            "weapons": list(u.weapons),
            "stats": {s: round(u.stat(s, cfg), 1) for s in STATS},
            "base_stats": {s: u.base[s] for s in STATS},
            "buffs": dict(u.up), "debuffs": dict(u.down),
            "status": dict(u.st), "defending": u.defending,
            "spell_tier": u.tier[0] if u.tier[1] > 0 else 1, "spell_tier_charges": u.tier[1],
            "boosted_this_round": u.boosted_this_round,
            "sub_job": u.sub_job, "skills": list(u.skills), "supports": sorted(u.sup),
            "rise_again_ready": u.rise,
        }
        if u.key == "castti":
            v["materials"] = u.materials
        return v
