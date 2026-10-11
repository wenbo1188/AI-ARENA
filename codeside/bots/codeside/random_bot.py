"""最简单的 CodeSide 机器人：随机跑跳，朝随机方向开火。演示最小的协议。"""
import json
import random
import sys

for line in sys.stdin:
    msg = json.loads(line)
    if msg["type"] == "init":
        print(json.dumps({"ready": True}), flush=True)
    elif msg["type"] == "turn":
        view = msg["player_view"]
        actions = {}
        for u in view["game"]["units"]:
            if u["player_id"] == view["my_id"]:
                actions[str(u["id"])] = {
                    "velocity": random.uniform(-10, 10), "jump": random.random() < 0.5,
                    "jump_down": random.random() < 0.2,
                    "aim": {"x": random.uniform(-1, 1), "y": random.uniform(-1, 1)},
                    "shoot": True, "reload": False, "swap_weapon": False, "plant_mine": random.random() < 0.01}
        print(json.dumps({"tick": msg["tick"], "actions": actions}), flush=True)
    elif msg["type"] == "end":
        break
