"""八方旅人 II 角色与技能数据。

技能参数使用随包 verified_values.json；伤害公式与已核对数值见参赛接口文档。
护盾、弱点和部分对战适配为赛事设置。历史字段名 ESTIMATED 为兼容代码保留。
"""

ARENA_HP_BONUS = 1000

WEAPONS = ["sword", "polearm", "dagger", "axe", "bow", "staff"]
ELEMENTS = ["fire", "ice", "lightning", "wind", "light", "dark"]
TYPES = WEAPONS + ELEMENTS

TYPE_ZH = {
    "sword": "剑", "polearm": "枪", "dagger": "短剑", "axe": "斧", "bow": "弓", "staff": "杖",
    "fire": "火", "ice": "冰", "lightning": "雷", "wind": "风", "light": "光", "dark": "暗",
}

# 99 级基础属性（真实数据）。shields / weak 为原创设计（旅人在原作中不会成为敌人，没有护盾和弱点）。
TRAVELERS = {
    "hikari":   {"name": "光", "name_en": "Hikari",   "job": "剑士", "job_en": "Warrior",
                 "hp": 5781, "sp": 145, "pa": 342, "pd": 313, "ea": 256, "ed": 228,
                 "acc": 313, "eva": 228, "crit": 285, "spd": 285,
                 "weapons": ["sword", "polearm"], "shields": 7, "weak": ["axe", "bow", "ice", "wind"]},
    "agnea":    {"name": "爱格妮娅", "name_en": "Agnea",    "job": "舞娘", "job_en": "Dancer",
                 "hp": 4002, "sp": 182, "pa": 285, "pd": 199, "ea": 342, "ed": 228,
                 "acc": 285, "eva": 313, "crit": 285, "spd": 370,
                 "weapons": ["dagger"], "shields": 5, "weak": ["sword", "polearm", "lightning", "dark"]},
    "partitio": {"name": "帕特提欧", "name_en": "Partitio", "job": "商人", "job_en": "Merchant",
                 "hp": 4891, "sp": 182, "pa": 313, "pd": 285, "ea": 313, "ed": 285,
                 "acc": 285, "eva": 256, "crit": 256, "spd": 256,
                 "weapons": ["polearm", "bow"], "shields": 6, "weak": ["dagger", "axe", "wind", "dark"]},
    "osvald":   {"name": "奥兹巴尔多", "name_en": "Osvald",   "job": "学者", "job_en": "Scholar",
                 "hp": 3557, "sp": 218, "pa": 256, "pd": 256, "ea": 370, "ed": 342,
                 "acc": 285, "eva": 285, "crit": 228, "spd": 256,
                 "weapons": ["staff"], "shields": 5, "weak": ["sword", "dagger", "fire", "lightning"]},
    "temenos":  {"name": "提米诺斯", "name_en": "Temenos",  "job": "神官", "job_en": "Cleric",
                 "hp": 4002, "sp": 236, "pa": 285, "pd": 285, "ea": 342, "ed": 370,
                 "acc": 285, "eva": 228, "crit": 199, "spd": 228,
                 "weapons": ["staff"], "shields": 6, "weak": ["polearm", "wind", "ice", "dark"]},
    "throne":   {"name": "斯洛妮", "name_en": "Throné",   "job": "盗贼", "job_en": "Thief",
                 "hp": 4447, "sp": 145, "pa": 313, "pd": 228, "ea": 285, "ed": 228,
                 "acc": 313, "eva": 342, "crit": 285, "spd": 342,
                 "weapons": ["dagger", "sword"], "shields": 5, "weak": ["staff", "bow", "fire", "light"]},
    "ochette":  {"name": "欧修缇", "name_en": "Ochette",  "job": "猎人", "job_en": "Hunter",
                 "hp": 4447, "sp": 145, "pa": 342, "pd": 228, "ea": 285, "ed": 228,
                 "acc": 342, "eva": 313, "crit": 313, "spd": 285,
                 "weapons": ["bow", "axe"], "shields": 6, "weak": ["sword", "staff", "fire", "ice"]},
    "castti":   {"name": "卡斯蒂", "name_en": "Castti",   "job": "药师", "job_en": "Apothecary",
                 "hp": 5336, "sp": 182, "pa": 313, "pd": 285, "ea": 285, "ed": 285,
                 "acc": 285, "eva": 256, "crit": 285, "spd": 228,
                 "weapons": ["axe"], "shields": 6, "weak": ["polearm", "staff", "lightning", "light"]},
}

LATENT = {
    "hikari":   ("阴之力", "释放体内的暗影之力，本次行动可以使用天裂斩、飞燕华、双月闪"),
    "agnea":    ("齐心协力", "本次行动的单体技能/攻击改为作用于全体"),
    "partitio": ("气势", "BP 立刻补满（5），然后正常行动"),
    "osvald":   ("魔法集合化", "本次的全体攻击魔法集中打一个敌人，伤害 ×2"),
    "temenos":  ("审判", "本次行动的每一击都削减护盾，无视弱点"),
    "throne":   ("残影", "本回合连续行动两次"),
    "ochette":  ("兽之力", "释放野性，本次行动可以使用兽之爪、兽之牙、兽之咆哮"),
    "castti":   ("节约", "本次调合不消耗材料，且按最大加成（BP 3）的效果生效（不花 BP）"),
}

# 技能表。
#  target: enemy 单个敌人 / enemies 全体敌人 / random 随机敌人多次 / chosen 自选目标多次 / ally 单个队友(含自己) / ally_other 其他队友
#          ally_any 单个队友（可以是倒下的）/ allies 全体队友 / self 自己
#  kind: phys 物理（用物攻对物防，可能闪避/暴击）/ elem 属性（用属攻对属防，必中）
#  boost: power 威力×(1+BP) / hits 次数按档位 / crit 暴击率按档位 / dur 持续回合按档位 / count 次数按档位 / none
#  spell: 受"高级魔法 / 阿雷法的智慧"影响的魔法
#  divine: 神技（30 SP，原作规则只能以最大加成发动：必须有 3 BP 并全部消耗；威力已按最大加成设计）
# 下方保留基础定义，文件末尾用核对参数覆盖伤害与消耗。
SKILLS = {
    # ---------------- 剑士 Warrior（Hikari）----------------
    "aggressive_slash": {"job": "Warrior", "name": "Aggressive Slash", "zh": "五月雨斩", "sp": 9, "target": "random",
                          "kind": "phys", "type": "sword", "power": 0.9, "boost": "hits", "levels": [3, 4, 5, 6],
                          "desc": "剑，随机攻击敌人 3/4/5/6 次"},
    "piercing_thrust": {"job": "Warrior", "name": "Piercing Thrust", "zh": "会心之枪", "sp": 12, "target": "enemy",
                        "kind": "phys", "type": "polearm", "power": 2.6, "boost": "crit", "levels": [25, 50, 75, 100],
                        "desc": "枪，单体强力攻击，暴击率 25/50/75/100%"},
    "abide": {"job": "Warrior", "name": "Abide", "zh": "蓄力", "sp": 4, "target": "self",
              "boost": "dur", "levels": [3, 5, 7, 9], "desc": "自身物攻上升 3/5/7/9 回合"},
    "enervating_slash": {"job": "Warrior", "name": "Enervating Slash", "zh": "无心长刀", "sp": 7, "target": "enemy",
                         "kind": "phys", "type": "sword", "power": 1.4, "boost": "power",
                         "desc": "先清除单个敌人的全部增益，再用剑攻击"},
    "stout_wall": {"job": "Warrior", "name": "Stout Wall", "zh": "铁壁", "sp": 4, "target": "self",
                   "boost": "dur", "levels": [3, 5, 7, 9], "desc": "自身物防上升 3/5/7/9 回合"},
    "incite": {"job": "Warrior", "name": "Incite", "zh": "挑衅", "sp": 4, "target": "self",
               "boost": "dur", "levels": [3, 5, 7, 9], "desc": "敌人的单体攻击全部打向自己，3 回合（加成延长）"},
    "vengeful_blade": {"job": "Warrior", "name": "Vengeful Blade", "zh": "反击长刀", "sp": 6, "target": "self",
                       "boost": "count", "levels": [2, 3, 4, 5], "desc": "受到物理攻击时用剑反击，2/3/4/5 次"},
    "brands_blade": {"job": "Warrior", "name": "Brand's Blade", "zh": "雷剑将布兰德的刚剑", "sp": 30, "target": "enemy",
                     "kind": "phys", "type": "sword", "power": 5.0, "divine": True,
                     "desc": "神技：剑，单体极强攻击"},

    # ---------------- 商人 Merchant（Partitio）----------------
    "arrow_of_fortune": {"job": "Merchant", "name": "Arrow of Fortune", "zh": "幸运之箭", "sp": 12, "target": "enemy",
                         "kind": "phys", "type": "bow", "power": 2.4, "boost": "power", "desc": "弓，单体强力攻击"},
    "rest": {"job": "Merchant", "name": "Rest", "zh": "稍作休息", "sp": 0, "target": "self", "boost": "power",
             "desc": "恢复自己最大 HP 10%×(1+BP)、最大 SP 8%×(1+BP)，并解除中毒"},
    "ember": {"job": "Merchant", "name": "Ember", "zh": "火花", "sp": 7, "target": "enemy", "kind": "elem",
              "type": "fire", "power": 1.6, "boost": "power", "spell": True, "desc": "火，单体"},
    "donate_bp": {"job": "Merchant", "name": "Donate BP", "zh": "BP传递", "sp": 6, "target": "ally_other",
                  "boost": "count", "levels": [1, 2, 3, 4], "desc": "给一名其他队友 1/2/3/4 BP"},
    "sidestep": {"job": "Merchant", "name": "Sidestep", "zh": "紧急回避", "sp": 10, "target": "self",
                 "boost": "count", "levels": [1, 2, 3, 4], "desc": "必定闪避接下来 1/2/3/4 次物理攻击"},
    "bifelgans_bounty": {"job": "Merchant", "name": "Bifelgan's Bounty", "zh": "绅商伯比菲尔根的心眼", "sp": 30,
                         "target": "enemy", "kind": "phys", "type": None, "power": 5.0, "divine": True,
                         "desc": "神技：无属性单体极强攻击（不削护盾）"},

    # ---------------- 盗贼 Thief（Throné）----------------
    "darkest_night": {"job": "Thief", "name": "Darkest Night", "zh": "暗夜", "sp": 7, "target": "enemy", "kind": "elem",
                      "type": "dark", "power": 1.6, "boost": "power", "spell": True, "desc": "暗，单体"},
    "hp_thief": {"job": "Thief", "name": "HP Thief", "zh": "吸血匕首", "sp": 6, "target": "enemy", "kind": "phys",
                 "type": "dagger", "power": 0.9, "hits": 2, "boost": "power", "desc": "短剑，单体 2 次，吸取伤害一半的 HP"},
    "surprise_attack": {"job": "Thief", "name": "Surprise Attack", "zh": "突然袭击", "sp": 12, "target": "enemy",
                        "kind": "phys", "type": "sword", "power": 2.6, "boost": "power",
                        "desc": "剑，单体；顺位倍率为 2 - min(a / max(1, n - 1), 1)，a 为本回合此前已完成的行动次数，n 为回合开始时行动队列人数；首次行动 2 倍，最低 1 倍"},
    "swift_step": {"job": "Thief", "name": "Swift Step", "zh": "瞬间移动", "sp": 4, "target": "self",
                   "boost": "dur", "levels": [3, 5, 7, 9], "desc": "自身速度上升 3 回合（加成延长）"},
    "armor_corrosive": {"job": "Thief", "name": "Armor Corrosive", "zh": "猫头鹰", "sp": 4, "target": "enemy",
                        "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个敌人物防下降 2/4/6/8 回合"},
    "shackle_foe": {"job": "Thief", "name": "Shackle Foe", "zh": "蝙蝠", "sp": 4, "target": "enemy",
                    "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个敌人物攻下降 2/4/6/8 回合"},
    "aebers_reckoning": {"job": "Thief", "name": "Aeber's Reckoning", "zh": "盗公子埃伯尔的钩爪", "sp": 30, "target": "enemies",
                         "kind": "phys", "type": "dagger", "power": 1.8, "divine": True, "use_spd": True,
                         "desc": "神技：短剑，全体攻击，伤害按速度计算"},

    # ---------------- 药师 Apothecary（Castti）----------------
    "healing_touch": {"job": "Apothecary", "name": "Healing Touch", "zh": "治疗术", "sp": 6, "target": "ally_any",
                      "heal": 2.2, "boost": "power", "desc": "单个队友恢复 HP，可复活倒下的队友"},
    "icicle": {"job": "Apothecary", "name": "Icicle", "zh": "冰柱", "sp": 7, "target": "enemy", "kind": "elem",
               "type": "ice", "power": 1.6, "boost": "power", "spell": True, "desc": "冰，单体"},
    "rehabilitate": {"job": "Apothecary", "name": "Rehabilitate", "zh": "健全化", "sp": 10, "target": "ally",
                     "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个队友免疫异常状态（中毒）2/4/6/8 回合，并解毒"},
    "sweeping_cleave": {"job": "Apothecary", "name": "Sweeping Cleave", "zh": "斧一闪", "sp": 9, "target": "enemies",
                        "kind": "phys", "type": "axe", "power": 1.0, "boost": "power", "desc": "斧，全体"},
    "poison_axe": {"job": "Apothecary", "name": "Poison Axe", "zh": "毒断击", "sp": 12, "target": "enemy", "kind": "phys",
                   "type": "axe", "power": 2.0, "boost": "power", "desc": "斧，单体强力攻击，并使其中毒 2 回合"},
    "replenish_health": {"job": "Apothecary", "name": "Replenish Health", "zh": "继续疗伤", "sp": 9, "target": "ally",
                         "boost": "dur", "levels": [3, 5, 7, 9], "desc": "单个队友每次行动后恢复最大 HP 的 20%，3/5/7/9 回合"},
    "weak_to_poison": {"job": "Apothecary", "name": "Weak to Poison", "zh": "施加中毒弱点", "sp": 4, "target": "enemy",
                       "boost": "dur", "levels": [2, 4, 6, 8],
                       "desc": "单个敌人 2/4/6/8 回合内弱毒：中毒结算伤害时削 1 护盾"},
    "dohters_charity": {"job": "Apothecary", "name": "Dohter's Charity", "zh": "灵药公德塔的恩惠", "sp": 30, "target": "ally",
                        "divine": True, "desc": "神技：3 回合内，该队友的单体恢复技能和调合作用于全体队友"},

    # ---------------- 猎人 Hunter（Ochette）----------------
    "precise_shot": {"job": "Hunter", "name": "Precise Shot", "zh": "狙击", "sp": 6, "target": "chosen",
                     "kind": "phys", "type": "bow", "power": 0.8, "boost": "hits", "levels": [2, 3, 4, 5],
                     "desc": "弓，攻击 2/3/4/5 次，每次的目标由你指定（targets 列表，不足的重复最后一个）"},
    "thunderbird": {"job": "Hunter", "name": "Thunderbird", "zh": "雷鸟", "sp": 7, "target": "enemy", "kind": "elem",
                    "type": "lightning", "power": 1.9, "boost": "power", "spell": True, "desc": "雷，单体较强攻击"},
    "cleaving_blow": {"job": "Hunter", "name": "Cleaving Blow", "zh": "瓦解", "sp": 12, "target": "enemy", "kind": "phys",
                      "type": "axe", "power": 2.0, "boost": "power",
                      "desc": "斧，单体强力攻击；自身物攻上升 3 回合，并按对手类型获得物防（物攻≥属攻）或属防上升"},
    "mercy_strike": {"job": "Hunter", "name": "Mercy Strike", "zh": "点到为止", "sp": 4, "target": "enemy",
                     "kind": "phys", "type": "bow", "power": 1.0, "boost": "power", "mercy": True,
                     "desc": "弓，单体；不会击倒对手（至少留 1 HP）"},
    "take_aim": {"job": "Hunter", "name": "Take Aim", "zh": "瞄准目标", "sp": 8, "target": "allies",
                 "boost": "dur", "levels": [2, 4, 6, 8], "desc": "全体队友暴击率和命中上升 2/4/6/8 回合"},
    "leghold_trap": {"job": "Hunter", "name": "Leghold Trap", "zh": "黏着捕网", "sp": 10, "target": "enemy",
                     "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个敌人 2/4/6/8 回合内总在回合最后行动"},
    "abating_orb": {"job": "Hunter", "name": "Abating Orb", "zh": "化解弹", "sp": 9, "target": "enemy",
                    "boost": "count", "levels": [1, 2, 3, 4], "desc": "清除单个敌人 1/2/3/4 个增益效果"},
    "draefendis_bow": {"job": "Hunter", "name": "Draefendi's Bow", "zh": "狩猎女王德雷芳朵的猛追", "sp": 30, "target": "enemies",
                       "kind": "phys", "type": "bow", "power": 0.85, "hits": 3, "divine": True,
                       "desc": "神技：弓，全体攻击 3 次"},

    # ---------------- 神官 Cleric（Temenos）----------------
    "heal_wounds": {"job": "Cleric", "name": "Heal Wounds", "zh": "恢复魔法", "sp": 15, "target": "allies", "heal": 1.4,
                    "boost": "power", "spell": True, "desc": "全体队友恢复 HP"},
    "holy_light": {"job": "Cleric", "name": "Holy Light", "zh": "圣光", "sp": 6, "target": "enemy", "kind": "elem",
                   "type": "light", "power": 1.6, "boost": "power", "spell": True, "desc": "光，单体"},
    "prayer_to_the_flame": {"job": "Cleric", "name": "Prayer to the Flame", "zh": "圣火的祈祷", "sp": 8, "target": "ally",
                            "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个队友物防和属防上升 2/4/6/8 回合"},
    "mystical_staff": {"job": "Cleric", "name": "Mystical Staff", "zh": "吸魔杖击", "sp": 6, "target": "enemy",
                       "kind": "phys", "type": "staff", "power": 0.9, "hits": 2, "boost": "power",
                       "desc": "杖，单体 2 次，回复相当于伤害 10% 的 SP"},
    "luminescence": {"job": "Cleric", "name": "Luminescence", "zh": "光明魔法", "sp": 14, "target": "enemies", "kind": "elem",
                     "type": "light", "power": 1.0, "boost": "power", "spell": True, "desc": "光，全体"},
    "sacred_shield": {"job": "Cleric", "name": "Sacred Shield", "zh": "守护之圣盾", "sp": 10, "target": "ally",
                      "boost": "count", "levels": [50, 65, 80, 100], "desc": "单个队友下一次受到的伤害减少 50/65/80/100%"},
    "revive": {"job": "Cleric", "name": "Revive", "zh": "复活魔法", "sp": 40, "target": "allies", "boost": "power",
               "spell": True, "desc": "复活全体倒下的队友，恢复最大 HP 10%×(1+BP)"},
    "aelfrics_blessing": {"job": "Cleric", "name": "Aelfric's Blessing", "zh": "圣火神爱尔福林克的指引", "sp": 30,
                          "target": "ally", "divine": True,
                          "desc": "神技：3 回合内，该队友每回合末尾额外行动一次"},

    # ---------------- 学者 Scholar（Osvald）----------------
    "fireball": {"job": "Scholar", "name": "Fireball", "zh": "火焰魔法", "sp": 14, "target": "enemies", "kind": "elem",
                 "type": "fire", "power": 1.0, "boost": "power", "spell": True, "desc": "火，全体"},
    "icewind": {"job": "Scholar", "name": "Icewind", "zh": "冰冻魔法", "sp": 14, "target": "enemies", "kind": "elem",
                "type": "ice", "power": 1.0, "boost": "power", "spell": True, "desc": "冰，全体"},
    "lightning_bolt": {"job": "Scholar", "name": "Lightning Bolt", "zh": "雷击魔法", "sp": 14, "target": "enemies",
                       "kind": "elem", "type": "lightning", "power": 1.0, "boost": "power", "spell": True,
                       "desc": "雷，全体"},
    "stroke_of_genius": {"job": "Scholar", "name": "Stroke of Genius", "zh": "灵光一闪", "sp": 5, "target": "self",
                         "boost": "count", "levels": [2, 3, 4, 5], "desc": "随机获得 2/3/4/5 个属性上升（3 回合，重复则延长）"},
    "elemental_barrage": {"job": "Scholar", "name": "Elemental Barrage", "zh": "属性混乱", "sp": 10, "target": "random",
                          "kind": "elem", "type": "random_fil", "power": 0.8, "boost": "hits",
                          "levels": [[3, 5], [4, 6], [5, 7], [6, 8]], "spell": True,
                          "desc": "火/冰/雷随机，随机攻击敌人 3-5/4-6/5-7/6-8 次"},
    "advance_magic": {"job": "Scholar", "name": "Advanced Magic", "zh": "大魔法化", "sp": 15, "target": "ally",
                      "desc": "单个队友接下来 2 次魔法强化为第 2 阶（全体魔法打 2 次，单体魔法和恢复 ×1.5）"},
    "alephans_wisdom": {"job": "Scholar", "name": "Alephan's Wisdom", "zh": "硕学王阿雷芬的知识", "sp": 30, "target": "ally",
                        "divine": True, "desc": "神技：单个队友接下来 3 次魔法强化为第 3 阶（全体魔法打 3 次，单体魔法和恢复 ×2）"},

    # ---------------- 舞娘 Dancer（Agnea）----------------
    "lion_dance": {"job": "Dancer", "name": "Lion Dance", "zh": "狮子之舞", "sp": 4, "target": "ally",
                   "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个队友物攻上升 2/4/6/8 回合"},
    "ruinous_kick": {"job": "Dancer", "name": "Ruinous Kick", "zh": "猛踢要害", "sp": 10, "target": "enemy",
                     "kind": "phys", "type": None, "power": 2.0, "boost": "power", "shield_break": 1,
                     "desc": "无属性物理单体强力攻击，无视弱点削减 1 护盾"},
    "peacock_strut": {"job": "Dancer", "name": "Peacock Strut", "zh": "孔雀之舞", "sp": 4, "target": "ally",
                      "boost": "dur", "levels": [2, 4, 6, 8], "desc": "单个队友属攻上升 2/4/6/8 回合"},
    "sweeping_gale": {"job": "Dancer", "name": "Sweeping Gale", "zh": "旋风", "sp": 7, "target": "enemy", "kind": "elem",
                      "type": "wind", "power": 1.6, "boost": "power", "spell": True, "desc": "风，单体"},
    "stimulate": {"job": "Dancer", "name": "Stimulate", "zh": "推波助澜", "sp": 5, "target": "ally_other",
                  "boost": "count", "levels": [1, 2, 3, 99], "desc": "让一名其他队友的下一次行动提前 1/2/3 位/最先"},
    "dagger_dance": {"job": "Dancer", "name": "Dagger Dance", "zh": "短刀之舞", "sp": 9, "target": "enemies",
                     "kind": "phys", "type": "dagger", "power": 1.0, "boost": "power", "desc": "短剑，全体"},
    "bewildering_grace": {"job": "Dancer", "name": "Bewildering Grace", "zh": "百思不解之舞", "sp": 25, "target": "self",
                          "boost": "count", "levels": [1, 2, 3, 4], "desc": "随机触发 1/2/3/4 个奇妙效果（有好有坏）"},
    "sealticges_seduction": {"job": "Dancer", "name": "Sealticge's Seduction", "zh": "舞姬希尔缇吉的话", "sp": 30,
                             "target": "ally", "divine": True,
                             "desc": "神技：3 回合内，该队友的单体技能改为作用于全体（神技和只作用于自己的技能除外）"},
}

# 潜力专属技能（原创：原作中 Hikari / Ochette 的潜力会解锁专属技能，具体技能这里自行设计）
LATENT_SKILLS = {
    # 招式基础定义，文件末尾应用核对后的效果和档位。
    "tenretsu": {"job": "hikari", "name": "Tenretsu", "zh": "天裂斩", "sp": 0, "target": "enemy", "kind": "phys",
                 "type": "sword", "power": 3.6, "boost": "power", "desc": "潜力专属：剑，单体 1 次强力斩击"},
    "hien": {"job": "hikari", "name": "Hien", "zh": "飞燕华", "sp": 0, "target": "enemy", "kind": "phys",
             "type": "sword", "power": 1.1, "hits": 2, "boost": "power", "desc": "潜力专属：剑，单体 2 次，之后立刻再行动一次"},
    "sougetsu": {"job": "hikari", "name": "Sougetsu", "zh": "双月闪", "sp": 0, "target": "enemies", "kind": "phys",
                 "type": "sword", "power": 1.0, "hits": 2, "boost": "power", "desc": "潜力专属：剑，全体 2 次"},
    "beast_claw": {"job": "ochette", "name": "Beast Claw", "zh": "兽之爪", "sp": 0, "target": "enemy", "kind": "phys",
                   "type": "axe", "power": 1.0, "hits": 3, "boost": "power", "desc": "潜力专属：斧，单体 3 次"},
    "beast_fang": {"job": "ochette", "name": "Beast Fang", "zh": "兽之牙", "sp": 0, "target": "enemy", "kind": "phys",
                   "type": "axe", "power": 1.6, "hits": 2, "boost": "power", "shield_break": 1,
                   "desc": "潜力专属：斧，单体 2 次，额外无视弱点削减 1 护盾"},
    "beast_roar": {"job": "ochette", "name": "Beast Roar", "zh": "兽之咆哮", "sp": 0, "target": "enemies",
                   "kind": "elem", "type": "lightning", "power": 1.2, "boost": "power",
                   "desc": "潜力专属：雷，全体，并使敌人物攻下降 2 回合"},
}

# 药师调合（原创：原作 Castti 的调合需要材料，这里简化为 4 个配方 + 有限材料）
CONCOCT = {
    "elixir": {"zh": "复苏药", "desc": "全体队友恢复最大 HP 15%×(1+BP)"},
    "phoenix": {"zh": "还魂药", "desc": "复活一名倒下的队友（target 填队友 id），恢复最大 HP 25%×(1+BP)；没有倒下队友时改为治疗该队友"},
    "toxin": {"zh": "毒雾", "desc": "全体敌人受到 0.5×(1+BP) 倍威力的无属性伤害，并中毒 3 回合"},
    "firebomb": {"zh": "火焰瓶", "desc": "全体敌人受到 0.9×(1+BP) 倍威力的火属性伤害（削护盾）"},
}

JOB_SKILLS = {}
for _sid, _s in SKILLS.items():
    JOB_SKILLS.setdefault(_s["job"], []).append(_sid)
TRAVELER_SKILLS = {k: JOB_SKILLS[v["job_en"]] for k, v in TRAVELERS.items()}

# 可用 -o 覆盖的全局估计系数
ESTIMATED = {
    "damage_k": 0.45,         # 伤害 = k × 威力 × 攻² / 防（估计）
    "weak_mult": 1.3,         # 打中弱点伤害倍率
    "break_mult": 2.0,        # 击破状态受到伤害倍率
    "crit_mult": 1.5,
    "defend_mult": 0.5,       # 防御时受到伤害倍率
    "buff_mult": 1.5,         # 属性上升
    "debuff_mult": 0.67,      # 属性下降
    "poison_pct": 1/6,       # 中毒每次行动后扣最大 HP 的比例
    "regen_pct": 0.20,
    "latent_per_dmg": 130.0,  # 受到相当于最大 HP 的伤害时原始潜力能量 +130
    "latent_per_break": 25.0,
    "latent_per_action": 0.0,
    "materials": 4,           # 药师调合材料数
    "speed_jitter": 0.08,     # 行动顺序的速度随机浮动 ±8%
}


# Source-backed parameters are kept separate from arena-only rules.
import json as _json
from pathlib import Path as _Path
VERIFIED_VALUES = _json.loads((_Path(__file__).with_name("verified_values.json")).read_text(encoding="utf-8"))
for _key, _sk in {**SKILLS, **LATENT_SKILLS}.items():
    if _key in VERIFIED_VALUES:
        _rec = VERIFIED_VALUES[_key]
        _sk["sp"] = _rec["sp"]
        _sk["hit_ratios"] = [x["hit_ratio"] for x in _rec["levels"]]
        _sk["ability_ratios"] = [x["ratio"] for x in _rec["levels"]]
        _sk["invocation_values"] = [next((e["value"] / 100 for e in x["effects"] if "DAMAGE" in e["effect"] and "SP_DAMAGE" not in e["effect"]), 0) for x in _rec["levels"]]
        if "tiers" in _rec:
            _sk["tier_parameters"] = _rec["tiers"]
        if "kind" in _sk:
            _sk["power"] = _sk["ability_ratios"][3 if _sk.get("divine") else 0] * _sk["invocation_values"][3 if _sk.get("divine") else 0]
        _sk["spell"] = _key in ("fireball", "icewind", "lightning_bolt", "luminescence", "heal_wounds", "revive")
SKILLS["bifelgans_bounty"]["kind"] = "elem"
SKILLS["aebers_reckoning"].pop("use_spd", None)
SKILLS["aebers_reckoning"]["desc"] = "全体短剑攻击；以物攻计算基础伤害，再乘 (0.84 + 当前速度/500)"
SKILLS["advance_magic"].update(boost="count", levels=[2,3,4,5], desc="使一名队友接下来2/3/4/5次适用魔法强化为二阶；魔法强化加成另加1次")
SKILLS["rest"]["desc"] = "按施术者基础属防、恢复系数和等级系数恢复HP；恢复25/50/75/100 SP，解除中毒"
SKILLS["enervating_slash"]["desc"] = "消除目标的正面效果，按消除数量提高此次攻击伤害"
SKILLS["bifelgans_bounty"]["desc"] = "神技：无属性单体魔法伤害；本赛事战斗中不增加赛前金钱"
LATENT_SKILLS["beast_claw"].update(target="enemies", type=None, hits=1, desc="潜力专属：全体一次无武器属性物理伤害")
LATENT_SKILLS["beast_fang"].update(type=None, hits=1, shield_break=0, desc="潜力专属：单体一次无武器属性物理伤害")
for _k in ("kind","power","type"):
    LATENT_SKILLS["beast_roar"].pop(_k, None)
LATENT_SKILLS["beast_roar"].update(boost="dur", levels=[3,4,5,6], desc="全体敌人物防、属防下降3/4/5/6回合，并无视弱点削1盾；不造成HP伤害")
LATENT_SKILLS["sougetsu"].update(hits=2, desc="潜力专属：全体先受一次剑攻击，再受一次长柄武器攻击")
LATENT_SKILLS["hien"]["desc"] = "潜力专属：单体两次剑攻击，在本回合末追加一次行动；每回合最多追加一次"
ESTIMATED.pop("damage_k", None)
ESTIMATED.update(level_multiplier=1.36328125, crit_mult=1.25, damage_random_min=1.01, damage_random_max=1.05)

SKILLS["revive"]["desc"] = "复活全体倒下队友；恢复量按属防、档位与魔法阶数计算，零BP一阶复活仅恢复1 HP"
SKILLS["alephans_wisdom"]["desc"] = "使一名队友接下来3次适用魔法强化为三阶；魔法强化加成另加1次"
SKILLS["prayer_to_the_flame"].update(levels=[2,4,6,8], desc="一名队友物防与属防上升2/4/6/8回合")
