"""平台射击赛起步程序：动作结构、基础策略与逐行 JSON 通信。"""
import json
import sys
from types import SimpleNamespace


# ---------- 动作与地块定义 ----------
class Tile:
    EMPTY, WALL, PLATFORM, LADDER, JUMP_PAD = "EMPTY", "WALL", "PLATFORM", "LADDER", "JUMP_PAD"


class WeaponType:
    PISTOL, ASSAULT_RIFLE, ROCKET_LAUNCHER = "PISTOL", "ASSAULT_RIFLE", "ROCKET_LAUNCHER"


class Vec2Double:
    def __init__(self, x, y):
        self.x, self.y = x, y


class UnitAction:
    def __init__(self, velocity=0.0, jump=False, jump_down=False, aim=None, shoot=False,
                 reload=False, swap_weapon=False, plant_mine=False):
        self.velocity, self.jump, self.jump_down = velocity, jump, jump_down
        self.aim = aim or Vec2Double(0, 0)
        self.shoot, self.reload, self.swap_weapon, self.plant_mine = shoot, reload, swap_weapon, plant_mine

    def to_json(self):
        return {"velocity": self.velocity, "jump": self.jump, "jump_down": self.jump_down,
                "aim": {"x": self.aim.x, "y": self.aim.y}, "shoot": self.shoot, "reload": self.reload,
                "swap_weapon": self.swap_weapon, "plant_mine": self.plant_mine}


class Debug:
    """不提供调试绘图；log 写入标准错误。"""
    def draw(self, data):
        pass

    def log(self, text):
        print(text, file=sys.stderr)


# ---------- 策略 ----------
class MyStrategy:
    def get_action(self, unit, game, debug):
        def distance_sqr(a, b):
            return (a.x - b.x) ** 2 + (a.y - b.y) ** 2
        nearest_enemy = min(
            filter(lambda u: u.player_id != unit.player_id, game.units),
            key=lambda u: distance_sqr(u.position, unit.position),
            default=None)
        nearest_weapon = min(
            filter(lambda box: box.item.type == "Weapon", game.loot_boxes),
            key=lambda box: distance_sqr(box.position, unit.position),
            default=None)
        target_pos = unit.position
        if unit.weapon is None and nearest_weapon is not None:
            target_pos = nearest_weapon.position
        elif nearest_enemy is not None:
            target_pos = nearest_enemy.position
        aim = Vec2Double(0, 0)
        if nearest_enemy is not None:
            aim = Vec2Double(
                nearest_enemy.position.x - unit.position.x,
                nearest_enemy.position.y - unit.position.y)
        jump = target_pos.y > unit.position.y
        if target_pos.x > unit.position.x and game.level.tiles[int(unit.position.x + 1)][int(unit.position.y)] == Tile.WALL:
            jump = True
        if target_pos.x < unit.position.x and game.level.tiles[int(unit.position.x - 1)][int(unit.position.y)] == Tile.WALL:
            jump = True
        return UnitAction(
            velocity=target_pos.x - unit.position.x,
            jump=jump,
            jump_down=not jump,
            aim=aim,
            shoot=True,
            reload=False,
            swap_weapon=False,
            plant_mine=False)


# ---------- Runner：收发 JSON ----------
def to_obj(v):
    if isinstance(v, dict):
        return SimpleNamespace(**{k: to_obj(x) for k, x in v.items()})
    if isinstance(v, list):
        return [to_obj(x) for x in v]
    return v


def main():
    strategy, debug = MyStrategy(), Debug()
    properties = level = None
    for line in sys.stdin:
        msg = json.loads(line)
        if msg["type"] == "init":
            properties = to_obj(msg["properties"])
            level = SimpleNamespace(tiles=msg["level"]["tiles"])   # tiles[x][y]，保持为字符串列表
            print(json.dumps({"ready": True}), flush=True)
        elif msg["type"] == "turn":
            view = msg["player_view"]
            game = to_obj(view["game"])
            game.properties, game.level = properties, level
            actions = {}
            for unit in game.units:
                if unit.player_id == view["my_id"]:
                    actions[str(unit.id)] = strategy.get_action(unit, game, debug).to_json()
            print(json.dumps({"tick": msg["tick"], "actions": actions}), flush=True)
        elif msg["type"] == "end":
            break


if __name__ == "__main__":
    main()
