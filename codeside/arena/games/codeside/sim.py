"""CodeSide 2019 世界模拟，逐行移植官方 Rust 源码 app-src/src/model/（game.rs、weapon.rs、unit.rs ...）。

几何约定和官方 batbox 0.3 相同：
- 矩形 AABB 的 intersects 是严格不等式（只碰到边不算相交）；
- AABB.distance_to 取 x、y 两个方向间隙的较大值（不是欧氏距离）；
- find_tiles 遍历 floor(左下) 到 ceil(右上) 之间的地块。
每个 tick 拆成 updates_per_tick（官方 100）次更新，每次更新的顺序和官方 Game::update 相同：
种地雷 → 射击 → 拾取 → 移动 → 跳板/梯子 → 子弹 → 地雷 → 爆炸 → 结算死亡。
"""
from __future__ import annotations

import math
import random

from .levels import CAN_PLANT_MINE, EMPTY, JUMP_PAD, LADDER, PLATFORM, WALKABLE, WALL

PISTOL, ASSAULT_RIFLE, ROCKET_LAUNCHER = "PISTOL", "ASSAULT_RIFLE", "ROCKET_LAUNCHER"
WEAPON_TYPES = (PISTOL, ASSAULT_RIFLE, ROCKET_LAUNCHER)

# 官方 Properties::default()（app-src/src/model/properties.rs）
PROPERTIES = {
    "max_tick_count": 3600,
    "team_size": 1,
    "ticks_per_second": 60.0,
    "updates_per_tick": 100,
    "loot_box_size": {"x": 0.5, "y": 0.5},
    "unit_size": {"x": 0.9, "y": 1.8},
    "unit_max_horizontal_speed": 10.0,
    "unit_fall_speed": 10.0,
    "unit_jump_time": 0.55,
    "unit_jump_speed": 10.0,
    "jump_pad_jump_time": 0.525,
    "jump_pad_jump_speed": 20.0,
    "unit_max_health": 100,
    "health_pack_health": 50,
    "weapon_params": {
        PISTOL: {"magazine_size": 8, "fire_rate": 0.4, "reload_time": 1.0, "min_spread": 0.05,
                 "max_spread": 0.5, "recoil": 0.5, "aim_speed": 1.0,
                 "bullet": {"speed": 50.0, "size": 0.2, "damage": 20}, "explosion": None},
        ASSAULT_RIFLE: {"magazine_size": 20, "fire_rate": 0.1, "reload_time": 1.0, "min_spread": 0.1,
                        "max_spread": 0.5, "recoil": 0.2, "aim_speed": 1.9,
                        "bullet": {"speed": 50.0, "size": 0.2, "damage": 5}, "explosion": None},
        ROCKET_LAUNCHER: {"magazine_size": 1, "fire_rate": 1.0, "reload_time": 1.0, "min_spread": 0.1,
                          "max_spread": 0.5, "recoil": 1.0, "aim_speed": 1.0,
                          "bullet": {"speed": 20.0, "size": 0.4, "damage": 30},
                          "explosion": {"radius": 3.0, "damage": 50}},
    },
    "mine_size": {"x": 0.5, "y": 0.5},
    "mine_explosion_params": {"radius": 3.0, "damage": 50},
    "mine_prepare_time": 1.0,
    "mine_trigger_time": 0.5,
    "mine_trigger_radius": 1.0,
    "kill_score": 1000,
}

EPS = 1e-9
_WALL, _LADDER = frozenset((WALL,)), frozenset((LADDER,))


def _intersects(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1) -> bool:
    return ax1 > bx0 and ay1 > by0 and ax0 < bx1 and ay0 < by1


def _norm_angle(a):
    while a >= math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class JumpState:
    __slots__ = ("can_jump", "speed", "max_time", "can_cancel")

    def __init__(self, can_jump=False, speed=0.0, max_time=0.0, can_cancel=False):
        self.can_jump, self.speed, self.max_time, self.can_cancel = can_jump, speed, max_time, can_cancel

    def copy(self):
        return JumpState(self.can_jump, self.speed, self.max_time, self.can_cancel)

    def to_json(self):
        return {"can_jump": self.can_jump, "speed": self.speed, "max_time": self.max_time,
                "can_cancel": self.can_cancel}


def falling():
    return JumpState()


class Weapon:
    __slots__ = ("typ", "params", "magazine", "was_shooting", "spread", "fire_timer", "last_angle",
                 "last_fire_tick")

    def __init__(self, props, typ):
        p = props["weapon_params"][typ]
        self.typ = typ
        self.params = p
        self.spread = p["min_spread"]
        self.magazine = p["magazine_size"]
        self.was_shooting = False
        self.fire_timer = p["reload_time"]     # 刚捡起的武器处于装弹状态
        self.last_angle = None
        self.last_fire_tick = None

    def reload(self):
        if self.magazine == self.params["magazine_size"]:
            return
        self.fire_timer = self.params["reload_time"]
        self.magazine = self.params["magazine_size"]

    def update(self, dt):
        p = self.params
        self.spread = max(self.spread - p["aim_speed"] * dt, p["min_spread"])
        if self.fire_timer is not None:
            t = self.fire_timer - dt
            self.fire_timer = t if t > 0 else None

    def aim(self, ax, ay):
        angle = math.atan2(ay, ax)
        if self.last_angle is not None:
            extra = abs(_norm_angle(angle - self.last_angle))
            self.spread = min(self.spread + extra, self.params["max_spread"])
        self.last_angle = angle

    def fire(self, tick, unit, ax, ay, rng):
        if self.fire_timer is not None or self.magazine == 0:
            return None
        p = self.params
        self.last_fire_tick = tick
        self.magazine -= 1
        a = rng.uniform(-self.spread, self.spread)
        c, s = math.cos(a), math.sin(a)
        dx, dy = ax * c - ay * s, ax * s + ay * c
        self.spread = min(self.spread + p["recoil"], p["max_spread"])
        if self.magazine == 0:
            self.magazine = p["magazine_size"]
            self.fire_timer = p["reload_time"]
        else:
            self.fire_timer = p["fire_rate"]
        n = math.hypot(dx, dy)
        b = p["bullet"]
        cx, cy = unit.x, unit.y + unit.sy / 2
        return Bullet(self.typ, unit.id, unit.player_id, cx, cy, dx / n * b["speed"], dy / n * b["speed"],
                      b["damage"], b["size"], p["explosion"])

    def to_json(self):
        return {"typ": self.typ, "params": self.params, "magazine": self.magazine,
                "was_shooting": self.was_shooting, "spread": self.spread, "fire_timer": self.fire_timer,
                "last_angle": self.last_angle, "last_fire_tick": self.last_fire_tick}


class Unit:
    __slots__ = ("player_id", "id", "health", "x", "y", "sx", "sy", "jump_state", "walked_right", "stand",
                 "on_ground", "on_ladder", "mines", "weapon")

    def __init__(self, props, uid, player_id, x, y):
        self.player_id = player_id
        self.id = uid
        self.health = props["unit_max_health"]
        self.x, self.y = x, y
        self.sx, self.sy = props["unit_size"]["x"], props["unit_size"]["y"]
        self.jump_state = falling()
        self.walked_right = True
        self.stand = True
        self.on_ground = False
        self.on_ladder = False
        self.mines = 0
        self.weapon: Weapon | None = None

    def rect(self):
        return self.x - self.sx / 2, self.y, self.x + self.sx / 2, self.y + self.sy

    def to_json(self):
        return {"player_id": self.player_id, "id": self.id, "health": self.health,
                "position": {"x": self.x, "y": self.y}, "size": {"x": self.sx, "y": self.sy},
                "jump_state": self.jump_state.to_json(), "walked_right": self.walked_right,
                "stand": self.stand, "on_ground": self.on_ground, "on_ladder": self.on_ladder,
                "mines": self.mines, "weapon": self.weapon.to_json() if self.weapon else None}


class Bullet:
    __slots__ = ("weapon_type", "unit_id", "player_id", "x", "y", "vx", "vy", "damage", "size",
                 "explosion_params")

    def __init__(self, wt, unit_id, player_id, x, y, vx, vy, damage, size, explosion):
        self.weapon_type, self.unit_id, self.player_id = wt, unit_id, player_id
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.damage, self.size, self.explosion_params = damage, size, explosion

    def rect(self):
        h = self.size / 2
        return self.x - h, self.y - h, self.x + h, self.y + h

    def to_json(self):
        return {"weapon_type": self.weapon_type, "unit_id": self.unit_id, "player_id": self.player_id,
                "position": {"x": self.x, "y": self.y}, "velocity": {"x": self.vx, "y": self.vy},
                "damage": self.damage, "size": self.size, "explosion_params": self.explosion_params}


class Mine:
    __slots__ = ("player_id", "x", "y", "sx", "sy", "state", "timer", "trigger_radius", "explosion_params")

    def __init__(self, player_id, props, x, y):
        self.player_id = player_id
        self.x, self.y = x, y
        self.sx, self.sy = props["mine_size"]["x"], props["mine_size"]["y"]
        self.state = "PREPARING"
        self.timer = props["mine_prepare_time"]
        self.trigger_radius = props["mine_trigger_radius"]
        self.explosion_params = props["mine_explosion_params"]

    def rect(self):
        return self.x - self.sx / 2, self.y, self.x + self.sx / 2, self.y + self.sy

    def to_json(self):
        return {"player_id": self.player_id, "position": {"x": self.x, "y": self.y},
                "size": {"x": self.sx, "y": self.sy}, "state": self.state, "timer": self.timer,
                "trigger_radius": self.trigger_radius, "explosion_params": self.explosion_params}


class LootBox:
    __slots__ = ("x", "y", "sx", "sy", "item", "r")

    def __init__(self, props, x, y, item):
        self.x, self.y = x, y
        self.sx, self.sy = props["loot_box_size"]["x"], props["loot_box_size"]["y"]
        self.r = self.rect()     # 战利品不会移动，缓存矩形
        self.item = item         # {"type": "HealthPack", "health": 50} / {"type": "Weapon", "weapon_type": ...} / {"type": "Mine"}

    def rect(self):
        return self.x - self.sx / 2, self.y, self.x + self.sx / 2, self.y + self.sy

    def to_json(self):
        return {"position": {"x": self.x, "y": self.y}, "size": {"x": self.sx, "y": self.sy},
                "item": dict(self.item)}


class World:
    """官方 model::Game。players[i] 的 id 是 i+1，单位 id 从 3 开始（和官方的全局 Id 计数器一致）。"""

    def __init__(self, props: dict, tiles, spawn_points, rng: random.Random, num_players: int = 2):
        self.props = props
        self.tiles = tiles
        self.w, self.h = len(tiles), len(tiles[0])
        self.has_pads = any(JUMP_PAD in col for col in tiles)
        self.rng = rng
        self.current_tick = 0
        self.player_ids = list(range(1, num_players + 1))
        self.scores = [0] * num_players
        self.units: list[Unit] = []
        self.bullets: list[Bullet] = []
        self.mines: list[Mine] = []
        self.loot_boxes: list[LootBox] = []
        next_id = num_players + 1
        sp = iter(spawn_points)
        for _ in range(props["team_size"]):
            for pid in self.player_ids:
                x, y = next(sp)
                self.units.append(Unit(props, next_id, pid, float(x), float(y)))
                next_id += 1
        self._spawn_loot()
        self.events: list = []

    # ---------- 开局 ----------
    def _spawn_loot(self):
        t, W = self.tiles, self.w
        possible = []
        for x in range(W):
            for y in range(self.h):
                if (x < W // 2 and y > 0 and t[x][y] == EMPTY and t[x][y - 1] in WALKABLE
                        and t[x][y] == t[W - 1 - x][y] and t[x][y - 1] == t[W - 1 - x][y - 1]):
                    possible.append((x, y))
        count = len(possible) // 4
        chosen = self.rng.sample(possible, count)
        for i, (x, y) in enumerate(chosen):
            if i < 3:
                item = {"type": "Weapon", "weapon_type": WEAPON_TYPES[i]}
            elif self.rng.random() < 0.5:
                item = {"type": "HealthPack", "health": self.props["health_pack_health"]}
            else:
                item = {"type": "Mine"}
            for px in (x, W - 1 - x):
                self.loot_boxes.append(LootBox(self.props, px + 0.5, float(y), dict(item)))

    # ---------- 地块查询 ----------
    def tile(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.tiles[x][y]
        return None

    def _range(self, x0, y0, x1, y1):
        """官方 Level::find_tiles 的遍历范围：[floor(x0), ceil(x1)) × [floor(y0), ceil(y1))，裁剪到地图内。"""
        w, h = self.w, self.h
        sx, sy, ex, ey = math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)
        return (0 if sx < 0 else (w if sx > w else sx), 0 if sy < 0 else (h if sy > h else sy),
                0 if ex < 0 else (w if ex > w else ex), 0 if ey < 0 else (h if ey > h else ey))

    def _tiles_in(self, x0, y0, x1, y1):
        """官方 Level::find_tiles：返回 [(x, y, tile)]。"""
        sx, sy, ex, ey = self._range(x0, y0, x1, y1)
        t = self.tiles
        return [(x, y, t[x][y]) for x in range(sx, ex) for y in range(sy, ey)]

    def _any_tile(self, rect, kinds):
        sx, sy, ex, ey = self._range(*rect)
        t = self.tiles
        for x in range(sx, ex):
            col = t[x]
            for y in range(sy, ey):
                if col[y] in kinds:
                    return True
        return False

    def _on_ladder_rect(self, u):
        # ladder_rect：从单位脚底中点到身体中心的竖线
        return self._any_tile((u.x, u.y, u.x, u.y + u.sy / 2), _LADDER)

    # ---------- 一个 tick ----------
    def tick(self, actions: dict) -> list:
        """actions: {unit_id: action dict}（已校验归属）。返回本 tick 的事件列表。"""
        self.events = []
        planted, swapped = set(), set()
        dt = 1.0 / self.props["ticks_per_second"] / self.props["updates_per_tick"]
        for _ in range(int(self.props["updates_per_tick"])):
            self._update(actions, planted, swapped, dt)
        self.current_tick += 1
        return self.events

    def finished(self) -> bool:
        return len({u.player_id for u in self.units}) <= 1 or self.current_tick >= self.props["max_tick_count"]

    def _update(self, actions, planted, swapped, dt):
        explosions = []
        self._planting_mines(actions, planted)
        self._shooting(actions, dt)
        self._loot_boxes(actions, swapped)
        self._movement(actions, dt)
        self._level_jumps()
        self._bullets(explosions, dt)
        self._process_mines(explosions, dt)
        self._explosions(explosions)
        for u in self.units:
            if u.health <= 0:
                other = next(i for i, pid in enumerate(self.player_ids) if pid != u.player_id)
                self.scores[other] += self.props["kill_score"]
                self.events.append(("death", u.id, u.x, u.y))
        if any(u.health <= 0 for u in self.units):
            self.units = [u for u in self.units if u.health > 0]
        for e in explosions:
            self.events.append(("explosion", e[0], e[1], e[2]["radius"], e[3]))

    def _score(self, player_id, amount):
        self.scores[self.player_ids.index(player_id)] += amount

    def _shooting(self, actions, dt):
        for u in self.units:
            w = u.weapon
            if w is None:
                continue
            a = actions.get(u.id)
            if a is not None and math.hypot(a["ax"], a["ay"]) > 0.5:
                w.aim(a["ax"], a["ay"])
                w.was_shooting = a["shoot"]
                if a["reload"]:
                    w.reload()
                if a["shoot"]:
                    b = w.fire(self.current_tick, u, a["ax"], a["ay"], self.rng)
                    if b is not None:
                        self.events.append(("shot", u.id, b.weapon_type))
                        self.bullets.append(b)
            w.update(dt)

    def _movement(self, actions, dt):
        p = self.props
        units = self.units

        def upd(old, direction, to):
            return max(old, to) if direction > old else min(old, to)

        for u in units:
            a = actions.get(u.id)
            vel = a["velocity"] if a else 0.0
            jump = a["jump"] if a else False
            jump_down = a["jump_down"] if a else False
            on_ground = False
            px, py = u.x, u.y
            js = u.jump_state.copy()
            nx, ny = px, py
            ms = p["unit_max_horizontal_speed"]
            nx += max(-ms, min(ms, vel)) * dt
            if js.can_cancel and not jump:
                js = falling()
            if js.can_jump:
                ny += js.speed * dt
                js.max_time -= dt
                if js.max_time < 0:
                    js = falling()
            elif jump_down or not self._on_ladder_rect(u):
                ny -= p["unit_fall_speed"] * dt
            hx, sy = u.sx / 2, u.sy
            ux0, uy0, ux1, uy1 = u.rect()

            # 水平
            for o in units:
                if o is u:
                    continue
                if _intersects(nx - hx, py, nx + hx, py + sy, *o.rect()):
                    sign = math.copysign(1.0, px - o.x)
                    nx = upd(px, nx, o.x + sign * ((u.sx + o.sx) / 2 + EPS))
            if self._any_tile((nx - hx, py, nx + hx, py + sy), _WALL):
                if nx > px:
                    px = upd(px, nx, px + math.ceil(ux1 - EPS) - ux1 - EPS)
                else:
                    px = upd(px, nx, px + math.floor(ux0 + EPS) - ux0 + EPS)
            else:
                px = nx
            nx = px

            # 竖直
            for o in units:
                if o is u:
                    continue
                if _intersects(nx - hx, ny, nx + hx, ny + sy, *o.rect()):
                    if ny > py:
                        ny = upd(py, ny, o.y - sy - EPS)
                        js = falling()
                    else:
                        ny = upd(py, ny, o.y + o.sy + EPS)
                        js = JumpState(True, p["unit_jump_speed"], p["unit_jump_time"], True)
            falling_from = None if jump_down else py
            hit = False
            for tx, ty, t in self._tiles_in(nx - hx, ny, nx + hx, ny + sy):
                if t == WALL:
                    hit = True
                elif t == PLATFORM:
                    hit = falling_from is not None and falling_from > 0 and int(falling_from) > ty
                elif t == LADDER:
                    hit = (falling_from is not None and falling_from > 0 and int(falling_from) > ty
                           and px > 0 and int(px) == tx)
                if hit:
                    break
            if hit:
                if ny < py:
                    js = JumpState(True, p["unit_jump_speed"], p["unit_jump_time"], True)
                    on_ground = True
                else:
                    js = falling()
                if ny > py:
                    py = upd(py, ny, py + math.ceil(uy1 - EPS) - uy1 - EPS)
                else:
                    py = upd(py, ny, py + math.floor(uy0 + EPS) - uy0 + EPS)
            else:
                py = ny

            u.on_ground = on_ground
            u.stand = px == u.x
            if not u.stand:
                u.walked_right = px > u.x
            u.x, u.y = px, py
            u.jump_state = js

    def _level_jumps(self):
        p = self.props
        for u in self.units:
            u.on_ladder = False
            for tx, ty, t in (self._tiles_in(*u.rect()) if self.has_pads else ()):
                if t == JUMP_PAD:
                    u.jump_state = JumpState(True, p["jump_pad_jump_speed"], p["jump_pad_jump_time"], False)
                    self.events.append(("pad", tx, ty))
                    break
            if self._on_ladder_rect(u):
                u.jump_state = JumpState(True, p["unit_jump_speed"],
                                         max(u.jump_state.max_time, p["unit_jump_time"]), True)
                u.on_ground = True
                u.on_ladder = True

    def _bullets(self, explosions, dt):
        keep = []
        for b in self.bullets:
            br = b.rect()
            gone = False
            for u in self.units:
                if u.id == b.unit_id:
                    continue
                if _intersects(*br, *u.rect()):
                    self.events.append(("hit", u.id, b.weapon_type))
                    score = max(min(b.damage, u.health), 0)
                    u.health -= b.damage
                    if u.player_id != b.player_id:
                        self._score(b.player_id, score)
                    if b.explosion_params:
                        explosions.append((b.x, b.y, b.explosion_params, b.player_id))
                    gone = True
                    break
            if not gone:
                for m in self.mines:
                    if _intersects(*br, *m.rect()):
                        m.state = "EXPLODED"
                        if b.explosion_params:
                            explosions.append((b.x, b.y, b.explosion_params, b.player_id))
                        gone = True
                        break
            if not gone:
                keep.append(b)
        for b in keep:
            b.x += b.vx * dt
            b.y += b.vy * dt
        self.bullets = []
        for b in keep:
            if self._any_tile(b.rect(), _WALL):
                if b.explosion_params:
                    explosions.append((b.x, b.y, b.explosion_params, b.player_id))
                self.events.append(("wall", b.x, b.y, b.weapon_type))
            elif -10 < b.x < self.w + 10 and -10 < b.y < self.h + 10:   # 安全网：飞出地图外的子弹删除（官方地图四周都是墙，不会发生）
                self.bullets.append(b)

    def _loot_boxes(self, actions, swapped):
        p = self.props
        taken = False
        for u in self.units:
            a = actions.get(u.id)
            swap = bool(a and a["swap_weapon"]) and u.id not in swapped
            ux0, uy0, ux1, uy1 = u.rect()
            for box in self.loot_boxes:
                r = box.r
                if not (ux1 > r[0] and uy1 > r[1] and ux0 < r[2] and uy0 < r[3]) or box.item is None:
                    continue
                it = box.item
                kind = it["type"]
                if kind == "HealthPack":
                    if u.health < p["unit_max_health"]:
                        self.events.append(("heal", u.id))
                        u.health = min(u.health + it["health"], p["unit_max_health"])
                        box.item = None
                        taken = True
                elif kind == "Weapon":
                    if u.weapon is not None:
                        if swap:
                            old = u.weapon.typ
                            u.weapon = Weapon(p, it["weapon_type"])
                            box.item = {"type": "Weapon", "weapon_type": old}
                            swapped.add(u.id)
                            self.events.append(("swap", u.id))
                    else:
                        self.events.append(("pickup", u.id))
                        u.weapon = Weapon(p, it["weapon_type"])
                        box.item = None
                        taken = True
                else:
                    self.events.append(("pickup_mine", u.id))
                    u.mines += 1
                    box.item = None
                    taken = True
        if taken:
            self.loot_boxes = [b for b in self.loot_boxes if b.item is not None]

    def _planting_mines(self, actions, planted):
        for u in self.units:
            a = actions.get(u.id)
            if a and a["plant_mine"] and u.id not in planted:
                below = self.tile(int(max(u.x, 0.0)), max(int(max(u.y, 0.0)), 1) - 1)
                if u.mines > 0 and u.on_ground and not u.on_ladder and below in CAN_PLANT_MINE:
                    u.mines -= 1
                    self.mines.append(Mine(u.player_id, self.props, u.x, u.y))
                    self.events.append(("plant", u.id))
                planted.add(u.id)

    def _process_mines(self, explosions, dt):
        for m in self.mines:
            if m.timer is not None:
                t = m.timer - dt
                m.timer = t if t > 0 else None
            if m.state == "PREPARING":
                if m.timer is None:
                    m.state = "IDLE"
            elif m.state == "IDLE":
                mr = m.rect()
                for u in self.units:
                    ur = u.rect()
                    d = max(mr[0] - ur[2], ur[0] - mr[2], mr[1] - ur[3], ur[1] - mr[3], 0.0)
                    if d < m.trigger_radius:
                        m.state = "TRIGGERED"
                        m.timer = self.props["mine_trigger_time"]
                        break
            elif m.state == "TRIGGERED":
                if m.timer is None:
                    m.state = "EXPLODED"
            if m.state == "EXPLODED":
                mr = m.rect()
                explosions.append(((mr[0] + mr[2]) / 2, (mr[1] + mr[3]) / 2, m.explosion_params, m.player_id))
        if any(m.state == "EXPLODED" for m in self.mines):
            self.mines = [m for m in self.mines if m.state != "EXPLODED"]

    def _explosions(self, explosions):
        for x, y, params, pid in explosions:
            r = params["radius"]
            rect = (x - r, y - r, x + r, y + r)
            for u in self.units:
                if _intersects(*u.rect(), *rect):
                    score = max(min(params["damage"], u.health), 0)
                    u.health -= params["damage"]
                    self.events.append(("blast_hit", u.id))
                    if u.player_id != pid:
                        self._score(pid, score)
            for m in self.mines:
                if _intersects(*m.rect(), *rect):
                    m.state = "EXPLODED"
