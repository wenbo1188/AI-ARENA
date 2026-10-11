"""起步策略：修改 MyStrategy.act；底部负责 JSON 收发。"""
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
    """入门基准：角色分工、直线预测拦截和守门。"""
    def act(self, me, rules, game, action):
        if not me.touch:
            action.target_velocity_y = -rules.MAX_ENTITY_SPEED
            action.use_nitro = True
            return
        ball, arena = game.ball, rules.arena
        action.jump_speed = rules.ROBOT_MAX_JUMP_SPEED if (
            math.dist((me.x,me.y,me.z),(ball.x,ball.y,ball.z)) < ball.radius+rules.ROBOT_MAX_RADIUS
            and me.z < ball.z) else 0
        if len(game.robots)==2 or any(r.is_teammate and r.id!=me.id and r.z<me.z for r in game.robots):
            for i in range(1,101):
                t=i/10; x=ball.x+ball.velocity_x*t; z=ball.z+ball.velocity_z*t
                if z>me.z and abs(x)<arena.width/2 and abs(z)<arena.depth/2:
                    dx,dz=x-me.x,z-me.z; speed=math.hypot(dx,dz)/t
                    if rules.ROBOT_MAX_GROUND_SPEED/2 < speed < rules.ROBOT_MAX_GROUND_SPEED:
                        action.target_velocity_x=dx/t; action.target_velocity_z=dz/t
                        return
        x,z=0,-arena.depth/2+arena.bottom_radius
        if ball.velocity_z < -1e-5:
            cross=ball.x+ball.velocity_x*(z-ball.z)/ball.velocity_z
            if abs(cross)<arena.goal_width/2: x=cross
        action.target_velocity_x=(x-me.x)*rules.ROBOT_MAX_GROUND_SPEED
        action.target_velocity_z=(z-me.z)*rules.ROBOT_MAX_GROUND_SPEED


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
