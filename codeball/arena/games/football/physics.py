"""3D 足球物理：逐行对照 Russian AI Cup 2018 CodeBall 官方《Developer Guide》第 3 章的模拟伪代码实现，
常数取自官方文档 3.2 节和 1.3 节（github.com/MailRuChamps/raic-2018 的 docs/ 目录同源）。

坐标系：x 横向（-width/2 ~ width/2），y 竖直向上（0 ~ height），z 纵向（-depth/2 ~ depth/2）。
1 号玩家（team 0）的球门在 z < 0 一侧，2 号玩家（team 1）的球门在 z > 0 一侧。
"""
from __future__ import annotations

import math
import random

# ---------------------------------------------------------------- 常数
RULES = {
    "ROBOT_MIN_RADIUS": 1.0,
    "ROBOT_MAX_RADIUS": 1.05,
    "ROBOT_MAX_JUMP_SPEED": 15.0,
    "ROBOT_ACCELERATION": 100.0,
    "ROBOT_NITRO_ACCELERATION": 30.0,
    "ROBOT_MAX_GROUND_SPEED": 30.0,
    "ROBOT_ARENA_E": 0.0,
    "ROBOT_RADIUS": 1.0,
    "ROBOT_MASS": 2.0,
    "TICKS_PER_SECOND": 60,
    "MICROTICKS_PER_TICK": 100,
    "RESET_TICKS": 120,              # 2 * TICKS_PER_SECOND
    "BALL_ARENA_E": 0.7,
    "BALL_RADIUS": 2.0,
    "BALL_MASS": 1.0,
    "MIN_HIT_E": 0.4,
    "MAX_HIT_E": 0.5,
    "MAX_ENTITY_SPEED": 100.0,
    "MAX_NITRO_AMOUNT": 100.0,
    "START_NITRO_AMOUNT": 50.0,
    "NITRO_POINT_VELOCITY_CHANGE": 0.6,
    "NITRO_PACK_X": 20.0,
    "NITRO_PACK_Y": 1.0,
    "NITRO_PACK_Z": 30.0,
    "NITRO_PACK_RADIUS": 0.5,
    "NITRO_PACK_AMOUNT": 100.0,
    "NITRO_PACK_RESPAWN_TICKS": 600, # 10 * TICKS_PER_SECOND
    "GRAVITY": 30.0,
}

ARENA = {
    "width": 60.0,
    "height": 20.0,
    "depth": 80.0,
    "bottom_radius": 3.0,
    "top_radius": 7.0,
    "corner_radius": 13.0,
    "goal_top_radius": 3.0,
    "goal_width": 30.0,
    "goal_height": 10.0,
    "goal_depth": 10.0,
    "goal_side_radius": 1.0,
}


# ---------------------------------------------------------------- 到场地的距离（dan = distance and normal）
class Arena:
    def __init__(self, a: dict):
        self.w2 = a["width"] / 2
        self.h = a["height"]
        self.d2 = a["depth"] / 2
        self.br = a["bottom_radius"]
        self.tr = a["top_radius"]
        self.cr = a["corner_radius"]
        self.gtr = a["goal_top_radius"]
        self.gw2 = a["goal_width"] / 2
        self.gh = a["goal_height"]
        self.gd = a["goal_depth"]
        self.gsr = a["goal_side_radius"]
        assert self.br == self.gtr, "规则要求 bottom_radius == goal_top_radius"

    def dan(self, x, y, z):
        """返回 (距离, nx, ny, nz)：点到场地表面的最近距离和指向场内的法向量。"""
        nx_neg = x < 0
        nz_neg = z < 0
        if nx_neg:
            x = -x
        if nz_neg:
            z = -z
        d, nx, ny, nz = self._quarter(x, y, z)
        if nx_neg:
            nx = -nx
        if nz_neg:
            nz = -nz
        return d, nx, ny, nz

    def _quarter(self, x, y, z):
        w2, h, d2, br, tr, cr = self.w2, self.h, self.d2, self.br, self.tr, self.cr
        gtr, gw2, gh, gd, gsr = self.gtr, self.gw2, self.gh, self.gd, self.gsr

        # 用局部变量保存当前最优 (dist, nx, ny, nz)，避免创建对象
        # 地面
        best_d, bx, by, bz = y, 0.0, 1.0, 0.0
        # 天花板
        dd = h - y
        if dd < best_d:
            best_d, bx, by, bz = dd, 0.0, -1.0, 0.0
        # 侧墙 x
        dd = w2 - x
        if dd < best_d:
            best_d, bx, by, bz = dd, -1.0, 0.0, 0.0
        # 球门后墙
        dd = d2 + gd - z
        if dd < best_d:
            best_d, bx, by, bz = dd, 0.0, 0.0, -1.0
        # 底线墙 z（门框以外的部分）
        vx, vy = x - (gw2 - gtr), y - (gh - gtr)
        if x >= gw2 + gsr or y >= gh + gsr or (vx > 0 and vy > 0 and math.hypot(vx, vy) >= gtr + gsr):
            dd = d2 - z
            if dd < best_d:
                best_d, bx, by, bz = dd, 0.0, 0.0, -1.0
        # 球门内的侧壁和顶
        if z >= d2 + gsr:
            dd = gw2 - x
            if dd < best_d:
                best_d, bx, by, bz = dd, -1.0, 0.0, 0.0
            dd = gh - y
            if dd < best_d:
                best_d, bx, by, bz = dd, 0.0, -1.0, 0.0

        def inner(cx, cy, cz, r):
            nonlocal best_d, bx, by, bz
            ex, ey, ez = cx - x, cy - y, cz - z
            ln = math.sqrt(ex * ex + ey * ey + ez * ez)
            dd = r - ln
            if dd < best_d and ln > 1e-12:
                best_d, bx, by, bz = dd, ex / ln, ey / ln, ez / ln

        def outer(cx, cy, cz, r):
            nonlocal best_d, bx, by, bz
            ex, ey, ez = x - cx, y - cy, z - cz
            ln = math.sqrt(ex * ex + ey * ey + ez * ez)
            dd = ln - r
            if dd < best_d and ln > 1e-12:
                best_d, bx, by, bz = dd, ex / ln, ey / ln, ez / ln

        def clamp(v, lo, hi):
            return lo if v < lo else hi if v > hi else v

        # 球门后角
        if z > d2 + gd - br:
            inner(clamp(x, br - gw2, gw2 - br), clamp(y, br, gh - gtr), d2 + gd - br, br)
        # 场地四角（竖直圆柱）
        if x > w2 - cr and z > d2 - cr:
            inner(w2 - cr, y, d2 - cr, cr)
        # 球门口外侧的圆角
        if z < d2 + gsr:
            if x < gw2 + gsr:
                outer(gw2 + gsr, y, d2 + gsr, gsr)
            if y < gh + gsr:
                outer(x, gh + gsr, d2 + gsr, gsr)
            ox, oy = gw2 - gtr, gh - gtr
            vx, vy = x - ox, y - oy
            if vx > 0 and vy > 0:
                ln = math.hypot(vx, vy)
                ox += vx / ln * (gtr + gsr)
                oy += vy / ln * (gtr + gsr)
                outer(ox, oy, d2 + gsr, gsr)
        # 球门内顶部圆角
        if z > d2 + gsr and y > gh - gtr:
            if x > gw2 - gtr:
                inner(gw2 - gtr, gh - gtr, z, gtr)
            if z > d2 + gd - gtr:
                inner(x, gh - gtr, d2 + gd - gtr, gtr)
        # 底部圆角
        if y < br:
            if x > w2 - br:
                inner(w2 - br, br, z, br)
            if z > d2 - br and x >= gw2 + gsr:
                inner(x, br, d2 - br, br)
            if z > d2 + gd - br:
                inner(x, br, d2 + gd - br, br)
            ox, oz = gw2 + gsr, d2 + gsr
            vx, vz = x - ox, z - oz
            if vx < 0 and vz < 0 and math.hypot(vx, vz) < gsr + br:
                ln = math.hypot(vx, vz)
                ox += vx / ln * (gsr + br)
                oz += vz / ln * (gsr + br)
                inner(ox, br, oz, br)
            if z >= d2 + gsr and x > gw2 - br:
                inner(gw2 - br, br, z, br)
            if x > w2 - cr and z > d2 - cr:
                cx, cz = w2 - cr, d2 - cr
                nx, nz = x - cx, z - cz
                ln = math.hypot(nx, nz)
                if ln > cr - br:
                    inner(cx + nx / ln * (cr - br), br, cz + nz / ln * (cr - br), br)
        # 天花板圆角
        if y > h - tr:
            if x > w2 - tr:
                inner(w2 - tr, h - tr, z, tr)
            if z > d2 - tr:
                inner(x, h - tr, d2 - tr, tr)
            if x > w2 - cr and z > d2 - cr:
                cx, cz = w2 - cr, d2 - cr
                nx, nz = x - cx, z - cz
                ln = math.hypot(nx, nz)
                if ln > cr - tr:
                    inner(cx + nx / ln * (cr - tr), h - tr, cz + nz / ln * (cr - tr), tr)
        return best_d, bx, by, bz


# ---------------------------------------------------------------- 实体
class Entity:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "radius", "mass", "arena_e", "radius_change_speed",
                 "touch", "tnx", "tny", "tnz", "nitro", "team", "id", "index",
                 "a_tvx", "a_tvy", "a_tvz", "a_jump", "a_nitro", "nitro_used")

    def __init__(self, x, y, z, radius, mass, arena_e):
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = self.vz = 0.0
        self.radius, self.mass, self.arena_e = radius, mass, arena_e
        self.radius_change_speed = 0.0
        self.touch = False
        self.tnx, self.tny, self.tnz = 0.0, 1.0, 0.0
        self.nitro = 0.0
        self.team = -1      # 0 / 1
        self.id = -1        # 官方的机器人 id（从 1 开始，全场唯一）
        self.index = -1     # 在本队里的序号
        self.nitro_used = False  # 本 tick 是否真的消耗了氮气（回放用）
        self.a_tvx = self.a_tvy = self.a_tvz = 0.0
        self.a_jump = 0.0
        self.a_nitro = False


class NitroPack:
    __slots__ = ("x", "y", "z", "radius", "alive", "respawn_ticks")

    def __init__(self, x, y, z, r):
        self.x, self.y, self.z, self.radius = x, y, z, r
        self.alive = True
        self.respawn_ticks = 0


# ---------------------------------------------------------------- 世界
class World:
    def __init__(self, rules: dict, arena: dict, team_size: int, nitro: bool, microticks: int, rng: random.Random,
                 disable_random: bool = False):
        self.R = rules
        self.A = arena
        self.arena = Arena(arena)
        self.team_size = team_size
        self.nitro_enabled = nitro
        self.microticks = microticks
        self.rng = rng
        # 官方 local runner 的 --disable-random：碰撞恢复系数固定取 MAX_HIT_E，机器人按 id 顺序处理
        self.disable_random = disable_random
        self.robots: list[Entity] = []
        for team in range(2):
            for i in range(team_size):
                r = Entity(0, rules["ROBOT_RADIUS"], 0, rules["ROBOT_RADIUS"], rules["ROBOT_MASS"], rules["ROBOT_ARENA_E"])
                r.team, r.index, r.id = team, i, team * team_size + i + 1
                self.robots.append(r)
        self.ball = Entity(0, rules["BALL_RADIUS"], 0, rules["BALL_RADIUS"], rules["BALL_MASS"], rules["BALL_ARENA_E"])
        self.packs: list[NitroPack] = []
        if nitro:
            for sx in (-1, 1):
                for sz in (-1, 1):
                    self.packs.append(NitroPack(sx * rules["NITRO_PACK_X"], rules["NITRO_PACK_Y"],
                                                sz * rules["NITRO_PACK_Z"], rules["NITRO_PACK_RADIUS"]))
        self.reset()

    def reset(self):
        """开球（官方 1.2 节）：机器人随机落在己方半场地面上，和对方机器人关于场地中心对称（因此到球的距离相同）；
        球在 (0, y, 0)，y 在 BALL_RADIUS ~ 4 * BALL_RADIUS 之间均匀随机。"""
        R, A = self.R, self.A
        for i in range(self.team_size):
            x = self.rng.uniform(-A["width"] / 2 + 4, A["width"] / 2 - 4)
            z = -self.rng.uniform(A["depth"] / 8, A["depth"] / 2 - 6)
            for r in self.robots:
                if r.index != i:
                    continue
                sign = 1 if r.team == 0 else -1
                r.x, r.y, r.z = x * sign, R["ROBOT_RADIUS"], z * sign
                r.vx = r.vy = r.vz = 0.0
                r.radius = R["ROBOT_RADIUS"]
                r.radius_change_speed = 0.0
                r.touch, r.tnx, r.tny, r.tnz = True, 0.0, 1.0, 0.0
                r.nitro = R["START_NITRO_AMOUNT"] if self.nitro_enabled else 0.0  # 第一轮没有氮气
        b = self.ball
        b.x, b.z = 0.0, 0.0
        b.y = self.rng.uniform(R["BALL_RADIUS"], 4 * R["BALL_RADIUS"])
        b.vx = b.vy = b.vz = 0.0
        for p in self.packs:
            p.alive, p.respawn_ticks = True, 0

    # ---- 官方伪代码 ----
    def _move(self, e: Entity, dt: float):
        R = self.R
        sp = math.sqrt(e.vx * e.vx + e.vy * e.vy + e.vz * e.vz)
        if sp > R["MAX_ENTITY_SPEED"]:
            k = R["MAX_ENTITY_SPEED"] / sp
            e.vx, e.vy, e.vz = e.vx * k, e.vy * k, e.vz * k
        e.x += e.vx * dt
        e.y += e.vy * dt
        e.z += e.vz * dt
        e.y -= R["GRAVITY"] * dt * dt / 2
        e.vy -= R["GRAVITY"] * dt

    def _collide_entities(self, a: Entity, b: Entity):
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        pen = a.radius + b.radius - dist
        if pen > 0 and dist > 1e-12:
            ia, ib = 1 / a.mass, 1 / b.mass
            ka, kb = ia / (ia + ib), ib / (ia + ib)
            nx, ny, nz = dx / dist, dy / dist, dz / dist
            a.x -= nx * pen * ka
            a.y -= ny * pen * ka
            a.z -= nz * pen * ka
            b.x += nx * pen * kb
            b.y += ny * pen * kb
            b.z += nz * pen * kb
            dv = ((b.vx - a.vx) * nx + (b.vy - a.vy) * ny + (b.vz - a.vz) * nz
                  - b.radius_change_speed - a.radius_change_speed)
            if dv < 0:
                e = self.R["MAX_HIT_E"] if self.disable_random else self.rng.uniform(self.R["MIN_HIT_E"], self.R["MAX_HIT_E"])
                imp = (1 + e) * dv
                a.vx += nx * imp * ka
                a.vy += ny * imp * ka
                a.vz += nz * imp * ka
                b.vx -= nx * imp * kb
                b.vy -= ny * imp * kb
                b.vz -= nz * imp * kb
            return True
        return False

    def _collide_with_arena(self, e: Entity):
        d, nx, ny, nz = self.arena.dan(e.x, e.y, e.z)
        pen = e.radius - d
        if pen > 0:
            e.x += nx * pen
            e.y += ny * pen
            e.z += nz * pen
            v = e.vx * nx + e.vy * ny + e.vz * nz - e.radius_change_speed
            if v < 0:
                k = (1 + e.arena_e) * v
                e.vx -= k * nx
                e.vy -= k * ny
                e.vz -= k * nz
                return nx, ny, nz
        return None

    def _update(self, dt: float) -> int | None:
        """一个微步。返回进球方（0/1）或 None。"""
        R = self.R
        robots = self.robots[:]
        if not self.disable_random:
            self.rng.shuffle(robots)
        for r in robots:
            if r.touch:
                tvx, tvy, tvz = r.a_tvx, r.a_tvy, r.a_tvz
                ln = math.sqrt(tvx * tvx + tvy * tvy + tvz * tvz)
                if ln > R["ROBOT_MAX_GROUND_SPEED"]:
                    k = R["ROBOT_MAX_GROUND_SPEED"] / ln
                    tvx, tvy, tvz = tvx * k, tvy * k, tvz * k
                dot = r.tnx * tvx + r.tny * tvy + r.tnz * tvz
                tvx -= r.tnx * dot
                tvy -= r.tny * dot
                tvz -= r.tnz * dot
                cx, cy, cz = tvx - r.vx, tvy - r.vy, tvz - r.vz
                cl = math.sqrt(cx * cx + cy * cy + cz * cz)
                if cl > 0:
                    acc = R["ROBOT_ACCELERATION"] * max(0.0, r.tny)
                    step = min(acc * dt, cl)
                    r.vx += cx / cl * step
                    r.vy += cy / cl * step
                    r.vz += cz / cl * step
            if r.a_nitro:
                # target_velocity_change = clamp(target_velocity - velocity, nitro * NITRO_POINT_VELOCITY_CHANGE)
                cx, cy, cz = r.a_tvx - r.vx, r.a_tvy - r.vy, r.a_tvz - r.vz
                cl = math.sqrt(cx * cx + cy * cy + cz * cz)
                lim = r.nitro * R["NITRO_POINT_VELOCITY_CHANGE"]
                if cl > lim:
                    cx, cy, cz = cx / cl * lim, cy / cl * lim, cz / cl * lim
                    cl = lim
                if cl > 0:
                    # velocity_change = clamp(normalize(change) * ROBOT_NITRO_ACCELERATION * dt, length(change))
                    step = min(R["ROBOT_NITRO_ACCELERATION"] * dt, cl)
                    r.vx += cx / cl * step
                    r.vy += cy / cl * step
                    r.vz += cz / cl * step
                    r.nitro -= step / R["NITRO_POINT_VELOCITY_CHANGE"]
                    r.nitro_used = True
            self._move(r, dt)
            js = r.a_jump
            r.radius = R["ROBOT_MIN_RADIUS"] + (R["ROBOT_MAX_RADIUS"] - R["ROBOT_MIN_RADIUS"]) * js / R["ROBOT_MAX_JUMP_SPEED"]
            r.radius_change_speed = js
        self._move(self.ball, dt)
        rs = self.robots
        for i in range(len(rs)):
            for j in range(i):
                self._collide_entities(rs[i], rs[j])
        for r in rs:
            self._collide_entities(r, self.ball)
            n = self._collide_with_arena(r)
            if n is None:
                r.touch = False
            else:
                r.touch = True
                r.tnx, r.tny, r.tnz = n
        self._collide_with_arena(self.ball)
        scored = None
        if abs(self.ball.z) > self.A["depth"] / 2 + self.ball.radius:
            scored = 0 if self.ball.z > 0 else 1
        if self.packs:
            for r in rs:
                if r.nitro >= R["MAX_NITRO_AMOUNT"]:
                    continue
                for p in self.packs:
                    if not p.alive:
                        continue
                    if math.sqrt((r.x - p.x) ** 2 + (r.y - p.y) ** 2 + (r.z - p.z) ** 2) <= r.radius + p.radius:
                        r.nitro = R["MAX_NITRO_AMOUNT"]
                        p.alive = False
                        p.respawn_ticks = R["NITRO_PACK_RESPAWN_TICKS"]
        return scored

    def tick(self) -> int | None:
        """一个 tick（拆成 microticks 个微步）。返回本 tick 的进球方或 None。"""
        dt = 1.0 / self.R["TICKS_PER_SECOND"] / self.microticks
        scored = None
        for r in self.robots:
            r.nitro_used = False
        for _ in range(self.microticks):
            s = self._update(dt)
            if s is not None and scored is None:
                scored = s
        for p in self.packs:
            if not p.alive:
                p.respawn_ticks -= 1
                if p.respawn_ticks == 0:
                    p.alive = True
        return scored
