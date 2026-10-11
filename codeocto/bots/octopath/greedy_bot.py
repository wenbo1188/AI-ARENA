"""八方旅人对决：贪心示例。

思路：
- 选人：神官（治疗/复活）+ 学者（全体魔法）+ 剑士（耐打输出）+ 盗贼（快、多种弱点覆盖）。
- 行动：先救人（复活/治疗），否则枚举所有伤害技能 × 目标，估算"伤害 + 削盾价值"，取最高；
  目标已被击破时把 BP 全压上（击破期间伤害翻倍），BP 快满时也用掉，平时攒着。
- 辅助：增益、减益、状态技能按粗略价值打分（身上已有就不重复），比最好的输出差得不多时先上辅助。
- 赛前配置：按物攻型/属攻型给每人挑一个副职，JP 先平均分让每人解锁 3 个副职支援技能，剩下的给排在前面的人多学；
  支援技能按固定优先级挑 4 个。
- 道具：最多一半的钱买大复活道具（没有复活技能时用），其余买精灵石（当作一种攻击参与比较）。
"""
import json
import sys

info = None
PICK = ["temenos", "osvald", "hikari", "throne", "castti", "ochette", "agnea", "partitio"]
if len(sys.argv) > 1:  # 可以用命令行参数指定选人优先顺序，例如 agnea,ochette,castti,partitio
    PICK = sys.argv[1].split(",") + [k for k in PICK if k not in sys.argv[1].split(",")]


def est_damage(sk, me, foe, boost, c):
    """按文档里的公式估算一次技能对 foe 的伤害和削盾数。"""
    hits = sk.get("hits", 1)
    power = sk["power"]
    if sk.get("boost") == "power":
        power *= 1 + boost
    elif sk.get("boost") == "hits":
        lv = sk["levels"][boost]
        hits = (sum(lv) / 2 if isinstance(lv, list) else lv)
    if sk["kind"] == "phys":
        atk = me["stats"]["spd" if sk.get("use_spd") else "pa"]
        df = foe["stats"]["pd"]
    else:
        atk, df = me["stats"]["ea"], foe["stats"]["ed"]
    dmg = sk["fixed"] if sk.get("fixed") else max(1, atk * sk.get("invocation_values", [1]*4)[3 if sk.get("divine") else boost] - df / 2) * sk.get("ability_ratios", [power]*4)[3 if sk.get("divine") else boost] * c["level_multiplier"]
    typ = sk["type"]
    weak = typ in foe["weaknesses"] or (typ == "random_fil" and any(t in foe["weaknesses"] for t in ("fire", "ice", "lightning")) and 0.33)
    if weak and not foe["broken"] and not sk.get("fixed"):   # 道具的固定伤害不乘倍率
        dmg *= c["weak_mult"]
    if foe["broken"] and not sk.get("fixed"):
        dmg *= c["break_mult"]
    shields = 0 if foe["broken"] else (hits if weak is True else (hits * 0.33 if weak else 0)) + sk.get("shield_break", 0)
    if sk["target"] == "random":
        hits_on_this = hits / max(1, n_alive)
        return dmg * hits_on_this, shields / max(1, n_alive)
    return dmg * hits, shields


def score_target(dmg, shields, foe):
    v = min(dmg, foe["hp"])
    if foe["hp"] <= dmg:
        v += 2500                     # 能击倒
    if shields and not foe["broken"]:
        left = foe["shields"]
        v += 300 * min(shields, left)
        if shields >= left:
            v += 2200                 # 能击破
    return v


def decide(msg):
    global n_alive
    c = info["constants"]
    me = msg["me"][msg["actor"]]
    usable = sorted(s["id"] for s in msg["available_skills"] if s["usable"])
    foes = [u for u in msg["opponents"] if u["alive"]]
    allies = msg["me"]
    n_alive = len(foes)
    skills = info["skills"]
    act = {"skill": "attack", "target": foes[0]["id"], "boost": 0}

    dead = [a for a in allies if not a["alive"]]
    hurt = sorted([a for a in allies if a["alive"]], key=lambda a: a["hp"] / a["max_hp"])
    bag = msg.get("usable_items", [])
    items = info["loadout_rules"]["items"]
    fx = lambda k: items[k]["fx"]
    # 1. 复活
    if dead:
        if "revive" in usable and len(dead) >= 1:
            return {"skill": "revive", "boost": min(me["bp"], 2)}
        if "healing_touch" in usable:
            return {"skill": "healing_touch", "target": dead[0]["id"], "boost": min(me["bp"], 2)}
        if "concoct" in usable:
            return {"skill": "concoct", "recipe": "phoenix", "target": dead[0]["id"], "boost": min(me["bp"], 1),
                    "latent": me["latent_ready"]}
        rev = [k for k in bag if fx(k).get("revive")]
        if rev:
            return {"skill": "item", "item": max(rev, key=lambda k: fx(k)["revive"]), "target": dead[0]["id"]}
    # 2. 治疗
    low = [a for a in hurt if a["hp"] / a["max_hp"] < 0.4]
    if low:
        if "heal_wounds" in usable and (len(low) >= 2 or "healing_touch" not in usable):
            return {"skill": "heal_wounds", "boost": min(me["bp"], 1 + (len(low) >= 2))}
        if "healing_touch" in usable:
            return {"skill": "healing_touch", "target": low[0]["id"], "boost": min(me["bp"], 1)}
        if "concoct" in usable and len(low) >= 2:
            return {"skill": "concoct", "recipe": "elixir", "boost": min(me["bp"], 1), "latent": me["latent_ready"]}
        if me["traveler"] == "partitio" and low[0]["id"] == me["id"]:
            return {"skill": "rest", "boost": min(me["bp"], 2)}
        need = low[0]["max_hp"] - low[0]["hp"]
        heal = lambda k: fx(k).get("hp", 0) + fx(k).get("hp_pct", 0) * low[0]["max_hp"]
        group = [k for k in bag if heal(k) and items[k]["target"] == "allies"]
        single = [k for k in bag if heal(k) and items[k]["target"] == "ally"]
        if group and len(low) >= 2:
            return {"skill": "item", "item": max(group, key=heal)}
        if single:  # 够用的里面挑最便宜的，否则挑回复最多的
            enough = [k for k in single if heal(k) >= need * 0.6]
            k = min(enough, key=lambda k: items[k]["price"]) if enough else max(single, key=heal)
            return {"skill": "item", "item": k, "target": low[0]["id"]}
    # SP 不够放任何伤害技能时补 SP
    sp_items = [k for k in bag if fx(k).get("sp") or fx(k).get("sp_pct")]
    costs = [skills[s]["sp"] for s in me["skills"] if s in skills and "kind" in skills[s]]
    if sp_items and costs and me["sp"] < min(costs) and me["max_sp"] >= 2 * min(costs):
        return {"skill": "item", "item": min(sp_items, key=lambda k: items[k]["price"]), "target": me["id"]}

    # 3. 输出：枚举技能 × 目标 × 加成
    latent = me["latent_ready"] and me["traveler"] in ("hikari", "ochette", "temenos", "osvald", "agnea", "throne", "partitio")
    bp = 5 if (latent and me["traveler"] == "partitio") else me["bp"]
    best = None
    options = [("attack", w) for w in me["weapons"]]
    for sid in usable:
        sk = skills.get(sid)
        if sk and "kind" in sk and (sk["sp"] <= me["sp"]):
            options.append((sid, None))
    for k in bag:  # 魂石：固定伤害，不看属攻
        if fx(k).get("dmg"):
            options.append(("item", k))
    for sid, weapon in options:
        if sid == "item":
            it = items[weapon]
            sk = {"kind": "elem", "type": it["fx"].get("type"), "fixed": it["fx"]["dmg"], "power": 1.0,
                  "target": it["target"], "sp": 0, "price": it["price"]}
        elif sid == "attack":
            sk = {"kind": "phys", "type": weapon, "power": 1.0, "target": "enemy", "boost": "hits_attack"}
        else:
            sk = skills[sid]
        if sid in [k for k, v in skills.items() if v.get("job") == me["traveler"]] and not latent:
            continue  # 潜力专属技能只有潜力发动时能用
        boosts = [0] if (sk.get("divine") or sid == "item") else range(0, min(3, bp) + 1)
        for b in boosts:
            if sid == "attack":
                s2 = {**sk, "hits": 1 + b, "boost": None}
                pairs = [(f, est_damage(s2, me, f, 0, c)) for f in foes]
            else:
                pairs = [(f, est_damage(sk, me, f, b, c)) for f in foes]
            if sk["target"] in ("enemies", "random"):
                val = sum(score_target(d, s, f) for f, (d, s) in pairs)
                if sid == "item":  # 实测：分散的伤害不如集火，精灵石只看能不能击倒/击破
                    val -= 0.6 * sum(min(d, f["hp"]) for f, (d, s) in pairs)
                tgt = foes[0]["id"]
            else:
                f, (d, s) = max(pairs, key=lambda p: score_target(p[1][0], p[1][1], p[0]))
                val, tgt = score_target(d, s, f), f["id"]
            cost = sk.get("sp", 0) * 8 + b * 500 + (900 if sk.get("divine") else 0)  # 神技固定花 3 BP
            if sid == "item":
                cost = 150 + sk["price"] // 4  # 道具用一个少一个
            if any(f["broken"] for f in foes):
                cost -= b * 400        # 击破时加成很划算
            if me["bp"] >= 5:
                cost -= 400            # BP 满了别浪费
            v = val - cost
            if best is None or v > best[0]:
                best = (v, sid, tgt, b, weapon)
    sup = support(msg, usable, allies, foes, me)
    if sup and (best is None or sup[0] >= best[0] * 0.55):
        return sup[1]
    if best:
        _, sid, tgt, b, weapon = best
        act = {"skill": sid, "target": tgt, "boost": b, "latent": latent}
        if sid == "item":
            act["item"] = weapon
        elif weapon:
            act["weapon"] = weapon
    return act


def support(msg, usable, allies, foes, me):
    """辅助技能的粗略价值：(分数, 行动)，没有合适的返回 None。"""
    live = [a for a in allies if a["alive"]]
    strongest = max(foes, key=lambda f: max(f["stats"]["pa"], f["stats"]["ea"]))
    phys_foe = max(foes, key=lambda f: f["stats"]["pa"])
    has = lambda u, k: k in u.get("buffs", {}) or k in u.get("status", {})
    deb = lambda u, k: k in u.get("debuffs", {}) or k in u.get("status", {})
    hp = lambda u: u["hp"] / u["max_hp"]
    c = []
    if "abide" in usable and not has(me, "pa"):
        c.append((1300, {"skill": "abide"}))
    if "stout_wall" in usable and not has(me, "pd") and hp(me) < 0.8:
        c.append((1100, {"skill": "stout_wall"}))
    if "swift_step" in usable and not has(me, "spd"):
        c.append((900, {"skill": "swift_step"}))
    if "incite" in usable and not has(me, "taunt") and hp(me) > 0.6 and any(hp(a) < 0.5 for a in live if a is not me):
        c.append((1400, {"skill": "incite"}))
    if "vengeful_blade" in usable and not has(me, "counter"):
        c.append((1000, {"skill": "vengeful_blade"}))
    if "sidestep" in usable and not has(me, "sidestep") and hp(me) < 0.6:
        c.append((1000, {"skill": "sidestep"}))
    if "armor_corrosive" in usable:
        t = [f for f in foes if not deb(f, "pd")]
        if t:
            c.append((1500, {"skill": "armor_corrosive", "target": max(t, key=lambda f: f["hp"])["id"]}))
    if "shackle_foe" in usable and not deb(phys_foe, "pa"):
        c.append((1500, {"skill": "shackle_foe", "target": phys_foe["id"]}))
    if "leghold_trap" in usable:
        t = [f for f in foes if not deb(f, "leghold")]
        if t:
            c.append((1000, {"skill": "leghold_trap", "target": max(t, key=lambda f: f["stats"]["spd"])["id"]}))
    if "weak_to_poison" in usable:
        t = [f for f in foes if not deb(f, "poison_weak")]
        if t:
            c.append((900, {"skill": "weak_to_poison", "target": t[0]["id"]}))
    if "abating_orb" in usable:
        f = max(foes, key=lambda f: len(f.get("buffs", {})))
        if f.get("buffs"):
            c.append((700 * len(f["buffs"]), {"skill": "abating_orb", "target": f["id"]}))
    if "rehabilitate" in usable:
        t = [a for a in live if "poison" in a.get("status", {})]
        if t:
            c.append((1500, {"skill": "rehabilitate", "target": t[0]["id"]}))
    if "replenish_health" in usable:
        t = [a for a in live if not has(a, "regen") and hp(a) < 0.75]
        if t:
            c.append((1100, {"skill": "replenish_health", "target": min(t, key=hp)["id"]}))
    if "take_aim" in usable and not any(has(a, "crit") for a in live):
        c.append((1300, {"skill": "take_aim"}))
    if "prayer_to_the_flame" in usable:
        t = [a for a in live if not has(a, "pd")]
        if t:
            c.append((1200, {"skill": "prayer_to_the_flame", "target": min(t, key=hp)["id"]}))
    if "sacred_shield" in usable:
        t = [a for a in live if not has(a, "sacred")]
        if t:
            c.append((1200, {"skill": "sacred_shield", "target": min(t, key=hp)["id"]}))
    if not c:
        return None
    v, act = max(c, key=lambda x: x[0])
    act.setdefault("boost", 0)
    return v, act


SUB_PREF = {"hikari": ["Hunter", "Thief"], "agnea": ["Scholar", "Cleric"], "partitio": ["Warrior", "Hunter"],
            "osvald": ["Cleric", "Dancer"], "temenos": ["Scholar", "Dancer"], "throne": ["Hunter", "Warrior"],
            "ochette": ["Warrior", "Thief"], "castti": ["Cleric", "Warrior"]}
SUP_PREF = ["full_power", "rise_again", "boost_start", "hang_tough", "summon_strength", "elemental_augmentation",
            "fleetfoot", "hale_and_hearty", "salt_the_wound", "eagle_eye", "resilience", "inner_strength",
            "latent_power_plus", "the_show_goes_on", "bolstering_break", "inspiriting_break", "incidental_attack",
            "ensnare", "ever_evasive", "advanced_magic_master", "preventative_measures", "invigorate_and_inspire",
            "deal_more_damage"]


def make_loadout(picks):
    rules = info["loadout_rules"]
    jobs, costs, budget = rules["jobs"], rules["jp_costs"], rules["budget"]["jp"]
    used, out = {}, []
    for k in picks:
        own = info["travelers"][k]["job_en"]
        sub = next((j for j in SUB_PREF.get(k, []) + list(jobs)
                    if j != own and used.get(j, 0) < rules["licenses"]), None)
        used[sub] = used.get(sub, 0) + 1
        out.append({"sub_job": sub, "learn": [], "supports": []})
    # JP：轮流给每人多学一个（便宜的先学），直到预算不够
    spent, progress = 0, True
    while progress:
        progress = False
        for o in out:
            j = jobs[o["sub_job"]]
            cand = [s for s in j["skills"] if s not in j["free_skills"] and s not in o["learn"] and s != j["divine"]]
            n = len(o["learn"])
            if cand and n < len(costs) and spent + costs[n] <= budget:
                spent += costs[n]
                o["learn"].append(cand[0])
                progress = True
    for k, o in zip(picks, out):
        t = info["travelers"][k]
        avail = list(jobs[t["job_en"]]["supports"])
        known = rules["free_skills"] + len(o["learn"])
        avail += [s for s, need in zip(jobs[o["sub_job"]]["supports"], rules["support_unlock"]) if known >= need]
        phys = t["pa"] >= t["ea"]
        pref = [s for s in SUP_PREF if not (s == "summon_strength" and not phys)
                and not (s == "elemental_augmentation" and phys)]
        o["supports"] = [s for s in pref if s in avail and rules["supports"][s]["battle"]][:rules["support_slots"]]
    return out


# 实测：用道具回 HP、或复活后只有 500 HP，都不如直接输出，所以贪心只买大复活和精灵石，剩下的钱都买精灵石
ITEM_SHARE = [("revive", 0.5), ("dmg", 1.0)]


def make_items(picks):
    """按比例分金钱：每类挑效果最强的一种（用道具要占一次行动，所以看单次效果，不看性价比）。"""
    rules = info["loadout_rules"]
    items, gold = rules["items"], rules["budget"]["gold"]
    value = {"revive": lambda f: f.get("revive", 0) if f.get("revive", 0) >= 1500 else 0, "hp": lambda f: f.get("hp", 0),
             "sp": lambda f: f.get("sp", 0), "dmg": lambda f: f.get("dmg", 0)}
    bag, left = {}, gold
    for cat, share in ITEM_SHARE:
        cand = [k for k, v in items.items() if value[cat](v["fx"]) > 0 and v["target"] in ("ally", "ko", "enemies", "enemy")
                and not (cat == "hp" and v["fx"].get("revive")) and v["price"] <= min(gold * share, left)]
        if not cand:
            continue
        # 攻击道具：同样强时先挑己方技能打不出的属性，再挑 8 名旅人里弱点最多的（盲配时不知道对手是谁）
        have = {info["skills"][x].get("type") for p in picks for x in info["travelers"][p]["skills"]}
        weak = lambda k: sum(items[k]["fx"].get("type") in t["weak"] for t in info["travelers"].values())
        k = max(cand, key=lambda k: (value[cat](items[k]["fx"]), items[k]["fx"].get("type") not in have, weak(k),
                                     -items[k]["price"]))
        n = min(rules["item_stack"], int(min(gold * share, left) // items[k]["price"]))
        if n > 0:
            bag[k] = bag.get(k, 0) + n
            left -= n * items[k]["price"]
    return bag


n_alive = 4
for line in sys.stdin:
    msg = json.loads(line)
    if msg["type"] == "init":
        info = msg
        print(json.dumps({"ready": True}), flush=True)
    elif msg["type"] == "turn":
        reply = {"tick": msg["tick"]}
        if msg["your_turn"]:
            if msg["phase"] == "pick":
                reply["pick"] = [k for k in PICK if k in msg["available"]][:msg["pick_count"]]
            elif msg["phase"] == "loadout":
                reply["loadout"] = make_loadout(msg["my_picks"])
                reply["items"] = make_items(msg["my_picks"])
            else:
                try:
                    reply["action"] = decide(msg)
                except Exception as e:  # 出错就普通攻击，别让整局崩掉
                    print("decide error:", repr(e), file=sys.stderr)
                    foes = [u for u in msg["opponents"] if u["alive"]]
                    reply["action"] = {"skill": "attack", "target": foes[0]["id"] if foes else 0}
        print(json.dumps(reply), flush=True)
    elif msg["type"] == "end":
        break
