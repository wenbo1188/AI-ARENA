"""战术机器人：一名门将 + 其余前锋，写法和原版 CodeBall 的 Python 语言包一样（MyStrategy.act）。

前锋：用简化物理预测球的轨迹，找到最早能赶到、并且能从球后方撞向对方球门的拦截点，
      跑过去并在接近时起跳顶球；远距离冲刺和空中追球时开氮气，氮气不多时顺路去捡氮气瓶。
门将：守在球门线前，根据球的预测落点左右移动；球进入危险区时出击解围。
"""
import json
import math
import sys
from types import SimpleNamespace

DT = 1 / 60


def unit(x, z):
    n = math.hypot(x, z)
    return (x / n, z / n) if n > 1e-9 else (0.0, 0.0)


class Action:
    def __init__(self):
        self.target_velocity_x = 0.0
        self.target_velocity_y = 0.0
        self.target_velocity_z = 0.0
        self.jump_speed = 0.0
        self.use_nitro = False


class MyStrategy:
    def __init__(self):
        self.path_tick = -1
        self.path = []

    # ---------- 预测 ----------
    def predict_ball(self, rules, ball, ticks):
        """简化的球轨迹预测：重力 + 地面/四周墙面反弹（不考虑圆角和球门），每 tick 一个点。"""
        arena = rules.arena
        g, e, r = rules.GRAVITY, rules.BALL_ARENA_E, ball.radius
        w2, d2 = arena.width / 2 - r, arena.depth / 2 - r
        gw2 = arena.goal_width / 2
        x, y, z = ball.x, ball.y, ball.z
        vx, vy, vz = ball.velocity_x, ball.velocity_y, ball.velocity_z
        path = []
        for _ in range(ticks):
            x += vx * DT
            z += vz * DT
            y += vy * DT - g * DT * DT / 2
            vy -= g * DT
            if y < r and vy < 0:
                y, vy = r, -vy * e
            if y > arena.height - r and vy > 0:
                y, vy = arena.height - r, -vy * e
            if abs(x) > w2:
                x, vx = math.copysign(w2, x), -vx * e
            if abs(z) > d2 and (abs(x) > gw2 - r or y > arena.goal_height - r):
                z, vz = math.copysign(d2, z), -vz * e
            path.append((x, y, z))
        return path

    # ---------- 角色 ----------
    def attacker(self, me, rules, ball):
        arena, vmax = rules.arena, rules.ROBOT_MAX_GROUND_SPEED
        goal = (0.0, arena.depth / 2 + 2)
        br, rr = ball.radius, me.radius
        # 找最早可达的拦截点：球不太高，机器人能在 t 秒内跑到"球后方"那个点
        for i, (bx, by, bz) in enumerate(self.path):
            t = (i + 1) * DT
            if by > br + 2.5:  # 太高顶不到
                continue
            dx, dz = unit(goal[0] - bx, goal[1] - bz)
            px, pz = bx - dx * (br + rr) * 0.9, bz - dz * (br + rr) * 0.9
            dist = math.hypot(px - me.x, pz - me.z)
            if dist / vmax <= t * 0.85:
                need = dist / t
                ux, uz = unit(px - me.x, pz - me.z)
                speed = vmax if need > vmax * 0.6 else max(need, 5.0)
                # 已经在球后方且很近时，直接全速冲向球
                if dist < 3 and me.z < bz:
                    ux, uz = unit(bx - me.x, bz - me.z)
                    speed = vmax
                return ux * speed, uz * speed
        # 找不到：跑向半秒后球所在位置的后方（相对对方球门）
        bx, by, bz = self.path[min(30, len(self.path) - 1)]
        dx, dz = unit(goal[0] - bx, goal[1] - bz)
        px, pz = bx - dx * (br + rr + 1), bz - dz * (br + rr + 1)
        ux, uz = unit(px - me.x, pz - me.z)
        return ux * vmax, uz * vmax

    def keeper(self, me, rules, ball):
        arena, vmax = rules.arena, rules.ROBOT_MAX_GROUND_SPEED
        d2, gw2 = arena.depth / 2, arena.goal_width / 2
        tx, tz = 0.0, -d2 + 2.5
        # 球门线上的预测落点
        for (bx, by, bz) in self.path:
            if bz < -d2 + 4:
                tx = max(-gw2 + 2, min(gw2 - 2, bx))
                break
        else:
            tx = max(-gw2 + 4, min(gw2 - 4, ball.x * 0.5))
        # 球很近：出击
        if ball.z < -d2 + 22 and math.hypot(ball.x - me.x, ball.z - me.z) < 12:
            return self.attacker(me, rules, ball)
        dx, dz = tx - me.x, tz - me.z
        d = math.hypot(dx, dz)
        k = min(vmax, d * 6) / d if d > 1e-6 else 0
        return dx * k, dz * k

    def nitro_pack_detour(self, me, rules, game):
        """氮气不足、球又离得远时，去捡最近的氮气瓶。"""
        ball = game.ball
        if me.nitro_amount > 40 or math.hypot(ball.x - me.x, ball.z - me.z) < 18:
            return None
        best = None
        for p in game.nitro_packs:
            if p.respawn_ticks is not None:  # 还没刷新出来
                continue
            d = math.hypot(p.x - me.x, p.z - me.z)
            if d < 14 and (best is None or d < best[0]):
                best = (d, p)
        if best is None:
            return None
        ux, uz = unit(best[1].x - me.x, best[1].z - me.z)
        v = rules.ROBOT_MAX_GROUND_SPEED
        return ux * v, uz * v

    def air_nitro(self, me, rules, ball, action):
        """在空中：球就在附近时开氮气朝球的后方（相对对方球门）飞过去。"""
        if me.nitro_amount <= 0:
            return False
        gx, gz = unit(-ball.x, rules.arena.depth / 2 + 2 - ball.z)
        tx, ty, tz = ball.x - gx * 1.2, ball.y, ball.z - gz * 1.2
        dx, dy, dz = tx - me.x, ty - me.y, tz - me.z
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d > 9 or d < 1e-6:
            return False
        v = rules.MAX_ENTITY_SPEED
        action.target_velocity_x, action.target_velocity_y, action.target_velocity_z = dx / d * v, dy / d * v, dz / d * v
        action.use_nitro = True
        return True

    # ---------- 每个机器人每 tick 调用一次 ----------
    def act(self, me, rules, game, action):
        ball = game.ball
        if self.path_tick != game.current_tick:  # 每个 tick 只预测一次
            self.path_tick = game.current_tick
            self.path = self.predict_ball(rules, ball, 120)
        if not me.touch:
            # 在空中只有氮气能改变速度：球在附近就喷氮气追过去，否则保持向下
            if not self.air_nitro(me, rules, ball, action):
                action.target_velocity_y = -rules.MAX_ENTITY_SPEED
            return
        mates = [r for r in game.robots if r.is_teammate]
        keeper = min(mates, key=lambda r: (r.z, r.id)) if len(mates) > 1 else None
        if keeper is not None and me.id == keeper.id:
            vx, vz = self.keeper(me, rules, ball)
        else:
            vx, vz = self.nitro_pack_detour(me, rules, game) or self.attacker(me, rules, ball)
            # 远距离全速冲刺时开氮气（地面上氮气让加速更快）
            far = math.hypot(ball.x - me.x, ball.z - me.z)
            action.use_nitro = me.nitro_amount > 30 and far > 10 and math.hypot(vx, vz) > rules.ROBOT_MAX_GROUND_SPEED * 0.9
        action.target_velocity_x, action.target_velocity_z = vx, vz
        dist = math.dist((me.x, me.y, me.z), (ball.x, ball.y, ball.z))
        # 球在前方、够得着、并且比自己高一点时起跳
        if dist < ball.radius + rules.ROBOT_MAX_RADIUS + 1.2 and ball.y > me.y and ball.z > me.z - 0.5:
            action.jump_speed = rules.ROBOT_MAX_JUMP_SPEED


def to_obj(v):
    if isinstance(v, dict):
        return SimpleNamespace(**{k: to_obj(x) for k, x in v.items()})
    if isinstance(v, list):
        return [to_obj(x) for x in v]
    return v


def main():
    strategy, rules = MyStrategy(), None
    for line in sys.stdin:
        msg = json.loads(line)
        if msg["type"] == "init":
            rules = to_obj(msg["rules"])
            print(json.dumps({"ready": True}), flush=True)
        elif msg["type"] == "turn":
            game = to_obj(msg["game"])
            actions = {}
            for robot in game.robots:
                if robot.is_teammate:
                    action = Action()
                    strategy.act(robot, rules, game, action)
                    actions[str(robot.id)] = vars(action)
            print(json.dumps({"tick": msg["tick"], "actions": actions}), flush=True)
        elif msg["type"] == "end":
            break


if __name__ == "__main__":
    main()
