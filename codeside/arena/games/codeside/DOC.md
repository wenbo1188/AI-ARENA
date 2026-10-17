# 游戏机制与接口源文档

正式规则由根目录 RULES.md 统一生成；本文件只维护游戏机制、协议与数值。

## 单局流程、得分与结束

### 3.1 对局流程

1. 裁判根据赛段和种子创建地图、角色及物品，并启动双方策略进程。
2. 裁判向双方发送 `init`，包含身份、地图、参数和运行预算；策略回复就绪消息。
3. 每个 tick，裁判向双方发送当前状态；双方在时限内返回己方角色动作。
4. 裁判应用动作，推进物理模拟并更新状态，然后进入下一个 tick。
5. 对局结束后，裁判发送 `end` 和双方得分，策略程序退出。

状态由裁判推进。每次动作只对应消息中的那个 tick，策略不能通过发送多条动作自行推进游戏时间。

### 3.2 时间单位

默认每秒 60 tick，每个 tick 包含 100 次物理内部更新。策略仍然每 tick 只回复一次，不需要对内部更新逐次回复。

单局默认上限为 3600 tick，即 60 秒游戏内时间。实际计算或播放所需的现实时间可以不同。

### 3.3 游戏得分

| 事件 | 计分方式 |
|---|---|
| 对敌方造成生命值伤害 | 每点实际伤害计 1 分 |
| 对己方造成伤害 | 不增加伤害得分 |
| 一个角色死亡 | 死亡角色的对手增加 `kill_score`，默认 1000 分 |

伤害得分按实际扣除的生命值结算。角色死亡的加分由角色所属队伍决定。比赛结果以双方游戏得分比较为准。

### 3.4 结束条件

达到以下任一条件时，对局结束：

- 达到 `max_tick_count`。
- 一支队伍的全部角色阵亡。
- 双方策略都被判为崩溃。

只有一名角色阵亡时，2v2 对局可以继续。只有一方策略崩溃时，也不会仅因此立即停止物理模拟；该方不再应用策略动作。


## 4. 世界、单位与移动

### 4.1 坐标与场景

- 世界是二维的，x 轴向右，y 轴向上；地图由 1×1 地块构成，`tiles[x][y]` 从左下角起计。
- 单位、子弹、爆炸、物品和地块均采用与坐标轴平行的矩形区域。
- 单位开局位于出生点，没有武器；地图中有武器、医疗包和地雷物品。
- 每个 tick 先向策略发送世界状态，接收动作后更新世界。默认每秒 60 tick，每 tick 包含 100 次内部更新，最多 3600 tick。
- 一队单位全部阵亡或双方策略都崩溃时，比赛提前结束。
- 双方使用同一套绝对坐标。`my_id` 和单位的 `player_id` 标识所属队伍。

### 4.2 地块与移动机制

| 地块值 | 作用 |
|---|---|
| EMPTY | 空地 |
| WALL | 阻挡移动和子弹 |
| PLATFORM | 可以站立，也可以穿越；是否阻挡下落与 jump_down 有关 |
| LADDER | 允许竖直移动；单位中心到脚底中点的线段与地块相交时视为在梯子上 |
| JUMP_PAD | 单位接触后触发跳跃；该跳跃不能通过动作取消 |

单位没有加速度。水平与竖直移动分别处理，先水平、后竖直。

- `velocity` 指定水平速度，数值限制在最大水平速度范围内；墙或其他单位可以阻挡移动。
- 竖直状态分为下落与跳跃，两者均按对应速度移动。
- 下落被地块或其他单位阻挡时进入可跳跃状态。在梯子上，下落状态也会转为可跳跃状态。
- `jump = true` 表示开始或继续跳跃；`jump = false` 会取消允许取消的跳跃。
- 跳跃持续时间结束或向上移动被墙、单位阻挡时，转为下落。
- 未设置 `jump_down` 时，平台和梯子也能阻挡下落；设置后只有墙地块阻挡下落。
- `jump_down = true` 也用于沿梯子向下移动和穿过平台。

单位尺寸、水平速度上限、下落速度、跳跃速度及持续时间均在 `properties` 中提供。单位 `position` 是底边中点。

### 4.3 单位状态

每个角色独立记录生命值、位置、尺寸、跳跃状态、所持武器和地雷数量。`weapon = null` 表示当前空手。观察消息中的 `units` 包含双方当前存活角色，阵亡角色从列表中移除。

双方收到的世界坐标相同，己方身份由 `my_id` 指定；单位 `player_id` 表示它属于哪一队。

<a id="chapter-5"></a>

## 5. 物品、武器与地雷

### 5.1 物品

单位与物品箱相交时可以拾取或交换物品：

- `HealthPack`：仅在未满生命值时拾取，立即增加生命值，不超过上限。
- `Weapon`：空手时拾取；已有武器时可以通过 `swap_weapon` 与箱中武器交换。
- `Mine`：增加携带地雷数量，之后可通过 `plant_mine` 放置。

### 5.2 武器与射击

武器拥有弹匣容量、射击间隔、装弹时间、散布范围、后坐、散布收敛速度、子弹参数，以及可选的爆炸参数。

下表是当前默认配置。实际参数通过开局 `properties.weapon_params` 提供。

| 武器类型 | 弹匣容量 | 射击间隔（秒） | 装弹（秒） | 子弹速度 | 子弹边长 | 子弹伤害 | 爆炸半径 / 伤害 |
|---|---:|---:|---:|---:|---:|---:|---|
| PISTOL | 8 | 0.4 | 1 | 50 | 0.2 | 20 | 无 |
| ASSAULT_RIFLE | 20 | 0.1 | 1 | 50 | 0.2 | 5 | 无 |
| ROCKET_LAUNCHER | 1 | 1 | 1 | 20 | 0.4 | 30 | 3 / 50 |

- `aim` 控制瞄准方向，`shoot` 控制开火，`reload` 控制装弹。
- 武器具有当前散布值。子弹角度在瞄准方向上增加散布范围内的均匀随机偏移；开火会增加后坐对应的散布，散布随后按收敛速度减小。
- 改变瞄准方向会按角度变化增加散布；武器第一次拾取时没有上次瞄准角度。
- 子弹为正方形，从射击单位的中心产生。子弹不能直接命中开枪者，可以命中其他单位、墙或地雷。
- 子弹命中后消失；命中单位造成伤害，命中地雷引发爆炸。
- 含爆炸参数的子弹命中时产生爆炸，影响与爆炸正方形相交的所有单位，并引爆相交的地雷。爆炸正方形边长为半径的两倍。
- 拾取武器后首先装弹，弹匣用尽时自动装弹。武器没有独立的备用弹药数量上限。

### 5.3 地雷

单位在地面上且携带地雷时可放置地雷。地雷经历准备、等待触发、触发倒计时和爆炸状态。准备期间不会自行触发；准备完成后，单位进入触发距离会启动倒计时。爆炸影响范围内的所有单位，也能引爆其他地雷。

地雷尺寸、准备时间、触发半径、倒计时和爆炸参数均由 `properties` 提供。

| 状态值 | 含义 |
|---|---|
| `PREPARING` | 放置后正在准备 |
| `IDLE` | 准备完成，等待触发 |
| `TRIGGERED` | 已触发，等待爆炸倒计时结束 |
| `EXPLODED` | 已爆炸 |

### 5.4 视觉表现与规则数据

回放使用东京 1987 年的复古像素街机场景。背景建筑、招牌与视觉特效用于展示；可碰撞地形、单位位置及可交互物品由比赛数据定义。程序通过状态消息获取游戏信息，不通过读取画面控制角色。

当前可拾取物品类别为医疗包、武器和地雷。没有单独的备用弹药箱拾取机制。

<a id="chapter-6"></a>

## 6. 策略控制与通信协议

### 6.1 通信约定

- 每条消息是一个 JSON 对象，占一行，以换行结束。
- 策略从标准输入读取消息，通过标准输出回复；输出后必须立即 flush。
- 标准输出只用于协议消息，日志写入标准错误。
- 下方代码示例为了阅读使用缩进；实际通信时必须输出为单行。
- 坐标及枚举含义见第 7 章；布尔值使用 JSON 的 `true` / `false`，空值使用 `null`。

### 6.2 初始化：init

每个策略进程在一局开始时收到初始化对象。

| 字段 | 类型 | 含义 |
|---|---|---|
| `type` | 字符串 | 固定为 `init` |
| `my_id` | 整数 | 己方玩家 ID |
| `stage` | 字符串 | `round1`、`round2` 或 `finals` |
| `seed` | 整数 | 本场种子 |
| `time_limit_ms` | 数值 | 每 tick 回复时间上限，毫秒 |
| `total_time_ms` | 数值 | 整局 CPU 总预算，单位毫秒 |
| `time_budget_type` | 字符串 | cpu_user_system：用户态与内核态 CPU 时间之和 |
| `memory_limit_bytes` | 数值 | 进程内存上限，默认 268435456 字节 |
| `properties` | 对象 | 世界与武器参数，详见附录 A |
| `level` | 对象 | 含 `tiles`，表示地图地块列数组 |

`properties` 和 `level` 在一局中不变，只在 init 发送一次。收到并准备完成后回复：

```json
{"ready": true}
```

### 6.3 状态消息：turn

每 tick 收到以下消息结构：

| 路径 | 类型 | 含义 |
|---|---|---|
| `type` | 字符串 | 固定为 `turn` |
| `tick` | 整数 | 这条消息对应的 tick |
| `player_view.my_id` | 整数 | 己方玩家 ID |
| `player_view.game.current_tick` | 整数 | 当前世界 tick |
| `player_view.game.players` | Player 数组 | 两队得分 |
| `player_view.game.units` | Unit 数组 | 双方存活单位 |
| `player_view.game.bullets` | Bullet 数组 | 当前飞行子弹 |
| `player_view.game.mines` | Mine 数组 | 当前地雷 |
| `player_view.game.loot_boxes` | LootBox 数组 | 当前物品箱 |

`game` 不重复包含 `properties` 和 `level`。起步模板会将初始化时保存的这两个对象附回 `game.properties` 和 `game.level`，供模板接口使用。

### 6.4 动作回复

回复包含 `tick` 和 `actions`。`tick` 必须与收到的消息一致；`actions` 的键为己方单位 ID 的字符串形式，值为该单位的动作对象。

下面是假设当前 tick 为 130、己方存活单位 ID 为 3 和 5 的格式示例。它只演示双角色回复结构，不代表固定 ID 或推荐动作。

```json
{
  "tick": 130,
  "actions": {
    "3": {
      "velocity": 0.0,
      "jump": false,
      "jump_down": false,
      "aim": {"x": 0.0, "y": 0.0},
      "shoot": false,
      "reload": false,
      "swap_weapon": false,
      "plant_mine": false
    },
    "5": {
      "velocity": 0.0,
      "jump": false,
      "jump_down": false,
      "aim": {"x": 0.0, "y": 0.0},
      "shoot": false,
      "reload": false,
      "swap_weapon": false,
      "plant_mine": false
    }
  }
}
```

### 6.5 动作字段

| 字段 | 类型 | 含义 | 省略时的值 |
|---|---|---|---|
| `velocity` | 数值 | 水平移动速度 | 0 |
| `jump` | 布尔 | 开始/继续跳跃，或沿梯子向上 | false |
| `jump_down` | 布尔 | 穿平台下落，或沿梯子向下 | false |
| `aim` | Vec2 | 瞄准方向向量 | (0, 0) |
| `shoot` | 布尔 | 射击动作 | false |
| `reload` | 布尔 | 装弹动作 | false |
| `swap_weapon` | 布尔 | 与相交物品箱中的武器交换 | false |
| `plant_mine` | 布尔 | 放置携带的地雷 | false |

`actions` 只能包含己方单位 ID。包含任何非己方单位 ID 时，整条回复视为协议错误，本 tick 己方全队使用默认动作；后续合法回复可恢复控制。没有提供动作的己方单位使用默认动作。默认动作不意味着暂停物理模拟，已有子弹、下落和地雷计时等仍继续。

### 6.6 结束：end

```json
{"type": "end", "scores": [1100, 85]}
```

`scores` 按玩家 1、玩家 2 的顺序排列。收到 end 后结束进程，无需回复。

### 6.7 起步模板接口

开发包中的 `entry/bot.py` 已包含单文件消息收发和动作类型定义。策略入口是 `MyStrategy.get_action(unit, game, debug)`，每 tick 对每个己方角色调用一次，返回 `UnitAction`。

`unit` 是当前待控制单位，`game` 是当前世界状态，`debug.log` 将日志写到标准错误。模板不提供调试绘图。参赛程序也可以自行实现通信，只要符合本章协议。

<a id="chapter-7"></a>

## 7. 数据结构

### 7.1 基础类型与枚举

`Vec2` 为 `{"x": 数值, "y": 数值}`。长度使用地图地块为单位，运动速度使用地块/秒，游戏内部时间字段通常使用秒；名称以 `_ms` 结尾的预算字段使用毫秒。

| 枚举 | 值 |
|---|---|
| 地块 | EMPTY、WALL、PLATFORM、LADDER、JUMP_PAD |
| 武器 | PISTOL、ASSAULT_RIFLE、ROCKET_LAUNCHER |
| 地雷状态 | PREPARING、IDLE、TRIGGERED、EXPLODED |
| 物品类型 | HealthPack、Weapon、Mine |

`Level.tiles` 按列存储；外层长度是地图宽度，每列长度是高度。`Player` 含 `id` 与 `score`。

### 7.2 Unit：角色

| 字段 | 类型 | 含义 |
|---|---|---|
| `player_id`、`id` | 整数 | 所属玩家 ID、单位 ID |
| `health` | 整数 | 当前生命值 |
| `position` | Vec2 | 底边中点位置 |
| `size` | Vec2 | 宽与高 |
| `jump_state` | JumpState | 跳跃状态 |
| `walked_right` | 布尔 | 最后水平移动方向是否向右 |
| `stand` | 布尔 | 是否处于水平静止状态 |
| `on_ground`、`on_ladder` | 布尔 | 地面/梯子状态 |
| `mines` | 整数 | 携带地雷数量 |
| `weapon` | Weapon 或 null | 当前武器；null 表示空手 |

`JumpState` 含 `can_jump`（能否开始/继续跳跃）、`speed`（上升速度）、`max_time`（剩余跳跃时间）和 `can_cancel`（能否通过动作取消）。

### 7.3 Weapon：武器状态

| 字段 | 类型 | 含义 |
|---|---|---|
| `typ` | 武器枚举 | 武器类型 |
| `params` | WeaponParams | 该武器的参数 |
| `magazine` | 整数 | 当前弹匣余量 |
| `was_shooting` | 布尔 | 射击状态标记 |
| `spread` | 数值 | 当前散布，弧度 |
| `fire_timer` | 数值或 null | 距离可再次射击的秒数；null 表示当前无计时等待 |
| `last_angle` | 数值或 null | 上次瞄准角度，弧度；无历史角度时为 null |
| `last_fire_tick` | 整数或 null | 上次开火的 tick；尚未开火时可为 null |

`WeaponParams` 包含 `magazine_size`、`fire_rate`、`reload_time`、`min_spread`、`max_spread`、`recoil`、`aim_speed`、`bullet` 与 `explosion`。

其中 `bullet` 含 `speed`、`size`、`damage`；`explosion` 含 `radius`、`damage`，无爆炸时为 null。默认数值见附录 A。

### 7.4 Bullet：子弹

| 字段 | 类型 | 含义 |
|---|---|---|
| `weapon_type` | 武器枚举 | 来源武器 |
| `unit_id`、`player_id` | 整数 | 发射单位和所属玩家 |
| `position` | Vec2 | 子弹中心 |
| `velocity` | Vec2 | 速度向量 |
| `damage` | 整数 | 直接命中伤害 |
| `size` | 数值 | 正方形边长 |
| `explosion_params` | 对象或 null | 爆炸半径与伤害，无爆炸则为 null |

### 7.5 Mine：地雷

| 字段 | 类型 | 含义 |
|---|---|---|
| `player_id` | 整数 | 所属玩家 |
| `position`、`size` | Vec2 | 底边中点位置、宽与高 |
| `state` | 地雷状态枚举 | 当前状态 |
| `timer` | 数值或 null | 当前状态剩余秒数，无倒计时时为 null |
| `trigger_radius` | 数值 | 触发距离 |
| `explosion_params` | 对象 | 爆炸 `radius` 与 `damage` |

### 7.6 LootBox：物品箱

`position` 是底边中点，`size` 为宽与高，`item` 表示内容：

```json
{"type": "HealthPack", "health": 50}
```

```json
{"type": "Weapon", "weapon_type": "PISTOL"}
```

```json
{"type": "Mine"}
```

以上三段分别为三类 `item` 的例子；它们不是完整的 LootBox 消息。

<a id="chapter-8"></a>


## 附录 A：默认参数表

### A.1 世界、角色与物品

以下字段位于 `init.properties`。`team_size` 随赛段为 1 或 2；其余为当前默认数值。时间参数单位为秒，速度参数单位为地块/秒，尺寸单位为地块。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `max_tick_count` | `3600` | 单局 tick 上限 |
| `team_size` | `1 / 2` | 每队角色数（由赛段决定） |
| `ticks_per_second` | `60.0` | 每秒 tick 数 |
| `updates_per_tick` | `100` | 每 tick 物理更新次数 |
| `loot_box_size` | `{"x": 0.5, "y": 0.5}` | 物品箱宽、高 |
| `unit_size` | `{"x": 0.9, "y": 1.8}` | 角色宽、高 |
| `unit_max_horizontal_speed` | `10.0` | 最大水平速度 |
| `unit_fall_speed` | `10.0` | 下落速度 |
| `unit_jump_time` | `0.55` | 普通跳跃持续时间 |
| `unit_jump_speed` | `10.0` | 普通跳跃速度 |
| `jump_pad_jump_time` | `0.525` | 跳板跳跃持续时间 |
| `jump_pad_jump_speed` | `20.0` | 跳板跳跃速度 |
| `unit_max_health` | `100` | 生命值上限 |
| `health_pack_health` | `50` | 医疗包回复量 |
| `mine_size` | `{"x": 0.5, "y": 0.5}` | 地雷宽、高 |
| `mine_explosion_params` | `{"radius": 3.0, "damage": 50}` | 地雷爆炸半径、伤害 |
| `mine_prepare_time` | `1.0` | 地雷准备时间 |
| `mine_trigger_time` | `0.5` | 触发后倒计时 |
| `mine_trigger_radius` | `1.0` | 地雷触发距离 |
| `kill_score` | `1000` | 角色死亡时给对手的分数 |

### A.2 武器参数

以下字段位于 `properties.weapon_params[武器类型]`。角度和散布以弧度计，收敛速度以弧度/秒计。

| 参数 | PISTOL | ASSAULT_RIFLE | ROCKET_LAUNCHER |
|---|---:|---:|---:|
| `magazine_size` | 8 | 20 | 1 |
| `fire_rate` | 0.4 | 0.1 | 1.0 |
| `reload_time` | 1.0 | 1.0 | 1.0 |
| `min_spread` | 0.05 | 0.1 | 0.1 |
| `max_spread` | 0.5 | 0.5 | 0.5 |
| `recoil` | 0.5 | 0.2 | 1.0 |
| `aim_speed` | 1.0 | 1.9 | 1.0 |
| `bullet.speed` | 50.0 | 50.0 | 20.0 |
| `bullet.size` | 0.2 | 0.2 | 0.4 |
| `bullet.damage` | 20 | 5 | 30 |
| `explosion` | null | null | radius = 3.0，damage = 50 |

<a id="appendix-b"></a>
