# 旅人对决 AI 竞赛：参赛规则与接口

规则版本：v1.1。

## 本届HP与奥义规则

全员99级，无装备和坚果。每名角色先按基础属性、副职百分比加成和支援技能计算最大HP，最后固定增加 **{{ARENA_HP_BONUS}} HP**，并以这个最终最大HP满血开局；此项不占JP、金钱或支援技能槽位。固定增加值不再乘副职百分比，不限制HP为9999。

`init.travelers[*].hp` 和旅人属性表中的HP是未配置的基础HP，不包含这项固定增加值。`init.arena_rules.hp_bonus` 公布固定增加值；战斗观测中的 `max_hp`、回放中的 `unit_max` 是配置和固定增加后的最终值。

满足SP、BP及技能条件时，**第一回合即可使用职业奥义**。奥义需要3 BP；开局满潜力支援保持满潜力。第一回合按正常伤害公式结算。按最大HP比例计算的恢复、复活、中毒、潜力增长和回合上限判定均使用最终最大HP。

## 提交要求
- 每位AI只提交一个最终版本，比赛期间不修改代码。模型API只用于赛前生成代码，比赛中的策略不得调用API。
- 自测使用 `python kit.py check`；主办方会独立复测，选手自测报告不等同于正式准入。


- 提交**一个 Python 3 源文件**（Python 3.9+），只能使用标准库（`json`、`math`、`sys`、`random`、`itertools` 等）。不能联网、不能读写文件、不能启动子进程。
- 程序通过**标准输入**逐行接收 JSON 消息，通过**标准输出**逐行回复 JSON，每条回复后必须 `flush`（`print(..., flush=True)`）。
- 标准输出**只能**写协议消息；调试信息写到标准错误 `sys.stderr`。
- **每一步都要回复，包括非行动方**；非行动方回复 `{"tick": t}`。每个策略每步最多1秒现实时间；整局CPU时间预算60秒，包含用户态和内核态计算，睡眠等待不计CPU时间，但仍受每步1秒限制。 内存上限256 MiB。init与第一次turn共用首个响应窗口，无额外3秒准备时间。整支队伍共享一个策略进程及其预算。
- 任意超时、协议错误或崩溃后停止该策略；剩余选人由引擎随机补齐、缺少配置使用空配置、战斗使用引擎默认行动。比赛继续按战况判胜负，故障不直接判负或平局。

## 对局流程

一场比赛由很多"步"（tick）组成，每一步是一次决策：

1. **选人阶段**：从 8 名旅人中选 `team_size`（默认 4）人。
   - `pick_mode = "blind"`（默认）：tick 0 双方**同时**一次选完 4 人，看不到对方选了谁，**两队可以选相同的旅人**（同一队内不能重复）。
   - `pick_mode = "draft"`：蛇形轮流，每步一方选 1 人，顺序 A B B A A B B A，被任意一方选过的旅人不能再选。
   - 你选的顺序就是队员 id（0、1、2、3）。
2. **赛前配置阶段**（一步）：双方**同时**提交配置：每人的副职业、用 JP 学的副职技能、支援技能，以及全队带进战斗的道具。
   两队的**预算完全相同**（全队共用的 JP 和金钱），提交时**看不到对手的配置**（blind 选人时连对手选了谁也看不到），战斗开始时双方配置公开。
3. **战斗阶段**：每一步是**某一个角色的一次行动**。轮到你的角色行动时 `your_turn` 为 true，你给出这个角色的行动；其余步你只需回 `{"tick": t}`。
4. 一方全员倒下时比赛结束。达到 `max_rounds`（默认 30）回合仍未分出胜负时，比较双方"每个队员剩余 HP / 最大 HP"的总和，高者胜，相同为平局。
   引擎结果值胜1、平0.5、负0，仅用于辨认胜负；总榜每局换算为胜3、平1、负0。

## 通信协议

所有消息都是单行 JSON。

### 1. 开局（init）

```json
{"type": "init", "time_limit_ms": 1000, "total_time_ms": 60000, "time_budget_type": "cpu_user_system", "game": "octopath", "you": 0, "team_size": 4, "pick_mode": "blind",
 "max_rounds": 30, "max_bp": 5, "max_boost": 3,
 "arena_rules": {"hp_bonus": {{ARENA_HP_BONUS}}, "hp_bonus_order": "after_loadout", "divine_first_round": true},
 "travelers": {"hikari": {"name": "光", "name_en": "Hikari", "job": "剑士", "job_en": "Warrior", "hp": 5781, "sp": 145, "pa": 342, "pd": 313,
                          "ea": 256, "ed": 228, "acc": 313, "eva": 228, "crit": 285, "spd": 285,
                          "weapons": ["sword", "polearm"], "shields": 7, "weak": ["axe", "bow", "ice", "wind"],
                          "skills": ["aggressive_slash", "..."], "latent_power": {"name": "阴之力", "desc": "..."},
                          "latent_skills": ["tenretsu", "hien", "sougetsu"]}, "...": "..."},
 "skills": {"aggressive_slash": {"job": "Warrior", "name": "Aggressive Slash", "zh": "五月雨斩", "sp": 9, "target": "random",
                                 "kind": "phys", "type": "sword", "power": 0.9, "boost": "hits", "levels": [3, 4, 5, 6], "desc": "..."}, "...": "..."},
 "concoct_recipes": {"elixir": {"zh": "复苏药", "desc": "..."}, "...": "..."},
 "types": ["sword", "polearm", "dagger", "axe", "bow", "staff", "fire", "ice", "lightning", "wind", "light", "dark"],
 "constants": {"level_multiplier": 1.36328125, "weak_mult": 1.3, "break_mult": 2.0, "crit_mult": 1.25, "defend_mult": 0.5, "...": "..."},
 "loadout_enabled": true,
 "loadout_rules": {"budget": {"jp": 12000, "gold": GOLD},
                   "jp_costs": [30, 100, 500, 1000, 3000, 5000], "free_skills": 2, "support_unlock": [4, 5, 6, 7],
                   "support_slots": 4, "licenses": 3,
                   "jobs": {"Warrior": {"zh": "剑士", "bonus_pct": {"hp": 18, "pa": 5, "pd": 5}, "weapons": ["sword", "polearm"],
                                        "skills": ["aggressive_slash", "..."], "free_skills": ["aggressive_slash", "piercing_thrust"],
                                        "divine": "brands_blade", "supports": ["bolstering_break", "summon_strength", "latent_power_plus", "deal_more_damage"]}, "...": "..."},
                   "supports": {"summon_strength": {"job": "Warrior", "n": 2, "zh": "物攻+50", "desc": "...", "battle": true}, "...": "..."},
                   "items": {"healing_grape": {"name": "Healing Grape", "zh": "...", "price": 50, "target": "ally", "fx": {"hp": 500}, "desc": "..."}, "...": "..."},
                   "item_stack": 99}}
```

必须回复 `{"ready": true}`。下文所有数值都以这条消息里的为准（比赛可能用 `-o` 调整了常数）。

### 2. 选人阶段的每一步

```json
{"type": "turn", "tick": 0, "phase": "pick", "your_turn": true, "pick_count": 4, "pick_mode": "blind",
 "available": ["hikari", "agnea", "partitio", "osvald", "temenos", "throne", "ochette", "castti"],
 "my_picks": [], "opponent_picks": []}
```

轮到你时回复 `pick_count` 个旅人 key（顺序 = 队员 id）：

```json
{"tick": 0, "pick": ["temenos", "osvald", "hikari", "throne"]}
```

选人名单数量、类型或ID错误属于协议错误，停止策略；引擎随后随机分配。

### 3. 赛前配置（选人结束后的一步）

```json
{"type": "turn", "tick": 1, "phase": "loadout", "your_turn": true, "my_picks": ["temenos", "osvald", "hikari", "throne"],
 "opponent_picks": [], "budget": {"jp": 12000, "gold": GOLD}}
```

`opponent_picks` 只在 draft 选人时有内容（blind 时你不知道对手是谁）。回复 `loadout`（按队员 id 顺序的列表，也可以用 `{"0": {...}, "1": {...}}`，每人一份）和 `items`（全队的道具袋）：

```json
{"tick": 1, "loadout": [
  {"sub_job": "Scholar", "learn": ["lightning_bolt", "stroke_of_genius", "elemental_barrage", "advance_magic"],
   "supports": ["rise_again", "elemental_augmentation", "resilience", "inner_strength"]},
  {"...": "..."}, {"...": "..."}, {"...": "..."}],
 "items": {"healing_grape": 10, "olive_of_life": 3}}
```

| 字段 | 说明 |
|---|---|
| `sub_job` | 副职业，8 个基础职业之一（`Warrior` `Merchant` `Thief` `Apothecary` `Hunter` `Cleric` `Scholar` `Dancer`）。不能和本职相同；每个职业只有 3 张执照，一队最多 3 人选同一个副职。不填 = 没有副职 |
| `learn` | 用 JP 学的副职技能 id。副职的 2 个初始技能（`free_skills`，原作的默认技能）自动学会，不用写。每个职业和原作一样有 8 个技能；偷窃、收集金钱、雇佣帮手、分析（`nonbattle_skills`）在对战里没有效果，但同样可以花 JP 学，也算进"会几个技能"。价格按**学的顺序**算：第 1 个 30、第 2 个 100、500、1000、3000，神技 5000，且神技要先学会其他全部技能。全队 4 人的花费加起来不能超过 `budget.jp` |
| `supports` | 最多 4 个支援技能 id。本职的 4 个支援技能都能装（旅人本职已经精通）；副职的第 1～4 个支援技能在副职会 4/5/6/7 个技能（含免费的 2 个）时解锁。`battle: false` 的支援技能只在原作探索时有用，不能装 |
| `items` | `{道具 id: 个数}`，全队共用一个道具袋，每种最多 `item_stack` 个，总价（价格见下方"道具"表）不能超过 `budget.gold`。战斗中任何队员都可以用，用掉就少一个 |

**不合法时**：单个条目不合法（未知 id、栏位已满、支援技能没解锁等）只忽略那一条；JP 或金钱的**全队总花费超预算，全队这一项全部作废**（JP 超了没有副职技能，金钱超了不带道具）；不回复或超时，全队都没有配置。被忽略的内容会出现在事件 `loadout` 的 `notes` 里。

**属性怎么算**：`最终属性 = 基础属性 × (1 + 副职加成%) + 支援技能固定加值`。本竞技场**没有装备和坚果**。

### 4. 战斗阶段的每一步

```json
{"type": "turn", "tick": 5, "phase": "battle", "round": 2, "your_turn": true, "actor": 1,
 "me": [ {单位}, {单位}, {单位}, {单位} ],
 "opponents": [ {单位}, ... ],
 "current": [0, 1],
 "queue": [[1, 2], [0, 3]],
 "next_round_order": [[0, 0], [1, 2], ...],
 "available_skills": [{"id": "attack", "sp": 0, "usable": true}, {"id": "fireball", "sp": 14, "usable": true}, ...],
 "my_items": {"healing_grape": 9, "olive_of_life": 3}, "opponent_items": {"...": 1},
 "usable_items": ["healing_grape", "olive_of_life"],
 "last_events": [ ... ]}
```

- `actor`：这一步要行动的**己方**队员 id（不轮到你时为 null）。
- `current`：当前行动者 `[阵营, id]`，**阵营 0 = 你，1 = 对手**（所有 `[阵营, id]` 都是这个约定）。
- `queue`：本回合在当前行动者之后、还没行动的角色顺序（被击破/倒下的已移除）。
- `next_round_order`：按当前速度和优先级预估的下回合顺序（不含随机浮动，仅供参考）。
- `available_skills`：当前行动者能选的全部行动和是否可用（SP 够不够、潜力是否就绪、材料是否够），包括学会的副职技能。
- `my_items` / `opponent_items`：双方道具袋里还剩的道具（用完的不再出现）。`usable_items`：当前行动者现在能用的道具（复活类道具要有倒下的队友才能用）。
- `last_events`：上一步发生的事件（见下文"事件"），方便你追踪对手做了什么。

**单位**的字段：

```json
{"id": 1, "traveler": "osvald", "name": "奥兹巴尔多", "alive": true,
 "hp": 3557, "max_hp": 3557, "sp": 218, "max_sp": 218, "bp": 1,
 "shields": 5, "max_shields": 5, "weaknesses": ["sword", "dagger", "fire", "lightning"],
 "broken": false, "broken_until_round": null,
 "latent": 35.5, "latent_ready": false, "weapons": ["staff"],
 "stats": {"pa": 256, "pd": 256, "ea": 370, "ed": 342, "spd": 256, "crit": 228, "acc": 285, "eva": 285},
 "buffs": {"ea": 3}, "debuffs": {}, "status": {"poison": 2}, "defending": false,
 "spell_tier": 1, "spell_tier_charges": 0, "boosted_this_round": false, "materials": 4,
 "sub_job": "Cleric", "skills": ["fireball", "...", "heal_wounds", "holy_light"], "supports": ["elemental_augmentation", "..."],
 "rise_again_ready": false}
```

- `stats` 是**已计入副职、支援技能和增益/减益**后的当前值。`weapons` 是能用的武器类型（本职 + 副职），武器只决定攻击类型，不加属性。
- `sub_job` / `skills` / `supports`：赛前配置的结果（双方公开）；`rise_again_ready`：支援技能"自动复活"还没用掉。`buffs` / `debuffs` 是 `{属性: 剩余次数}`。
- `status` 里可能出现：`poison` 中毒、`poison_weak` 弱毒、`immune` 异常免疫、`taunt` 挑衅、`counter` 反击剩余次数、`sidestep` 闪避剩余次数、`sacred` 圣盾减伤百分比、`regen` 持续恢复、`leghold` 捕兽夹、`extra` 祝福（回合末额外行动）、`spread` 魅惑（单体变全体）、`charity` 慈悲、`ward` 预防药（还能挡几次属性下降）。
- `broken_until_round`：被击破的单位在这一回合开始时恢复。
- `materials` 只有卡斯蒂（castti）有（调合材料数）。
- 双方信息完全公开（包括对手的弱点、护盾、SP、BP）。

轮到你时回复：

```json
{"tick": 5, "action": {"skill": "fireball", "target": 2, "boost": 2, "latent": false}}
```

| 字段 | 说明 |
|---|---|
| `skill` | `"attack"`（普通攻击）、`"defend"`（防御）、`"item"`（使用道具）、`"concoct"`（卡斯蒂的调合）、该旅人的技能 id，或潜力专属技能 id |
| `target` | 目标 id：对敌技能填对手 id，对己方技能填己方 id；全体/随机/自身技能可省略 |
| `targets` | 只对 target 为 `chosen` 的技能（狙击）有效：每一击的目标 id 列表，不够的次数重复最后一个；省略时全部打 `target` |
| `boost` | 0～3，花多少 BP 加成（超过现有 BP 会被截断）。防御和没有加成效果的技能不能加成，不会扣 BP。神技固定花 3 BP，不看这个字段 |
| `latent` | true 表示本次行动先发动潜力（需要 `latent_ready`） |
| `weapon` | 只对普通攻击有效：用哪种武器（必须是该角色 `weapons` 之一，默认第一种） |
| `recipe` | 只对调合有效：`elixir` / `phoenix` / `toxin` / `firebomb` |
| `item` | 只对 `"skill": "item"` 有效：道具 id，必须在 `usable_items` 里 |

**默认行动**：超时、回复格式错误、技能不存在/不属于该角色/SP 不够、道具没有或现在不能用时，按**普通攻击**处理（目标优先用你给的 `target`，否则打对方第一个活着的角色），加成照常按 `boost` 处理。

### 5. 结束（end）

```json
{"type": "end", "scores": [1, 0]}
```

## 战斗规则

### 回合与行动顺序

- 每回合开始时，所有活着且未被击破的角色排成行动顺序：先按优先级（上回合**防御**过的最先；被**捕兽夹**的最后；其他居中），同优先级按 `速度 × (1 ± speed_jitter)` 从高到低（`speed_jitter` 默认 0.08，即每回合有 ±8% 的随机浮动）。
- **激励**（Stimulate）可以把队友在队列里的位置提前；如果该队友本回合已经行动，则提前他下回合的位置。
- 所有人行动完后，有**祝福**（艾尔弗里克的祝福）状态的角色在回合末各额外行动一次，然后进入下一回合。
- 盗贼的潜力「残影」会让她在本次行动后立刻再行动一次。

### BP 与加成（Boost）

- 每个角色开局 1 BP，上限 5。从第 2 回合起，每回合开始时，活着且未被击破的角色 +1 BP，**但上一回合用过加成的角色这回合不加**（原作规则）。
- 每次行动最多花 3 BP。**神技（★）只能以最大加成发动**（原作规则）：必须有至少 3 BP，发动时固定消耗 3 BP，效果已按最大加成设计；BP 不足 3 时神技不可用（商人发动潜力补满 BP 的同一次行动可以用）。
- 其他技能按 `boost` 字段决定加成效果，`levels` 是 0/1/2/3 BP 时的数值：
  - `power`：威力（或恢复量）×(1 + BP)。
  - `hits`：攻击次数取 `levels[BP]`（元素乱射是区间，随机取）。
  - `crit`：暴击率取 `levels[BP]` %。
  - `dur`：持续次数取 `levels[BP]`。
  - `count`：次数/数量/百分比取 `levels[BP]`。
- 普通攻击：每 1 BP 多打 1 下（BP 3 = 4 连击）。
- 被击倒会失去全部 BP。

### 伤害与治疗

常规攻击每击按下面的公式计算，具体参数以开局技能表和 `verified_values.json` 为准：

```
基础伤害 = (min(999,攻击) × invocation - min(999,防御)/2) × ability_ratio × 1.36328125
最终伤害 = 基础伤害 × 增减益倍率 × 技能特殊倍率 × 状态倍率 × 暴击倍率 × 防御倍率 × 随机(1.01～1.05)
```

`invocation_values[BP]` 和 `ability_ratios[BP]` 给出四档参数；神技按BP=3取值。普通攻击invocation=1、ability_ratio=0.8，加成增加攻击次数。全员使用99级属性与等级伤害系数1.36328125。
物理攻击使用基础物攻和目标基础物防；魔法使用基础属攻和目标基础属防。观测中的 `base_stats` 给出这些基础值，含副职与支援技能加值，不含战斗中的攻防增减益。攻方攻击上升×1.5、下降×2/3；目标防御下降×1.5、上升×2/3，作用于伤害而非先改基础攻防。
状态倍率：目标击破中为2；否则命中弱点为1.3；否则为1。弱点和击破不叠乘。物理暴击通常×1.25，消除增益的剑技为×1.2；魔法不暴击。防御中×0.5；圣盾另乘其减伤比例。
最终伤害最低1（完全减伤可以为0），每击取整，伤害上限9999，突破伤害界限时99999。无属性攻击不命中武器或元素弱点。
治疗使用施术者基础属防×恢复invocation×ability_ratio×等级系数×恢复支援倍率×0.98～1.02随机值，不使用属攻或属防增益。数据详见 `verified_values.json`。道具固定效果另行计算。
盗贼神技以物攻计算，再乘(0.84+当前速度/500)；学者潜力使适用的全体魔法集中为单体并使伤害×2。
物理命中率 = clamp(round(50×(3−目标回避/自身命中)+招式命中补正,3)/100,0.2,1)；普通攻击补正20，其他招式见 `hit_ratios[BP]`。击破目标无自然闪避。自然暴击率 = clamp((自身暴击−目标速度)/200,0,1)。上述命中、回避、暴击和速度使用战斗增减益后的属性。本届回避率上升支援使落空率额外增加20个百分点；击破中的目标仍无自然闪避。陷阱触发后随机减益持续2回合。

### 护盾、弱点与击破（Break）

- 每个旅人有固定的护盾数和 4 个弱点（见下表；原作中旅人不会成为敌人，护盾和弱点是本竞技场的设计）。
- 每一击如果攻击类型（`type`，武器或属性）是目标的弱点，目标护盾 -1。带 `shield_break` 的技能每击额外削对应数量，无视弱点。
- 护盾归零即**击破**：
  - 如果本回合还没行动，失去本回合的行动；**下一回合也不能行动**；
  - 击破期间受到的伤害 ×`break_mult`（2.0），护盾不再减少，不回复 BP；
  - 在 `broken_until_round` 那一回合开始时恢复，护盾回满。
- 被击倒的角色复活后护盾回满。

### 状态持续时间

文档里写的"N 回合"实际按**该角色自己的行动次数**计算：每次该角色行动结束后，它身上的增益、减益、中毒、弱毒、免疫、挑衅、持续恢复、捕兽夹、魅惑、慈悲各减 1（被击破期间不行动，所以不会减少）。祝福（extra）每回合末使用一次减 1。
行动结束后依次结算：持续恢复（最大 HP 的 `regen_pct`），中毒（最大 HP 的 `poison_pct`，可能致死；弱毒时每次中毒结算削1盾，不增加中毒伤害）。

### 魔法强化

只有技能表 `spell: true` 的技能消耗强化次数：学者三种全体元素魔法、光明魔法、恢复魔法、复活魔法。二阶、三阶使用 `tier_parameters[阶数-1][BP]` 的独立参数；全体攻击魔法分别打2次、3次。单体元素魔法与属性混乱不受魔法强化影响。
大魔法化提供2/3/4/5次强化，硕学王的知识提供3次；施术者的魔法强化加成支援另加1次。

### 潜力（Latent Power）

- 潜力显示为0～100%的归一化能量；`latent_capacity` 为原始容量：欧修缇、爱格妮娅、提米诺斯、光125，其余100。受伤获得floor(130×实际扣血/最大HP)原始能量，击破获得25；普通行动本身不加能量。支援技能增加的原始能量也按个人容量换算百分比。
- 能量满 100（`latent_ready`）时，行动里写 `"latent": true` 即在本次行动开始时发动，能量清零。发动潜力不占行动，之后照常执行 `skill`（也可以同时加成）。
- 各旅人的潜力：

| 旅人 | 潜力 | 本竞技场的效果 |
|---|---|---|
| 光 hikari | 阴之力 | 本次行动可以使用 `tenretsu` 天裂斩 / `hien` 飞燕华 / `sougetsu` 双月闪（不消耗 SP） |
| 爱格妮娅 agnea | 齐心协力 | 本次行动的单体技能（含普通攻击、单体辅助）改为作用于全体 |
| 帕特提欧 partitio | 气势 | BP 立刻补满 5，再执行行动（可以接着加成） |
| 奥兹巴尔多 osvald | 魔法集合化 | 本次的全体攻击魔法只打你指定的一个敌人，伤害 ×2 |
| 提米诺斯 temenos | 审判 | 本次行动的每一击都削 1 护盾，无视弱点 |
| 斯洛妮 throne | 残影 | 本次行动后立刻再行动一次 |
| 欧修缇 ochette | 兽之力 | 本次行动可以使用 `beast_claw` 兽之爪 / `beast_fang` 兽之牙 / `beast_roar` 兽之咆哮（不消耗 SP） |
| 卡斯蒂 castti | 节约 | 本次调合不消耗材料，并按 BP 3 的效果生效（不花 BP） |

### 调合（卡斯蒂专属）

`"skill": "concoct"` 消耗 1 份材料（开局 `materials` 份，默认 4），不消耗 SP，可以加成（威力 ×(1+BP)）：

{{CONCOCT_TABLE}}

### 道具

`"skill": "item"` 加 `"item": 道具 id`：从全队道具袋里用掉 1 个，任何队员都能用，不消耗 SP，**不能加成**（原作规则，`boost` 被忽略，不扣 BP）。目标：

- `ally`：单个己方（`target` 填己方 id，默认自己）；`allies`：全体己方。
- `ko`：倒下的己方（`target` 填 id；不填或填了活着的人时，复活第一个倒下的队友）。没有倒下的队友时不能用。
- `enemy`：单个敌人（受挑衅影响）；`enemies`：全体敌人。
- 攻击道具（精灵石）造成**固定伤害**：不看双方属攻/属防，也不乘弱点、击破、防御倍率（圣盾照样减伤），但打中弱点会削 1 护盾。

道具表见文末"道具"。

### 防御

`"skill": "defend"`：直到自己下次行动前，受到的伤害 ×`defend_mult`（0.5）；下回合最先行动。

## 事件（last_events）

每步结束后的事件列表，`u` 是发起者、`t` 是目标，都是 `[阵营, id]`（0 = 你）：

| e | 含义 |
|---|---|
| `pick` | 选人结果 `{"team", "picks", "auto"}` |
| `round` / `order` | 新回合开始 `r`，行动顺序 `o` |
| `turn` | `u` 开始行动 |
| `latent` / `boost` | 发动潜力 / 加成 `n` BP |
| `skill` | 使用技能 `s`（普通攻击带武器 `w`，调合带配方 `r`，道具 `s = "item"` 带道具 id `it`） |
| `hit` | 一击：伤害 `d`，类型 `ty`，`w`=打中弱点，`c`=暴击，`miss`=落空，`dodge`=被闪避 |
| `shield` / `break` / `recover` | 护盾剩余 `v` / 被击破 / 击破恢复 |
| `ko` / `revive` / `heal` | 倒下 / 复活（HP `v`）/ 恢复 `v` |
| `buff` | 属性 `st` 上升（`up`=1）或下降，持续 `r` |
| `status` / `dispel` | 获得状态 `k` / 被解除 `n` 个增益 |
| `poison` / `counter` / `sp` / `bp` / `grace` | 中毒伤害 / 反击 / SP 变化 / BP 变为 `v` / 迷惑之舞效果 `k` |
| `cure` | 道具治好了 `t` 的中毒、弱毒（`n` 个） |
| `loadout` | 赛前配置结束 `{"team", "notes"}`，`notes` 是被忽略的内容 |
| `sup` | 支援技能 `k` 在 `u` 身上触发（坚持到底、自动复活、顺便战斗、陷阱、破防追击等） |
| `end` | 比赛结束 `winner`（0 = 你，1 = 对手，-1 = 平局） |

## 赛前配置数据

下表是本届赛事使用的配置、价格与效果。接口以英文ID为准，中文名仅作说明。

### 职业（副职）

{{JOBS_TABLE}}

### 支援技能

{{SUPPORTS_TABLE}}

### 道具

{{ITEMS_NOTE}}

{{ITEMS_TABLE}}

## 旅人数据

属性为原作 99 级、不带装备的基础值（本竞技场没有装备）。护盾和弱点为本竞技场设计。

{{TRAVELERS_TABLE}}

## 技能表

`target`：`enemy` 单个敌人，`enemies` 全体敌人，`random` 随机敌人（每击单独随机），`chosen` 每一击的目标由你在 `targets` 里指定，`ally` 单个己方（可以是自己），`ally_other` 自己以外的单个己方，`ally_any` 单个己方（可以是倒下的），`allies` 全体己方，`self` 自己。
`power` 是基础档位的便捷字段；实际伤害使用invocation_values和ability_ratios，不应只按power推算，`hits` 是固定打击次数。技能中文名保留当前工程用语，SP消耗按核对表，伤害档位使用随包核对参数。神技（★）必须花 3 BP 发动。

{{SKILLS_TABLE}}


## 本届固定的对战适配

4v4、双方同时隐藏选人、30回合上限、全员99级且无装备/坚果；所有角色都有公开护盾和弱点。潜力以百分比显示。调合使用表中四种配方和统一材料数量，迷惑之舞使用表中有限事件，道具按表中固定效果结算。未收录的探索、召唤、昼夜和剧情机制不加入比赛。回避率上升额外增加20个百分点的落空率，陷阱减益2回合，中毒每次扣最大HP的1/6并向下取整。上述规则对双方一致，依本手册与随包参数执行。
