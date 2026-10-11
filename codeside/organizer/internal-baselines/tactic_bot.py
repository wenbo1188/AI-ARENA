"""示例战术机器人：地块寻路 + 视线判断再开火。

- 没枪先捡最近的枪（优先突击步枪），血少时去捡医疗包；
- 在可站立格子上做 BFS 寻路（走、爬梯子、跳上去、掉下去），沿路径移动；
- 只有射线不穿墙、不会打到队友、火箭不会炸到自己时才开火；有敌方子弹飞来时跳起躲避。
"""
import heapq
import json
import math
import sys
from collections import deque
from types import SimpleNamespace

WALL, PLATFORM, LADDER, JUMP_PAD, EMPTY = "WALL", "PLATFORM", "LADDER", "JUMP_PAD", "EMPTY"


class Planner:
    def __init__(self, props, tiles):
        self.p = props
        self.t = tiles
        self.W, self.H = len(tiles), len(tiles[0])
        self.stand = [[self._standable(x, y) for y in range(self.H)] for x in range(self.W)]
        self.adj = {}
        for x in range(self.W):
            for y in range(self.H):
                if self.stand[x][y]:
                    self.adj[(x, y)] = self._edges(x, y)

    def tile(self, x, y):
        if 0 <= x < self.W and 0 <= y < self.H:
            return self.t[x][y]
        return WALL

    def free(self, x, y):
        return self.tile(x, y) != WALL and self.tile(x, y + 1) != WALL

    def _standable(self, x, y):
        if not self.free(x, y):
            return False
        below = self.tile(x, y - 1)
        return below in (WALL, PLATFORM, LADDER) or self.tile(x, y) == LADDER

    def _edges(self, x, y):
        out = []
        for dx in (-1, 1):
            nx = x + dx
            if not self.free(nx, y):
                continue
            ny = y
            while ny > 0 and not self._standable(nx, ny) and self.free(nx, ny - 1):
                ny -= 1
            if self._standable(nx, ny):
                out.append(((nx, ny), 1 + (y - ny) * 0.3))
        # 梯子上下
        for dy in (-1, 1):
            if self.tile(x, y + dy) == LADDER or (dy == 1 and self.tile(x, y) == LADDER):
                if self._standable(x, y + dy):
                    out.append(((x, y + dy), 1))
        # 往上跳：最多 5 格高、左右 2 格
        for dy in range(1, 6):
            if not self.free(x, y + dy):
                break
            for dx in (-2, -1, 0, 1, 2):
                nx, ny = x + dx, y + dy
                if dx and not all(self.free(x + s, y + dy) for s in range(0, dx + (1 if dx > 0 else -1), 1 if dx > 0 else -1)):
                    continue
                if self._standable(nx, ny) and self.tile(nx, ny - 1) in (WALL, PLATFORM, LADDER):
                    out.append(((nx, ny), 1.5 + dy * 0.5 + abs(dx) * 0.5))
        # 跳板：跳得高得多（20 × 0.525 ≈ 10 格），而且不能中途取消
        if self.tile(x, y) == JUMP_PAD:
            for dy in range(1, 11):
                if not self.free(x, y + dy):
                    break
                for dx in (-1, 0, 1):
                    if (self._standable(x + dx, y + dy) and self.tile(x + dx, y + dy - 1) in (WALL, PLATFORM, LADDER)
                            and all(self.free(x + dx, y + h) for h in range(max(1, dy - 2), dy + 1))):
                        out.append(((x + dx, y + dy), 3 + abs(dx) * 0.5))
        # 从平台跳下
        if self.tile(x, y - 1) in (PLATFORM, LADDER):
            ny = y - 1
            while ny > 0 and not (self.tile(x, ny - 1) in (WALL, PLATFORM)) and self.free(x, ny - 1):
                ny -= 1
            if ny != y and self._standable(x, ny):
                out.append(((x, ny), 1 + (y - ny) * 0.2))
        return out

    def landing_cell(self, x, y):
        """单位脚下（会落到）的可站立格子：从当前高度往下找。"""
        cx, cy = int(x), int(y + 0.01)
        for yy in range(cy, max(-1, cy - 30), -1):
            if (cx, yy) in self.adj:
                return (cx, yy)
            if not self.free(cx, yy - 1) and self.tile(cx, yy - 1) == WALL:
                break
        return self.nearest_stand(x, y + 0.01)

    def nearest_stand(self, x, y):
        x, y = int(x), int(y)
        for r in range(0, 6):
            for dy in range(-r, r + 1):
                for dx in (-r, r) if abs(dy) != r else range(-r, r + 1):
                    if (x + dx, y + dy) in self.adj:
                        return (x + dx, y + dy)
        return None

    def path(self, start, goal):
        """Dijkstra，返回 (下一步格子, 总代价)，走不到返回 None。"""
        if start is None or goal is None:
            return None
        if start == goal:
            return goal, 0.0
        prev, dist = {start: None}, {start: 0.0}
        heap = [(0.0, start)]
        while heap:
            d, cur = heapq.heappop(heap)
            if cur == goal:
                break
            if d > dist[cur]:
                continue
            for nxt, w in self.adj.get(cur, ()):
                nd = d + w
                if nd < dist.get(nxt, 1e9):
                    dist[nxt] = nd
                    prev[nxt] = cur
                    heapq.heappush(heap, (nd, nxt))
        if goal not in prev:
            return None
        node = goal
        while prev[node] != start:
            node = prev[node]
        return node, dist[goal]

    def all_dist(self, start):
        """从 start 出发到所有格子的最短代价（用来判断战利品能不能走到、哪个最近）。"""
        dist = {start: 0.0}
        heap = [(0.0, start)]
        while heap:
            d, cur = heapq.heappop(heap)
            if d > dist[cur]:
                continue
            for nxt, w in self.adj.get(cur, ()):
                nd = d + w
                if nd < dist.get(nxt, 1e9):
                    dist[nxt] = nd
                    heapq.heappush(heap, (nd, nxt))
        return dist

    def clear_line(self, x0, y0, x1, y1, half=0.1):
        n = int(math.hypot(x1 - x0, y1 - y0) * 4) + 1
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            y = y0 + (y1 - y0) * i / n
            for cx, cy in ((x - half, y - half), (x + half, y + half), (x - half, y + half), (x + half, y - half)):
                if self.tile(int(math.floor(cx)), int(math.floor(cy))) == WALL:
                    return False, (x, y)
        return True, (x1, y1)


class MyStrategy:
    def __init__(self):
        self.planner = None
        self.claimed = {}       # 本 tick 队友已经选定的战利品，避免两人抢同一个
        self.claim_tick = -1
        self.commit = {}        # 单位 id -> (正在去的相邻格子, 开始的 tick)

    def get_action(self, unit, game, props):
        P = self.planner
        me = unit.position
        cx, cy = me.x, me.y + unit.size.y / 2
        enemies = [u for u in game.units if u.player_id != unit.player_id]
        mates = [u for u in game.units if u.player_id == unit.player_id and u.id != unit.id]
        start = P.landing_cell(me.x, me.y)

        if game.current_tick != self.claim_tick:
            self.claim_tick, self.claimed = game.current_tick, {}
        taken = {k for uid, k in self.claimed.items() if uid != unit.id}

        def boxes(kind, wt=None):
            return [b for b in game.loot_boxes if b.item.type == kind and (wt is None or b.item.weapon_type == wt)
                    and (b.position.x, b.position.y) not in taken]

        # ---- 选目标（按寻路距离，走不到的不考虑） ----
        dist = P.all_dist(start) if start else {}

        def reach(b):
            n = P.nearest_stand(b.position.x, b.position.y + 0.01)
            return dist.get(n, 1e9)

        target = None
        swap = False
        if unit.weapon is None:
            cands = [b for b in boxes("Weapon") if reach(b) < 1e9]
            if cands:
                target = min(cands, key=lambda b: reach(b) - (6 if b.item.weapon_type == "ASSAULT_RIFLE" else 0)).position
        elif unit.weapon.typ != "ASSAULT_RIFLE" and boxes("Weapon", "ASSAULT_RIFLE"):
            b = min(boxes("Weapon", "ASSAULT_RIFLE"), key=reach)
            if reach(b) < 12:
                target, swap = b.position, True
        if target is None and unit.health < 70:
            packs = [b for b in boxes("HealthPack") if reach(b) < 1e9]
            if packs:
                target = min(packs, key=reach).position
        if target is not None:
            self.claimed[unit.id] = (target.x, target.y)
        enemy = min(enemies, key=lambda e: (e.position.x - me.x) ** 2 + (e.position.y - me.y) ** 2, default=None)
        if target is None and enemy is not None:
            target = enemy.position
            ok, _ = P.clear_line(cx, cy, enemy.position.x, enemy.position.y + enemy.size.y / 2)
            d = math.hypot(enemy.position.x - me.x, enemy.position.y - me.y)
            if ok and d < 9 and unit.weapon is not None:
                target = None            # 有视线且距离合适：原地附近打
        # ---- 走路 ----
        velocity, jump, jump_down = 0.0, False, False
        if target is not None:
            goal = P.nearest_stand(target.x, target.y + 0.01)
            # 跳跃过程中坚持上一次选定的落脚点，避免在空中改主意把跳跃取消
            commit = self.commit.get(unit.id)
            if commit and (game.current_tick - commit[1] > 90 or
                           (-0.02 < me.y - commit[0][1] < 0.4 and abs(me.x - commit[0][0] - 0.5) < 0.7)):
                commit = None
            if commit is None:
                step = P.path(start, goal)
                nxt = step[0] if step else None
                if nxt is not None and start is not None and nxt[1] != start[1]:
                    self.commit[unit.id] = (nxt, game.current_tick, nxt[1] > start[1])
                else:
                    self.commit.pop(unit.id, None)
            else:
                nxt = commit[0]
            if nxt is None:
                tx, ty = target.x, target.y
            else:
                tx, ty = nxt[0] + 0.5, nxt[1]
                if goal == nxt:
                    tx = target.x
            velocity = max(-10.0, min(10.0, (tx - me.x) * 12))
            going_up = unit.id in self.commit and self.commit[unit.id][2]
            if ty > me.y + 0.2 or (going_up and me.y < ty + 0.3):
                jump = True          # 往上的一步：跳到比落脚点稍高再松开，让单位落到平台上
            elif ty < me.y - (0.05 if unit.on_ladder else 0.4):
                jump_down = True
            ahead = P.tile(int(me.x + (0.6 if velocity > 0 else -0.6)), int(me.y))
            if ahead == WALL and abs(velocity) > 0.5:
                jump = True
        elif enemy is not None:
            # 和敌人保持距离，左右小幅晃动
            dx = enemy.position.x - me.x
            want = 6.0 if unit.weapon and unit.weapon.typ == "ROCKET_LAUNCHER" else 4.0
            velocity = -10.0 if abs(dx) < want and dx > 0 else (10.0 if abs(dx) < want else 0.0)
            velocity += 6.0 * math.sin(game.current_tick / 9.0 + unit.id)
        # 队友挡路：id 大的往远离队友的方向让开；让不开（贴墙）就照常走，id 小的那个跳过去
        for m in mates:
            dx = m.position.x - me.x
            if abs(dx) < 1.3 and abs(m.position.y - me.y) < 2.0:
                away = -1 if dx > 0 else 1
                if m.id < unit.id and P.tile(int(me.x + away * 0.9), int(me.y + 0.1)) != WALL:
                    velocity, jump, jump_down = away * 10.0, False, False
                elif m.id > unit.id and dx * velocity > 0:
                    jump = True
        # 躲子弹
        for b in game.bullets:
            if b.player_id == unit.player_id:
                continue
            rx, ry = cx - b.position.x, cy - b.position.y
            v2 = b.velocity.x ** 2 + b.velocity.y ** 2
            t = (rx * b.velocity.x + ry * b.velocity.y) / v2 if v2 else -1
            if 0 < t < 0.35:
                px, py = b.position.x + b.velocity.x * t, b.position.y + b.velocity.y * t
                if abs(px - cx) < 0.8 and abs(py - cy) < 1.3:
                    jump = py < cy + 0.3
                    jump_down = not jump
        # ---- 瞄准和开火 ----
        aim = {"x": 0.0, "y": 0.0}
        shoot = False
        reload = False
        plant = False
        if enemy is not None and unit.weapon is not None:
            ex = enemy.position.x
            ey = enemy.position.y + enemy.size.y / 2
            aim = {"x": ex - cx, "y": ey - cy}
            ok, hit = P.clear_line(cx, cy, ex, ey, half=unit.weapon.params.bullet.size / 2)
            if ok:
                shoot = True
                for m in mates:
                    mx, my = m.position.x, m.position.y + m.size.y / 2
                    # 队友在射线附近就不开火
                    vx, vy = ex - cx, ey - cy
                    L2 = vx * vx + vy * vy or 1
                    s = ((mx - cx) * vx + (my - cy) * vy) / L2
                    if 0 < s < 1 and abs((mx - cx) * vy - (my - cy) * vx) / math.sqrt(L2) < 1.0:
                        shoot = False
            if unit.weapon.typ == "ROCKET_LAUNCHER":
                r = unit.weapon.params.explosion.radius
                if abs(hit[0] - cx) < r + 0.6 and abs(hit[1] - cy) < r + 1.0:
                    shoot = False
            if not shoot and unit.weapon.magazine < unit.weapon.params.magazine_size / 2 and \
                    math.hypot(enemy.position.x - me.x, enemy.position.y - me.y) > 12:
                reload = True
            if unit.mines > 0 and unit.on_ground and math.hypot(enemy.position.x - me.x, enemy.position.y - me.y) < 2.5 \
                    and unit.health > enemy.health:
                plant = True
        return {"velocity": velocity, "jump": jump, "jump_down": jump_down and not jump, "aim": aim,
                "shoot": shoot, "reload": reload, "swap_weapon": swap, "plant_mine": plant}


def to_obj(v):
    if isinstance(v, dict):
        return SimpleNamespace(**{k: to_obj(x) for k, x in v.items()})
    if isinstance(v, list):
        return [to_obj(x) for x in v]
    return v


def main():
    strategy = MyStrategy()
    props = None
    for line in sys.stdin:
        msg = json.loads(line)
        if msg["type"] == "init":
            props = to_obj(msg["properties"])
            strategy.planner = Planner(props, msg["level"]["tiles"])
            print(json.dumps({"ready": True}), flush=True)
        elif msg["type"] == "turn":
            view = msg["player_view"]
            game = to_obj(view["game"])
            actions = {}
            for unit in game.units:
                if unit.player_id == view["my_id"]:
                    actions[str(unit.id)] = strategy.get_action(unit, game, props)
            print(json.dumps({"tick": msg["tick"], "actions": actions}), flush=True)
        elif msg["type"] == "end":
            break


if __name__ == "__main__":
    main()
