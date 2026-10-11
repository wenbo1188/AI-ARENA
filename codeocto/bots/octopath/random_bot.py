"""八方旅人对决：最简单的示例，随机选人、随机配置、随机出招。演示协议用。"""
import json
import random
import sys

rng = random.Random()
info = None
for line in sys.stdin:
    msg = json.loads(line)
    if msg["type"] == "init":
        info = msg
        print(json.dumps({"ready": True}), flush=True)
    elif msg["type"] == "turn":
        reply = {"tick": msg["tick"]}
        if msg["your_turn"]:
            if msg["phase"] == "pick":
                reply["pick"] = rng.sample(msg["available"], msg["pick_count"])
            elif msg["phase"] == "loadout":
                # 随机副职、随机学几个副职技能（每人不超过平分的 JP），支援技能从本职的里随机挑
                rules = info["loadout_rules"]
                share = rules["budget"]["jp"] // len(msg["my_picks"])
                lo = []
                for k in msg["my_picks"]:
                    own = info["travelers"][k]["job_en"]
                    sub = rng.choice([j for j in rules["jobs"] if j != own])
                    job = rules["jobs"][sub]
                    pool = [s for s in job["skills"] if s not in job["free_skills"] and s != job["divine"]]
                    n = 0
                    while n < len(pool) and sum(rules["jp_costs"][:n + 1]) <= share:
                        n += 1
                    sups = [s for s in rules["jobs"][own]["supports"] if rules["supports"][s]["battle"]]
                    lo.append({"sub_job": sub, "learn": rng.sample(pool, rng.randint(0, n)),
                               "supports": rng.sample(sups, min(len(sups), rules["support_slots"]))})
                reply["loadout"] = lo
                # 随机买道具，直到钱不够
                gold, bag = rules["budget"]["gold"], {}
                items = list(rules["items"].items())
                for _ in range(40):
                    k, v = rng.choice(items)
                    if v["price"] <= gold and bag.get(k, 0) < rules["item_stack"]:
                        bag[k] = bag.get(k, 0) + 1
                        gold -= v["price"]
                reply["items"] = bag
            else:
                me = msg["me"][msg["actor"]]
                skills = [s["id"] for s in msg["available_skills"] if s["usable"]]
                skill = rng.choice(skills)
                ally_skill = skill in info["skills"] and info["skills"][skill]["target"].startswith("ally")
                pool = msg["me"] if ally_skill else [u for u in msg["opponents"] if u["alive"]]
                reply["action"] = {
                    "skill": skill,
                    "target": rng.choice(pool)["id"] if pool else 0,
                    "boost": rng.randint(0, min(1, me["bp"])),
                    "latent": me["latent_ready"],
                    "recipe": rng.choice(list(info["concoct_recipes"])),
                }
                if skill == "item":
                    it = rng.choice(msg["usable_items"])
                    kind = info["loadout_rules"]["items"][it]["target"]
                    pool = [u for u in msg["opponents"] if u["alive"]] if kind.startswith("enem") else \
                        [u for u in msg["me"] if not u["alive"]] if kind == "ko" else [u for u in msg["me"] if u["alive"]]
                    reply["action"].update(item=it, target=rng.choice(pool)["id"] if pool else 0)
        print(json.dumps(reply), flush=True)
    elif msg["type"] == "end":
        break
