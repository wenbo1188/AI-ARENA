"""入门机器人：所有机器人都跑到球的后方（相对对方球门）去撞球，球在身前且够得着时起跳。

写法和原版 CodeBall 的 Python 语言包一样：实现 MyStrategy.act(me, rules, game, action)，
下面的 main() 相当于官方的 Runner.py，负责收发 JSON。可以复制这个文件当模板。
记住：己方球门永远在 z < 0 一侧，对方球门在 z = +(depth/2) 方向。
"""
import json
import math
import sys
from types import SimpleNamespace


class Action:
    def __init__(self):
        self.target_velocity_x = 0.0
        self.target_velocity_y = 0.0
        self.target_velocity_z = 0.0
        self.jump_speed = 0.0
        self.use_nitro = False


class MyStrategy:
    def act(self, me, rules, game, action):
        ball, arena = game.ball, rules.arena
        goal_z = arena.depth / 2 + arena.goal_depth / 2
        # 从对方球门指向球的方向，机器人要站到球的这一侧再往前冲
        gx, gz = ball.x, ball.z - goal_z
        n = math.hypot(gx, gz) or 1.0
        tx, tz = ball.x + gx / n * 2.5, ball.z + gz / n * 2.5
        if me.z < ball.z - 1:          # 已经在球后方：直接冲向球
            tx, tz = ball.x, ball.z
        dx, dz = tx - me.x, tz - me.z
        d = math.hypot(dx, dz) or 1.0
        speed = rules.ROBOT_MAX_GROUND_SPEED
        action.target_velocity_x = dx / d * speed
        action.target_velocity_z = dz / d * speed
        dist = math.dist((me.x, me.y, me.z), (ball.x, ball.y, ball.z))
        if dist < ball.radius + 1.5 * me.radius + 1 and ball.z > me.z:
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
