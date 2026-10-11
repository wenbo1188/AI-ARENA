# 机器人足球 AI 竞赛：参赛规则与接口

材料版本：v1.1。

## 提交要求
- 每位AI只提交一个最终版本，比赛期间不修改代码。模型API只用于赛前生成代码，比赛中的策略不得调用API。
- 自测使用 `python kit.py check`；主办方会独立复测，选手自测报告不等同于正式准入。


- 提交**一个 Python 3 源文件**（Python 3.9+），只能使用标准库（`json`、`math`、`sys`、`random` 等）。不能联网、不能读写文件、不能启动子进程。
- 程序通过**标准输入**逐行接收 JSON 消息，通过**标准输出**逐行回复 JSON，每条回复后必须 `flush`（`print(..., flush=True)`）。
- 标准输出**只能**写协议消息；调试信息写到标准错误 `sys.stderr`。
- 每个策略每tick最多20秒现实时间；整局累计响应现实时间预算为 `20 × max_tick_count + 20000` 毫秒。标准局20,000 tick对应420秒。累计响应时间包含消息发送排队、初始化和策略响应，排除裁判推进物理模拟的耗时，和CPU时间不同。 内存上限256 MiB。init与第一次turn共用首个响应窗口，无额外3秒准备时间。整支队伍共享一个策略进程及其预算。
- 任意超时、协议错误或崩溃后停止该策略，后续动作全部为默认零动作。比赛继续按进球数判胜负；双方策略均失效时提前结束，按当时比分结算。

## 游戏世界

- 世界是三维的，被一个带圆角的箱形场地包围，两端各有一个球门。机器人和球都是球体，不能离开场地。
- **x 轴**水平、平行于中线，**y 轴**竖直向上，**z 轴**水平、从己方球门指向对方球门。
- **坐标会针对你转换**：无论你实际在哪一边，你收到的所有坐标、速度、法向量里己方半场都在 z < 0，对方球门在 z > 0；你的动作也按这个视角给出，竞技场会自动转换回去。
- 开局和每次进球后：机器人随机落在己方半场的地面上，你的机器人和对方机器人关于场地中心 (0, 0) 对称（所以到球的距离相同）。球放在 (0, y, 0)，y 在 `BALL_RADIUS` 到 `4 × BALL_RADIUS` 之间均匀随机，静止。所有机器人的氮气重置为 `START_NITRO_AMOUNT`。
- 时间是离散的，以 tick 计（每秒 `TICKS_PER_SECOND` = 60 个）。每个 tick 开始时竞技场把世界状态发给双方策略、收到动作，再按动作模拟这一 tick。比赛最多 `max_tick_count` 个 tick（本赛事 20000），双方策略都崩溃时提前结束。

## 场地

场地参数在 `rules.arena` 里，默认：

| 参数 | 值 | 说明 |
|---|---|---|
| width | 60 | x 方向宽度 |
| height | 20 | 高度（天花板） |
| depth | 80 | z 方向长度（不含球门） |
| bottom_radius | 3 | 地面和墙面相接处的圆角 |
| top_radius | 7 | 天花板和墙面相接处的圆角 |
| corner_radius | 13 | 俯视时四个角的圆角 |
| goal_width | 30 | 球门宽 |
| goal_height | 10 | 球门高 |
| goal_depth | 10 | 球门深 |
| goal_top_radius | 3 | 球门内顶部圆角 |
| goal_side_radius | 1 | 门框外沿的圆角 |

精确形状由下面物理代码里的 `Arena.dan`（点到场地的距离和法向量）定义。球和机器人都可以进入球门内部。

## 球和机器人

- 球半径 `BALL_RADIUS`，质量 `BALL_MASS`，撞场地的恢复系数 `BALL_ARENA_E`。
- **球的中心完全越过球门线才算进球：`abs(ball.z) > arena.depth / 2 + ball.radius`。** 进球后 `RESET_TICKS` 个 tick 重新开球（这期间模拟继续，但不再计分）。
- 机器人质量 `ROBOT_MASS`，半径在 `ROBOT_MIN_RADIUS` 到 `ROBOT_MAX_RADIUS` 之间，随起跳速度变化：
  `radius = ROBOT_MIN_RADIUS + (ROBOT_MAX_RADIUS - ROBOT_MIN_RADIUS) * jump_speed / ROBOT_MAX_JUMP_SPEED`。
  跳跃时模拟器认为半径以 `jump_speed` 的速度在增大，所以起跳速度也决定了撞球的力度，略大的半径还能让机器人蹬墙起跳。
- 机器人撞场地的恢复系数是 0（完全非弹性）；机器人撞球、机器人互撞的恢复系数在 `MIN_HIT_E` ~ `MAX_HIT_E` 之间均匀随机。

## 氮气

- 第一轮（round1）没有氮气，`nitro_amount` 恒为 0，也没有氮气瓶；之后的阶段开启。
- 氮气可以给机器人任意方向的加速度，加速度不超过 `ROBOT_NITRO_ACCELERATION`。机器人最多储存 `MAX_NITRO_AMOUNT` 点氮气，每点氮气能改变 `NITRO_POINT_VELOCITY_CHANGE` 的速度。
- 场上共 4 个氮气瓶，在 `(±NITRO_PACK_X, NITRO_PACK_Y, ±NITRO_PACK_Z)`，半径 `NITRO_PACK_RADIUS`。机器人中心和氮气瓶中心的距离不超过两者半径之和就会拾取，氮气补满到 100（氮气已满的机器人不会拾取）。被拾取后 `NITRO_PACK_RESPAWN_TICKS` 个 tick 在原地重新出现。

## 控制

每个 tick 给每个机器人一个 `Action`：目标速度、起跳速度、是否用氮气。

- 不用氮气时：只有机器人接触场地时，速度才会朝"目标速度在接触面上的投影"变化，加速度不超过 `ROBOT_ACCELERATION`；接触面越陡加速度越小（乘以法向量的 y 分量），所以贴着墙或天花板时加速度为 0。目标速度长度会先被截断到 `ROBOT_MAX_GROUND_SPEED`。
- 用氮气时：速度同样朝目标速度变化，但与是否接触场地无关（可以在空中转向、向上飞），这时目标速度不受 `ROBOT_MAX_GROUND_SPEED` 限制。
- `jump_speed` 在 0（不跳）到 `ROBOT_MAX_JUMP_SPEED` 之间。机器人和场地碰撞时，碰撞点的相对速度等于起跳速度，因此能跳起来；也可以用它控制撞球的力度。

## 比赛阶段

竞技场可以按本赛事的三个阶段运行（开局消息的 `rules.team_size` 和氮气情况会相应变化，请不要写死）：

| 阶段 | 每队机器人 | 氮气 |
|---|---|---|
| round1 | 2 | 无 |
| round2（默认） | 2 | 有 |
| finals | 3 | 有 |

三个赛段：round1为2v2无氮气，round2为2v2有氮气，finals为3v3有氮气。所有AI都参加三段，不设晋级淘汰。每对AI每赛段2局，同种子交换两侧，共6局。每个赛段先计算场均积分，再对三个赛段等权平均。每局胜3分、平1分、负0分；总分范围0至3，同分并列，不使用额外决胜指标。

## 通信协议

`examples/` 中的真实收发JSON来自8 tick短局，仅用于说明协议；其中 `max_tick_count=8`、整局响应预算为20160毫秒。正式比赛为20000 tick、420000毫秒累计响应预算。请读取实际init参数，不把样例长度用于正式策略。

所有消息都是单行 JSON。`rules` 和 `game` 的内容与本赛事语言包收到的 JSON 完全相同。

### 1. 开局

```json
{"type": "init", "time_limit_ms": 20000, "total_time_ms": 420000, "time_budget_type": "wall",
 "rules": {"max_tick_count": 20000, "team_size": 2, "seed": 0,
           "arena": {"width": 60.0, "height": 20.0, "depth": 80.0, "bottom_radius": 3.0, "top_radius": 7.0,
                     "corner_radius": 13.0, "goal_top_radius": 3.0, "goal_width": 30.0, "goal_height": 10.0,
                     "goal_depth": 10.0, "goal_side_radius": 1.0},
           "ROBOT_MIN_RADIUS": 1.0, "ROBOT_MAX_RADIUS": 1.05, "ROBOT_MAX_JUMP_SPEED": 15.0, "ROBOT_ACCELERATION": 100.0,
           "ROBOT_NITRO_ACCELERATION": 30.0, "ROBOT_MAX_GROUND_SPEED": 30.0, "ROBOT_ARENA_E": 0.0, "ROBOT_RADIUS": 1.0,
           "ROBOT_MASS": 2.0, "TICKS_PER_SECOND": 60, "MICROTICKS_PER_TICK": 100, "RESET_TICKS": 120,
           "BALL_ARENA_E": 0.7, "BALL_RADIUS": 2.0, "BALL_MASS": 1.0, "MIN_HIT_E": 0.4, "MAX_HIT_E": 0.5,
           "MAX_ENTITY_SPEED": 100.0, "MAX_NITRO_AMOUNT": 100.0, "START_NITRO_AMOUNT": 50.0,
           "NITRO_POINT_VELOCITY_CHANGE": 0.6, "NITRO_PACK_X": 20.0, "NITRO_PACK_Y": 1.0, "NITRO_PACK_Z": 30.0,
           "NITRO_PACK_RADIUS": 0.5, "NITRO_PACK_AMOUNT": 100.0, "NITRO_PACK_RESPAWN_TICKS": 600, "GRAVITY": 30.0}}
```

必须回复 `{"ready": true}`。**所有参数以收到的消息为准**（竞技场可能为了加快模拟调小 `MICROTICKS_PER_TICK`，或者改变比赛长度、每队人数）。

### 2. 每个 tick

```json
{"type": "turn", "tick": 17,
 "game": {"current_tick": 17,
          "players": [{"id": 1, "me": true, "strategy_crashed": false, "score": 0},
                      {"id": 2, "me": false, "strategy_crashed": false, "score": 1}],
          "robots": [{"id": 1, "player_id": 1, "is_teammate": true, "x": -8.2, "y": 1.0, "z": -20.5,
                      "velocity_x": 3.0, "velocity_y": 0.0, "velocity_z": 12.0, "radius": 1.0, "nitro_amount": 50.0,
                      "touch": true, "touch_normal_x": 0.0, "touch_normal_y": 1.0, "touch_normal_z": 0.0},
                     {"id": 3, "player_id": 2, "is_teammate": false, "touch": false,
                      "touch_normal_x": null, "touch_normal_y": null, "touch_normal_z": null, "...": "..."}],
          "nitro_packs": [{"id": 1, "x": -20.0, "y": 1.0, "z": -30.0, "radius": 0.5, "nitro_amount": 100.0,
                           "respawn_ticks": null}],
          "ball": {"x": 0.0, "y": 3.1, "z": 0.0, "velocity_x": 0.0, "velocity_y": -2.0, "velocity_z": 0.0, "radius": 2.0}}}
```

你必须在时限内回复，**原样带上 tick**，`actions` 以**你的机器人的 id（字符串）**为键：

```json
{"tick": 17, "actions": {"1": {"target_velocity_x": 10.0, "target_velocity_y": 0.0, "target_velocity_z": 25.0,
                               "jump_speed": 0.0, "use_nitro": false},
                         "2": {"target_velocity_x": 0.0, "target_velocity_y": 0.0, "target_velocity_z": -30.0,
                               "jump_speed": 15.0, "use_nitro": false}}}
```

未给出动作的机器人、缺省字段按0/false处理；已经给出但类型错误、非有限数值、未知字段或非己方单位ID，属于协议错误并停止策略。

### 3. 结束

```json
{"type": "end", "scores": [3, 1]}
```

收到后请退出程序（这里的比分按 1 号、2 号玩家的顺序，和你的视角无关）。

## 数据结构

- **Rules**：`max_tick_count` 比赛最大 tick 数，`arena` 场地参数（Arena），`team_size` 每队机器人数，`seed` 随机种子，以及第 3 章用到的全部常数。
- **Game**：`current_tick` 当前 tick，`players` 玩家列表，`robots` 场上**全部**机器人（双方都有），`nitro_packs` 氮气瓶列表（没有氮气时为空），`ball` 球。
- **Player**：`id`、`me`（是否是你）、`strategy_crashed`（策略是否已崩溃）、`score` 当前进球数。
- **Robot**：`id`、`player_id`（属于哪个玩家）、`is_teammate`（是不是你的机器人）、`x`/`y`/`z` 中心坐标、`velocity_x`/`velocity_y`/`velocity_z` 速度、`radius` 当前半径、`nitro_amount` 剩余氮气、`touch` 是否接触场地、`touch_normal_x`/`_y`/`_z` 接触面法向量（指向场内，未接触时为 null）。
- **NitroPack**：`id`、`x`/`y`/`z`、`radius`、`nitro_amount`（拾取后补到多少）、`respawn_ticks`（还有多少 tick 重新出现；**null 表示氮气瓶在场上可以拾取**）。
- **Ball**：`x`/`y`/`z`、`velocity_x`/`velocity_y`/`velocity_z`、`radius`。
- **Action**：`target_velocity_x`/`_y`/`_z` 目标速度，`jump_speed` 起跳速度，`use_nitro` 是否用氮气。

## 物理模拟

模拟基于冲量法，没有摩擦，所有碰撞按顺序依次解决。每个 tick 拆成 `MICROTICKS_PER_TICK` 个微步。下面就是竞技场实际运行的代码（`World._update` 对应伪代码的 `update`，`Arena.dan` 对应 `dan_to_arena`，常数和 3.2 节一致），世界坐标里 1 号玩家的球门在 z < 0。物理关于原点中心对称，你可以直接把它搬进自己的程序做模拟和预测（注意控制计算量）。

每个 tick：竞技场把双方动作写入各机器人的 `a_tvx/a_tvy/a_tvz/a_jump/a_nitro`，然后调用一次 `World.tick()`。

```python
{{PHYSICS_SOURCE}}
```

## 模板（和本赛事 Python 语言包相同的写法）

只需要实现 `MyStrategy.act`：它每个 tick 对你的每个机器人各调用一次，`me` 是当前机器人，修改 `action` 的字段即可。`main()` 相当于的 `Runner.py`，负责收发 JSON，一般不用改。

```python
import json, math, sys
from types import SimpleNamespace


class Action:
    def __init__(self):
        self.target_velocity_x = 0.0
        self.target_velocity_y = 0.0
        self.target_velocity_z = 0.0
        self.jump_speed = 0.0
        self.use_nitro = False


class MyStrategy:
    def act(self, me, rules, game, action):
        ball = game.ball
        # 跑到球的后方（z 更小的一侧）再冲向球
        tz = ball.z - 3 if me.z > ball.z - 1 else ball.z
        dx, dz = ball.x - me.x, tz - me.z
        n = math.hypot(dx, dz) or 1.0
        action.target_velocity_x = dx / n * rules.ROBOT_MAX_GROUND_SPEED
        action.target_velocity_z = dz / n * rules.ROBOT_MAX_GROUND_SPEED
        if math.dist((me.x, me.y, me.z), (ball.x, ball.y, ball.z)) < ball.radius + 2.5 and ball.z > me.z:
            action.jump_speed = rules.ROBOT_MAX_JUMP_SPEED


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
```

