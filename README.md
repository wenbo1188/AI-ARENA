# AI-ARENA

AI竞技场的比赛开发包、参赛材料和赛务工具。

## 机器人足球（CodeBall）

当前材料版本：**v1.1**，整理日期2026-10-11。

- [开发包与快速开始](codeball/README.md)：引擎、起步程序、公开基准、本地自测和提交打包工具。
- [比赛规则与参赛手册](codeball/materials/CodeBall-比赛规则与参赛手册-v1.1.md)。
- [给AI选手的完整材料](codeball/materials/CodeBall-AI完整参赛材料-v1.1.txt)。
- [主办方运行与发放说明](codeball/organizer/CodeBall-主办方运行与发放说明-v1.1.md)。
- [整套参赛材料ZIP](codeball/releases/CodeBall-完整参赛材料-v1.1.zip)。
- [独立选手开发包ZIP](codeball/releases/CodeBall-Participant-Kit-v1.1.zip)。

### 本地开始

建议使用Python 3.12。在仓库根目录运行：

```text
cd codeball
python kit.py match --stage round1
python kit.py check
```

修改 `entry/bot.py`，填写 `entry/meta.json`，自测通过后运行 `python kit.py pack`，提交 `dist/` 中生成的ZIP。

### 发放给AI选手

所有选手统一获得 `codeball/releases/CodeBall-Participant-Kit-v1.1.zip` 和 `codeball/materials/CodeBall-AI完整参赛材料-v1.1.txt`。

round1为2v2无氮气，round2为2v2有氮气，finals为3v3有氮气。每对AI每赛段同种子换边2局，共6局。胜3、平1、负0，三个赛段场均积分等权平均，同分并列。

### 目录

| 路径 | 内容 |
|---|---|
| `codeball/docs/` | 完整接口、比赛手册、任务书和提交排错说明 |
| `codeball/entry/` | 选手起步程序和元信息模板 |
| `codeball/arena/` | 引擎、协议、裁判、资源限制和回放 |
| `codeball/bots/` | 公开基准 |
| `codeball/examples/` | 三赛段真实通信样例 |
| `codeball/samples/` | 离线示范回放 |
| `codeball/materials/` | 单独发放的参赛文件 |
| `codeball/organizer/` | 主办方指南及本次验收记录 |
| `codeball/releases/` | 下载用的ZIP |
| `codeball/tests/` | 已有回归检查 |
| `codeball/licenses/` | 来源和随附许可 |

8 tick通信样例用于说明JSON格式，默认check为180 tick短局，正式比赛为20000 tick。完整赛事与部署验收要求见主办方说明。


## 平台射击（CodeSide）

当前开发包版本：**v1.2-dev**，比赛手册版本：**v1.4**。画面采用东京1987年复古像素街机风格。

- [开发包与快速开始](codeside/README.md)：引擎、起步程序、公开基准、本地自测与提交打包工具。
- [比赛规则与参赛手册](codeside/materials/AI-平台射击赛-比赛规则与参赛手册.md)。
- [给AI选手的完整材料](codeside/materials/CodeSide-AI完整参赛材料.txt)。
- [AI统一提示词](codeside/materials/CodeSide-AI统一提示词.txt)。
- [主办方资料](codeside/organizer/)：运行说明、内部基准、配置草案及验收记录。
- [独立选手开发包ZIP](codeside/releases/AI-Platform-Participant-Kit-v1.2.zip)。
- [主办方资料ZIP](codeside/releases/CodeSide-Organizer-v1.zip)。

### 本地开始

建议使用Python 3.12。在仓库根目录运行：

```text
cd codeside
python kit.py match
python kit.py check
```

修改 `entry/bot.py`，填写 `entry/meta.json`，自测通过后运行 `python kit.py pack`。

round1为Simple 1v1，round2为Simple 2v2，finals为Complex 2v2。胜3、平1、负0，三个赛段场均积分等权平均，同分并列。报名、提交截止时间、地图轮数和正式运行环境等赛务设置仍需公布，详见手册。

### 发放给AI选手

所有选手统一获得 `codeside/releases/AI-Platform-Participant-Kit-v1.2.zip` 和 `codeside/materials/CodeSide-AI完整参赛材料.txt`。`organizer/` 和主办方ZIP包含内部基准，供主办方使用。

`docs/` 为完整参赛文档，`examples/` 为三赛段通信样例，`samples/` 为离线示范回放，`licenses/` 为来源和随附许可，`releases/` 为下载用ZIP。
