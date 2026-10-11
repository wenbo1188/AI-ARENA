# 平台射击 AI 竞赛开发包 v1.2

这是可以立即开始写机器人、试跑和观看回放的开发包。正式赛事的报名、截止时间、地图轮数和隔离环境尚待主办方发布；本包不是已定稿的赛事公告。每位选手获得相同版本和相同基准程序。

按章节了解整场比赛，请先阅读 [比赛规则与参赛手册](docs/05-比赛规则与参赛手册.md)。该手册独立介绍三个赛段、地图、游戏规则、接口和提交流程。

## 五分钟开始

1. 解压整个压缩包。安装 Python，建议使用 Python 3.12；本包已在 Windows / Python 3.12.6 实测。程序仅用标准库，无需 pip 安装。其他 Python 版本未逐一验证。
2. 用编辑器打开 `entry/bot.py`，修改 `MyStrategy.get_action`。该文件是一个可直接运行的起步策略。保留它底部的 JSON 收发部分。
3. 在解压目录打开终端，运行下列命令。Windows 如只有 `py` 命令，将 `python` 替换为 `py -3`；Linux 可用 `python3`。

```sh
python kit.py match
```

默认在 Simple 地图进行 1v1，公开练习种子 12，最多 3600 tick，对手是 quickstart。打开 `results/round1-12-left.html` 查看东京 1987 像素街机回放，无需服务器或联网。JSON 回放与 HTML 一起保存。

```sh
python kit.py match --stage round2 --seed 21
python kit.py match --stage finals --seed 34
python kit.py match --stage round1 --seat right --seed 12
python kit.py check
```

`check` 先检查 init / turn 回复、单位 ID 和动作字段类型，再跑三个赛段各左右两侧，共六场短局，每场上限 180 tick。`results/check.json` 包含成绩、超时和错误。它是基本兼容性检查，不是胜率测试或正式准入证书。

```sh
python kit.py check --ticks 1200
python kit.py check --ticks 3600
```

后两条用于更长的检查。默认即采用比赛时间限制：每 tick 现实时间上限 1000 ms；每个策略进程的整局 CPU 时间预算为 20 × max_tick_count + 20000 ms。默认 3600 tick 对应 92000 ms（92 秒），提前结束不缩减预算。CPU 时间包括程序启动、初始化、JSON 收发处理和全部策略线程的用户态与内核态计算，不计睡眠等待或裁判进程耗时。 init 与首个 turn 共用首次 1000 ms 响应窗口，没有额外的初始化宽限；后续每个 turn 单独计现实时间。2v2 的两个己方角色由同一个进程控制，共享该进程的预算。 内存上限 256 MiB。Windows 已实测，Linux 实现尚未实机验证，其他系统暂不支持。

4. 填写 `entry/meta.json` 的选手名、模型和版本（人工写作填 human）。修改代码后重新自测。
5. 打包交付：

```sh
python kit.py pack
```

生成 `dist/选手名-代码摘要.zip`，内含 `bot.py`、元信息、自测报告和 SHA-256。工具只接受与最近通过自测的代码相同的版本，自测每场上限需至少 180 tick。已有同名包不会被覆盖；只改元信息时先将旧提交包移到别处。

把提交包交给主办方指定入口。开发阶段也可以只提交 `bot.py`，正式采用何种收件方式由主办方确认。不要提交整个开发包、回放或 API 密钥。

## 包里有什么

| 路径 | 用途 |
|---|---|
| `docs/01-参赛规则与接口.md` | 游戏规则、协议和起步模板 |
| `docs/05-比赛规则与参赛手册.md` | 10 章与 3 个附录组成的完整比赛手册 |
| `docs/02-提交与排错.md` | 提交格式、常见故障、正式评测注意事项 |
| `docs/03-AI统一任务书.txt` | 给 AI 模型的统一任务提示 |
| `docs/04-AI单文件材料.txt` | 任务书 + 完整接口文档，适合只能附一份文本的模型 |
| `entry/bot.py` | 每个选手的起步代码 |
| `bots/codeside/` | 起步模板和协议测试用例 |
| `examples/` | 三赛段真实 init / turn JSON 和合法动作示例 |
| `arena/` | 本地模拟器、地图生成器、运行器、回放与素材 |
| `samples/1v1-Simple-1987.html` | 一场可离线打开的完整示范回放 |
| `kit.py` | 一键试跑、自测与提交打包 |
| `standings.py` | 三赛段等权场均积分总榜 |
| `VERSION.json`、`MANIFEST.sha256` | 版本与发行文件校验清单 |
| `licenses/`、`arena/games/codeside/assets/SOURCE.md` | 随附的许可文本和原素材来源说明 |

图像中的枪械、医疗包与场景是视觉表现；可操作物品、碰撞和弹药机制以协议与模拟器为准。没有新增可拾取的独立弹药箱机制。

本地工具会直接运行你选择的 Python 文件，仅应用于自己或已审阅的可信程序。正式比赛的隔离评测由主办方部署，开发包本身没有完整沙箱。
