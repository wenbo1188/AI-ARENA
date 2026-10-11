"""最简单的机器人：随机乱跑、偶尔乱跳。用来当陪练和最小协议示例（不用官方风格的包装，直接读写 JSON）。"""
import json
import random
import sys

for line in sys.stdin:
    msg = json.loads(line)
    if msg["type"] == "init":
        print(json.dumps({"ready": True}), flush=True)
    elif msg["type"] == "turn":
        actions = {}
        for r in msg["game"]["robots"]:
            if r["is_teammate"]:
                actions[str(r["id"])] = {"target_velocity_x": random.uniform(-30, 30), "target_velocity_y": 0,
                                         "target_velocity_z": random.uniform(-30, 30),
                                         "jump_speed": 15 if random.random() < 0.02 else 0, "use_nitro": False}
        print(json.dumps({"tick": msg["tick"], "actions": actions}), flush=True)
    elif msg["type"] == "end":
        break
