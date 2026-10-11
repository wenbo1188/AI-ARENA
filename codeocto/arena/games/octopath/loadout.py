"""赛前配置（loadout）：副职业、用 JP 学副职技能、支援技能、携带的战斗道具。

规则对应《八方旅人 II》的养成系统，数值来源：
- 副职属性加成（按基础属性的百分比）、副职武器、JP 价格（第 3～8 个技能 30/100/500/1000/3000/5000）、
  支援技能在学会 4/5/6/7 个技能时解锁、支援技能栏 4 格、每个基础职业 3 张执照：原作数据，
  出处 game8.jp、hyperwiki.jp、ot2.monogamer.net、游侠网（简体中文名）。
- 支援技能里原作没写具体数值的（标了 est 的），以及竞技场里的预算，是本竞技场的估计/设计值。
- 不带装备、不吃坚果（2026-10-07 mr.wang：降低复杂度，只比技能、配队和道具使用）。
- 只和地图探索有关的支援技能（遇敌率、金钱、经验等）在对战里没有意义，不能装备（battle=False）。

公平性：两队拿到同样的预算（JP、买道具的金钱），配置在选人后同时提交，看不到对方的配置，战斗开始时公开。
"""
from __future__ import annotations

from .data import JOB_SKILLS, SKILLS, TRAVELERS

JOB_ZH = {"Warrior": "剑士", "Merchant": "商人", "Thief": "盗贼", "Apothecary": "药师",
          "Hunter": "猎人", "Cleric": "神官", "Scholar": "学者", "Dancer": "舞娘"}

# 副职属性加成：基础属性 ×(1 + x/100)（原作数据，game8.jp 各职业页；商人 SP+8% 只有 game8.jp 一个来源）
JOB_BONUS = {
    "Warrior":    {"hp": 18, "pa": 5, "pd": 5},
    "Dancer":     {"ea": 8, "spd": 10, "eva": 10},
    "Merchant":   {"hp": 8, "sp": 8, "pa": 3, "pd": 3, "ea": 3, "ed": 3},
    "Scholar":    {"sp": 13, "ea": 10, "ed": 5},
    "Thief":      {"pa": 2, "acc": 5, "spd": 8, "crit": 5, "eva": 8},
    "Cleric":     {"sp": 18, "ea": 5, "ed": 5},
    "Hunter":     {"pa": 8, "acc": 6, "spd": 5, "crit": 6, "eva": 3},
    "Apothecary": {"hp": 20, "pa": 2, "pd": 2, "ea": 2, "crit": 2},
}
JOB_WEAPONS = {
    "Warrior": ["sword", "polearm"], "Dancer": ["dagger"], "Merchant": ["polearm", "bow"], "Scholar": ["staff"],
    "Thief": ["dagger", "sword"], "Cleric": ["staff"], "Hunter": ["bow", "axe"], "Apothecary": ["axe"],
}
LICENSES = 3            # 每个基础职业的执照数：一队最多 3 人用同一个副职（原作）
FREE_SKILLS = 2         # 副职一上来就会 2 个初始技能（原作），具体是哪两个见 INITIAL_SKILLS
JP_COSTS = [30, 100, 500, 1000, 3000, 5000]   # 第 3、4、…、8 个技能的价格（按学的顺序，不按哪个技能；原作）
SUPPORT_UNLOCK = [4, 5, 6, 7]                  # 会了几个技能时解锁第 1～4 个支援技能（原作）
SUPPORT_SLOTS = 4

# 支援技能。battle=False 的只影响地图探索，竞技场里不能装。est 标出原作没给数值、由本竞技场估计的部分。
SUPPORTS = {
    # 剑士
    "bolstering_break": {"job": "Warrior", "n": 1, "name": "Bolstering Break", "zh": "令敌人破防提升物攻",
                         "desc": "自己击破敌人时，自身物攻上升 2 回合"},
    "summon_strength": {"job": "Warrior", "n": 2, "name": "Summon Strength", "zh": "物攻+50", "desc": "物攻 +50"},
    "latent_power_plus": {"job": "Warrior", "n": 3, "name": "Latent Power Plus", "zh": "提升潜力上升量",
                          "desc": "潜力能量积累速度 ×1.2"},
    "deal_more_damage": {"job": "Warrior", "n": 4, "name": "Deal More Damage", "zh": "突破伤害界限",
                         "desc": "自己造成的伤害上限从 9999 提高到 99999"},
    # 舞娘
    "the_show_goes_on": {"job": "Dancer", "n": 1, "name": "The Show Goes On", "zh": "强化回合数增加",
                         "desc": "自己施加的属性上升多持续 1 回合"},
    "ever_evasive": {"job": "Dancer", "n": 2, "name": "Ever Evasive", "zh": "回避率上升",
                     "desc": "被物理攻击时的落空率 +20%（直接加在落空率上）", "arena_rule": "本届确定规则：自然落空率额外增加20个百分点；击破目标仍无自然闪避"},
    "hard_worker": {"job": "Dancer", "n": 3, "name": "Hard Worker", "zh": "获得JP上升", "battle": False,
                    "desc": "战斗后获得的 JP ×1.1（探索用，竞技场无效）"},
    "invigorate_and_inspire": {"job": "Dancer", "n": 4, "name": "Invigorate and Inspire", "zh": "暖场高手",
                               "desc": "自己施加属性上升时，获得增益的角色潜力能量 +5/10/15/20（按这次行动花的 BP 0/1/2/3）"},
    # 商人
    "grows_on_trees": {"job": "Merchant", "n": 1, "name": "Grows on Trees", "zh": "获取金额上升", "battle": False,
                       "desc": "战斗后获得的金钱 ×1.1（探索用，竞技场无效）"},
    "boost_start": {"job": "Merchant", "n": 2, "name": "Boost-Start", "zh": "BP加成", "desc": "开战时 BP +1"},
    "hang_tough": {"job": "Merchant", "n": 3, "name": "Hang Tough", "zh": "坚持到底",
                   "desc": "受到致命的一击时，如果这一击之前 HP 在 25% 以上，剩 1 HP 撑住（多段攻击每一击单独判断）"},
    "full_power": {"job": "Merchant", "n": 4, "name": "Full Power", "zh": "潜力爆发MAX", "desc": "开战时潜力能量全满"},
    # 学者
    "evasive_maneuvers": {"job": "Scholar", "n": 1, "name": "Evasive Maneuvers", "zh": "遇敌概率减半", "battle": False,
                          "desc": "遇敌率减半（探索用，竞技场无效）"},
    "elemental_augmentation": {"job": "Scholar", "n": 2, "name": "Elemental Augmentation", "zh": "属攻+50",
                               "desc": "属攻 +50"},
    "extra_experience": {"job": "Scholar", "n": 3, "name": "Extra Experience", "zh": "获得EXP提升", "battle": False,
                         "desc": "战斗后获得的经验 ×1.1（探索用，竞技场无效）"},
    "advanced_magic_master": {"job": "Scholar", "n": 4, "name": "Advanced Magic Master", "zh": "魔法强化加成",
                              "desc": "自己施放大魔法化 / 硕学王的知识时，强化次数 +1"},
    # 盗贼
    "incidental_attack": {"job": "Thief", "n": 1, "name": "Incidental Attack", "zh": "顺便战斗",
                          "desc": "使用不造成伤害的技能后，50% 概率再普通攻击 1 次"},
    "fleetfoot": {"job": "Thief", "n": 2, "name": "Fleetfoot", "zh": "行动速度+50", "desc": "速度 +50"},
    "ensnare": {"job": "Thief", "n": 3, "name": "Ensnare", "zh": "陷阱",
                "desc": "受到物理伤害时，50% 概率让攻击者随机一项属性下降 2 回合", "arena_rule": "本届确定规则：减益持续2回合"},
    "life_in_the_shadows": {"job": "Thief", "n": 4, "name": "Life in the Shadows", "zh": "存于黑暗", "battle": False,
                            "desc": "夜晚战斗后经验和 JP ×1.5（探索用，竞技场无效）"},
    # 神官
    "resilience": {"job": "Cleric", "n": 1, "name": "Resilience", "zh": "HP恢复量上升",
                   "desc": "自己技能的 HP 恢复量 ×1.3"},
    "inner_strength": {"job": "Cleric", "n": 2, "name": "Inner Strength", "zh": "最大SP+50", "desc": "最大 SP +50"},
    "evil_ward": {"job": "Cleric", "n": 3, "name": "Evil Ward", "zh": "逃跑成功率上升", "battle": False,
                  "desc": "逃跑成功率上升（竞技场无效）"},
    "rise_again": {"job": "Cleric", "n": 4, "name": "Rise Again", "zh": "自动复活",
                   "desc": "每场一次，倒下时立刻以 25% HP 复活"},
    # 猎人
    "heighten_senses": {"job": "Hunter", "n": 1, "name": "Heighten Senses", "zh": "先制攻击的概率上升", "battle": False,
                        "desc": "先制攻击概率上升（探索用，竞技场无效）"},
    "eagle_eye": {"job": "Hunter", "n": 2, "name": "Eagle Eye", "zh": "暴击+50", "desc": "暴击 +50"},
    "more_rare_monsters": {"job": "Hunter", "n": 3, "name": "More Rare Monsters", "zh": "稀有怪物遭遇率上升",
                           "battle": False, "desc": "稀有怪遭遇率上升（探索用，竞技场无效）"},
    "salt_the_wound": {"job": "Hunter", "n": 4, "name": "Salt the Wound", "zh": "破防追击",
                       "desc": "自己击破敌人时，50% 概率立刻再行动一次（不会连续触发）"},
    # 药师
    "vigorous_victor": {"job": "Apothecary", "n": 1, "name": "Vigorous Victor", "zh": "战斗后恢复", "battle": False,
                        "desc": "战斗胜利后恢复 30% HP/SP（竞技场无效）"},
    "hale_and_hearty": {"job": "Apothecary", "n": 2, "name": "Hale and Hearty", "zh": "最大HP+500", "desc": "最大 HP +500"},
    "inspiriting_break": {"job": "Apothecary", "n": 3, "name": "Inspiriting Break", "zh": "令敌人破防恢复SP",
                          "desc": "自己击破敌人时，恢复固定 20 SP"},
    "preventative_measures": {"job": "Apothecary", "n": 4, "name": "Preventative Measures", "zh": "预防药",
                              "desc": "开战时获得 3 次属性下降无效（每挡掉一次减 1；按次数算，日文资料和玩家实测一致）"},
}
SUPPORT_FLAT = {"summon_strength": ("pa", 50), "elemental_augmentation": ("ea", 50), "fleetfoot": ("spd", 50),
                "eagle_eye": ("crit", 50), "inner_strength": ("sp", 50), "hale_and_hearty": ("hp", 500)}


# 原作每个职业 8 个技能。偷窃、收集金钱、雇佣帮手、分析在对战里没有意义，竞技场里没有效果，
# 但仍占技能格：学它们要花 JP，也计入"会几个技能"（解锁支援技能、学神技的条件），和原作一致。
NONBATTLE_SKILLS = {
    "steal":     {"job": "Thief",    "name": "Steal",     "zh": "偷窃"},
    "collect":   {"job": "Merchant", "name": "Collect",   "zh": "收集金钱"},
    "hire_help": {"job": "Merchant", "name": "Hire Help", "zh": "雇佣帮手"},
    "analyze":   {"job": "Scholar",  "name": "Analyze",   "zh": "分析"},
}
# 各职业的 2 个初始技能（原作，各职业攻略的默认技能；中文名未逐个对照 PS5 简中界面）
INITIAL_SKILLS = {
    "Warrior": ["aggressive_slash", "piercing_thrust"], "Dancer": ["lion_dance", "ruinous_kick"],
    "Merchant": ["arrow_of_fortune", "rest"], "Thief": ["steal", "darkest_night"],
    "Hunter": ["precise_shot", "thunderbird"], "Apothecary": ["healing_touch", "icicle"],
    "Cleric": ["heal_wounds", "holy_light"], "Scholar": ["fireball", "icewind"],
}


def job_grid(job: str) -> list[str]:
    """职业的全部 8 个技能（含竞技场里没有效果的）。"""
    return JOB_SKILLS[job] + [k for k, v in NONBATTLE_SKILLS.items() if v["job"] == job]


def job_divine(job: str) -> str:
    return next(s for s in JOB_SKILLS[job] if SKILLS[s].get("divine"))


def job_supports(job: str) -> list[str]:
    return sorted((k for k, v in SUPPORTS.items() if v["job"] == job), key=lambda k: SUPPORTS[k]["n"])


def free_skills(job: str) -> list[str]:
    return list(INITIAL_SKILLS[job])


# ---------------- 战斗道具 ----------------
# 赛前用金钱买，全队共用一个道具袋；战斗中任何队员都可以用"item"行动使用（占一次行动）。数据待补。
# 战斗道具（原作数据：ot2.monogamer.net、game8.jp、hyperwiki.jp；中文名取自游侠网/gametoeasy，未对照 PS5 简中界面）
# fx：hp 固定回复 HP，sp 固定回复 SP，revive 复活并回复的 HP，cure 治疗中毒，bp 增加 BP，dmg 固定伤害（type 属性）
# target：ally 单个己方，allies 全体己方，ko 倒下的己方，enemy 单个敌人，enemies 全体敌人
ITEMS: dict = {
    "healing_grape": {"name": "Healing Grape", "zh": "恢复HP的葡萄", "price": 50, "target": "ally", "fx": {"hp": 500},
                      "desc": "恢复 HP 500"},
    "healing_grape_m": {"name": "Healing Grape (M)", "zh": "恢复HP的葡萄(大)", "price": 260, "target": "ally",
                        "fx": {"hp": 1250}, "desc": "恢复 HP 1250"},
    "healing_grape_bunch": {"name": "Healing Grape Bunch", "zh": "恢复全体HP的葡萄", "price": 720, "target": "allies",
                            "fx": {"hp": 900}, "desc": "全体恢复 HP 900", "src": "内部价值"},
    "inspiriting_plum": {"name": "Inspiriting Plum", "zh": "恢复SP的李子", "price": 240, "target": "ally",
                         "fx": {"sp": 40}, "desc": "恢复 SP 40"},
    "inspiriting_plum_m": {"name": "Inspiriting Plum (M)", "zh": "恢复SP的李子(大)", "price": 900, "target": "ally",
                           "fx": {"sp": 100}, "desc": "恢复 SP 100"},
    "energizing_pomegranate": {"name": "Energizing Pomegranate", "zh": "恢复BP的石榴", "price": 300, "target": "ally",
                               "fx": {"bp": 1}, "desc": "BP +1", "src": "内部价值"},
    "olive_of_life": {"name": "Olive of Life", "zh": "复活的橄榄", "price": 500, "target": "ko",
                      "fx": {"revive": 500}, "desc": "复活倒下的队友，HP 500"},
    "olive_of_life_m": {"name": "Olive of Life (M)", "zh": "复活的橄榄(大)", "price": 3000, "target": "ko",
                        "fx": {"revive": 2000}, "desc": "复活倒下的队友，HP 2000"},
    "herb_of_serenity": {"name": "Herb of Serenity", "zh": "包治百病的药草", "price": 600, "target": "ally",
                         "fx": {"cure": True}, "desc": "治疗中毒（原作是治疗全部异常状态，本竞技场只有中毒和弱毒）"},
}
_EL = {"fire": ("Fire", "火"), "ice": ("Ice", "冰"), "lightning": ("Thunder", "雷"), "wind": ("Wind", "风"),
       "light": ("Light", "光"), "dark": ("Shadow", "暗")}
for _t, (_en, _zh) in _EL.items():
    ITEMS[f"{_t}_soulstone"] = {"name": f"{_en} Soulstone", "zh": f"{_zh}之精灵石", "price": 700, "target": "enemies",
                                "fx": {"dmg": 200, "type": _t}, "desc": f"全体敌人受到 200 点{_zh}属性固定伤害"}
    ITEMS[f"{_t}_soulstone_m"] = {"name": f"{_en} Soulstone (M)", "zh": f"{_zh}之精灵石(大)", "price": 1700,
                                  "target": "enemies", "fx": {"dmg": 1100, "type": _t},
                                  "desc": f"全体敌人受到 1100 点{_zh}属性固定伤害"}
ITEMS_NOTE = ("效果和价格为原作数据；价格是原作商店的售价（精灵石只在新德尔斯塔平原的黑市卖），标 *内部价值* 的原作商店不卖，"
              "用原作数据表里的道具价值代替。原作资料没写、本竞技场自己定的："
              "道具不能加成；精灵石的固定伤害不乘弱点、击破、防御倍率（圣盾照样减伤），但打中弱点会削 1 护盾；"
              "药师的「HP恢复量上升」等支援技能不影响道具。")
ITEM_STACK = 99            # 每种道具最多带几个（原作上限）

BUDGET = {
    "jp": 12000,      # 全队共用的 JP，用来学副职技能
    "gold": 6000,     # 全队共用的金钱（叶），赛前买战斗道具
}


def empty() -> dict:
    return {"sub_job": None, "learn": [], "supports": []}


def info() -> dict:
    """开局消息里给机器人的配置规则和数据。"""
    jobs = {}
    for j in JOB_ZH:
        jobs[j] = {"zh": JOB_ZH[j], "bonus_pct": JOB_BONUS[j], "weapons": JOB_WEAPONS[j],
                   "skills": job_grid(j), "free_skills": free_skills(j), "divine": job_divine(j),
                   "nonbattle_skills": [k for k in job_grid(j) if k in NONBATTLE_SKILLS],
                   "supports": job_supports(j)}
    return {
        "budget": dict(BUDGET),
        "jp_costs": JP_COSTS, "free_skills": FREE_SKILLS, "support_unlock": SUPPORT_UNLOCK,
        "support_slots": SUPPORT_SLOTS, "licenses": LICENSES,
        "jobs": jobs,
        "supports": {k: {kk: vv for kk, vv in v.items()} | {"battle": v.get("battle", True)} for k, v in SUPPORTS.items()},
        "nonbattle_skills": NONBATTLE_SKILLS,
        "items": ITEMS, "item_stack": ITEM_STACK,
    }


def jp_cost(n_paid: int) -> int:
    return sum(JP_COSTS[:n_paid])


def _member_msgs(msg, n: int) -> list:
    if isinstance(msg, list):
        return [msg[i] if i < len(msg) and isinstance(msg[i], dict) else {} for i in range(n)]
    if isinstance(msg, dict):
        return [msg.get(str(i), msg.get(i)) if isinstance(msg.get(str(i), msg.get(i)), dict) else {} for i in range(n)]
    return [{} for _ in range(n)]


def validate(keys: list[str], msg) -> tuple[list[dict], list[str]]:
    """把一队的配置请求规范化。返回 (每人一份配置, 被忽略的内容说明)。
    规则：单个条目不合法只忽略那一条；某项全队总花费超预算，则全队这一项作废。"""
    notes: list[str] = []
    reqs = _member_msgs(msg, len(keys))
    out = [empty() for _ in keys]
    used_jobs: dict[str, int] = {}
    # 1. 副职
    for i, (k, r) in enumerate(zip(keys, reqs)):
        j = r.get("sub_job")
        if j is None:
            continue
        if not isinstance(j, str) or j not in JOB_ZH:
            notes.append(f"{i}: 未知副职 {j!r}")
            continue
        if j == TRAVELERS[k]["job_en"]:
            notes.append(f"{i}: 副职不能和本职相同")
            continue
        if used_jobs.get(j, 0) >= LICENSES:
            notes.append(f"{i}: 副职 {j} 的执照已用完（每队最多 {LICENSES} 人）")
            continue
        used_jobs[j] = used_jobs.get(j, 0) + 1
        out[i]["sub_job"] = j
    # 2. JP 学副职技能
    total = 0
    for i, r in enumerate(reqs):
        j = out[i]["sub_job"]
        learn = r.get("learn") or []
        if not j or not isinstance(learn, list):
            continue
        free, grid, divine = free_skills(j), job_grid(j), job_divine(j)
        got = []
        for s in learn:
            if s in grid and s not in free and s not in got and s != divine:
                got.append(s)
            elif s != divine:
                notes.append(f"{i}: 不能学 {s!r}")
        if divine in learn:
            if len(got) == len(grid) - FREE_SKILLS - 1:
                got.append(divine)
            else:
                notes.append(f"{i}: 学神技要先学会其他全部技能")
        out[i]["learn"] = got
        total += jp_cost(len(got))
    if total > BUDGET["jp"]:
        notes.append(f"JP 总花费 {total} 超过预算 {BUDGET['jp']}，全队不学副职技能")
        for o in out:
            o["learn"] = []
    # 3. 支援技能
    for i, (k, r) in enumerate(zip(keys, reqs)):
        avail = set(job_supports(TRAVELERS[k]["job_en"]))  # 本职已精通，4 个支援技能都会
        j = out[i]["sub_job"]
        if j:
            known = FREE_SKILLS + len(out[i]["learn"])
            sups = job_supports(j)
            avail |= {sups[n] for n, need in enumerate(SUPPORT_UNLOCK) if known >= need}
        got = []
        for s in (r.get("supports") or []) if isinstance(r.get("supports"), list) else []:
            if s in got:
                continue
            if s not in SUPPORTS or s not in avail:
                notes.append(f"{i}: 支援技能 {s!r} 未解锁或不存在")
            elif not SUPPORTS[s].get("battle", True):
                notes.append(f"{i}: 支援技能 {s!r} 在对战里无效，不能装备")
            elif len(got) >= SUPPORT_SLOTS:
                notes.append(f"{i}: 支援技能最多 {SUPPORT_SLOTS} 个")
            else:
                got.append(s)
        out[i]["supports"] = got
    return out, notes


def validate_items(msg) -> tuple[dict, list[str]]:
    """全队的道具袋 {道具 id: 个数}。单条不合法忽略；总价超预算则一个都不带。"""
    notes: list[str] = []
    bag: dict[str, int] = {}
    if msg is None:
        return bag, notes
    if not isinstance(msg, dict):
        return bag, ["items 应该是 {道具 id: 个数}"]
    gold = 0
    for k, n in msg.items():
        if k not in ITEMS or not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= ITEM_STACK:
            notes.append(f"道具 {k!r}×{n!r} 不合法（每种最多 {ITEM_STACK} 个）")
            continue
        if n:
            bag[k] = n
            gold += ITEMS[k]["price"] * n
    if gold > BUDGET["gold"]:
        notes.append(f"道具总价 {gold} 超过预算 {BUDGET['gold']}，一个道具都不带")
        bag = {}
    return bag, notes


def bag_cost(bag: dict) -> int:
    return sum(ITEMS[k]["price"] * n for k, n in bag.items())


def apply_stats(key: str, lo: dict) -> dict:
    """基础属性 → 计入副职百分比（只乘角色基础属性）和支援技能固定加值之后的属性（含 hp/sp）。"""
    t = TRAVELERS[key]
    stats = {s: t[s] for s in ("hp", "sp", "pa", "pd", "ea", "ed", "acc", "eva", "crit", "spd")}
    j = lo.get("sub_job")
    if j:
        for s, pct in JOB_BONUS[j].items():
            stats[s] = int(t[s] * (1 + pct / 100))
    for sid in lo.get("supports") or []:
        if sid in SUPPORT_FLAT:
            s, v = SUPPORT_FLAT[sid]
            stats[s] += v
    return stats
