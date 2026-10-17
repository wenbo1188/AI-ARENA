# 主办方运行说明 v2.0

## 发放与开发

按 README 表格顺序为所有模型安排七项独立比赛。每项统一发放对应完整说明和对应 ZIP，记录精确模型版本、120 分钟开发的起止及经确认的设施暂停。开发计时和模型工具权限由统一的开发平台实施，event.py 不控制外部模型调用或自动切断开发会话。

截止时收取 bot.py 和自由格式策略说明，保存原件。模型身份、收件记录、摘要均由主办方管理，不能让选手另填自测证明。策略说明不评分、不强制内容模板。

## 安装与本地开发

使用 Windows / Python 3.12.6，所有功能只依赖标准库。源码内三个项目各保留 kit.py match/check，发放包已固定配置。

```text
python event.py list
python tools/build_materials.py
```

`participant-materials/` 和 `releases/` 是生成结果。统一规则只编辑 RULES.md；接口只编辑各项目 docs/接口源.md，修改后重新生成。不得单独维护 TXT/MD 两份正文。旧 docs/materials 链接只作为新入口指引；v1 主办方资料标记历史，不用于新比赛。

## 收件清单（主办方填写）

为每项建立独立 entries.json，恰好六个名字。路径相对该清单文件，说明文档格式不限。示例：

```json
{
  "AI-A": {"bot": "incoming/A/bot.py", "description": "incoming/A/strategy.md"},
  "AI-B": {"bot": "incoming/B/bot.py", "description": "incoming/B/strategy.txt"},
  "AI-C": {"bot": "incoming/C/bot.py", "description": "incoming/C/strategy.pdf"},
  "AI-D": {"bot": "incoming/D/bot.py", "description": "incoming/D/strategy.md"},
  "AI-E": {"bot": "incoming/E/bot.py", "description": "incoming/E/strategy.txt"},
  "AI-F": {"bot": "incoming/F/bot.py", "description": "incoming/F/strategy.md"}
}
```

## 冻结、准入与比赛

以下先以本地试跑模式说明流程。执行任何非可信提交前须配置独立隔离启动器，即使是非正式模式也不应直接执行来源不明的程序。

```text
python event.py init --event travelers --entries entries.json --out results/travelers
python event.py qualify results/travelers
python event.py run results/travelers --max-games 100
python event.py status results/travelers
```

init 将代码和说明复制到赛事目录，冻结摘要、规则及评测实现；只安排无种子的五轮配对，不生成正式种子。qualify 对每个选手与公开 quickstart 基准进行公开种子 12 的完整换边两局，不按胜率拒收、不因偶发错误拒收。任一基准永久失效时视为设施/基准异常，不能据此拒收选手。未通过准入者不进入对战排名，本版不足六人会阻止运行，主办方需先解决名额或另定赛制。

run 在比赛即将运行时才生成并落盘种子，每轮三场共用；同阶段 BO5 使用相同种子序列。每次只运行一局，进程异常、种子、双方出场侧、比分和回放均记录。普通 tick 错误可恢复；初始化失败或崩溃后默认接管、不重启。

事件目录包含 event.json（状态、审计、逐局结果、准入记录）、逐局 JSON/HTML 回放，以及完成后才生成的 ranking.json / ranking.html。开发模式榜单明确标为非正式。

## 正式隔离部署验收

源码的 Job Object / RLIMIT_AS 是资源限制，未完成跨选手文件隔离和禁网。正式部署由主办方提供并验收；不能用“已创建子进程”代替隔离验收。

准备 deployment.json：

```json
{
  "isolation_verified": true,
  "hardware": "填写实际 CPU、内存等配置",
  "machine_id": "填写实际 Windows 计算机名",
  "os": "Windows",
  "python": "3.12.6",
  "parallel_matches": 1,
  "bot_command": ["C:/Arena/verified-isolation-launcher.exe", "--seat", "{seat}", "--bot", "{bot}"]
}
```

此启动器仅为接口示例，不随仓库提供。必须为双方各自建立受限环境，禁网、禁止读取对手及裁判文件、限制进程和资源，并透传 stdin/stdout/stderr。正式模式校验主机系统与 Python、机器名、单场并发及验收登记；登记本身不证明启动器安全，须保存实际验收证据。启动器可通过 `{python}` 引用当前评测 Python；实际隔离环境也须确认 Python 3.12.6。

```text
python event.py init --event football-2v2 --entries entries.json --out results/football-2v2 --official --deployment deployment.json
python event.py qualify results/football-2v2
python event.py run results/football-2v2
```

正式模式有条件未满足时拒绝执行，不自动回退为非隔离正式计分。

## 中断、平局与复核

同一赛事使用操作系统文件锁防止两个调度器同时运行。状态原子写入；中断后重复 run 即可恢复，已完成小局不重跑，记录为 pending 的未完成小局沿用原种子和出场侧重赛。

`--max-games` 仅控制本次任务运行多少小局，达到后退出码为 2，赛事未结束，不发布名次。连续平局可暂停续跑，不自动抽签判胜。主办方可用它安排展示与运行时段，不能通过暂停筛选结果。

裁判设施故障修复后可恢复；若修复涉及已冻结的规则或评测器，摘要校验会阻止继续。主办方须保存原目录，暂停受影响比赛、统一公告修正范围，建立有明确版本迁移记录的重赛任务。不得手改摘要后不留记录地继续，也不得更换选手代码。

结果公布后开放 24 小时异议期，按冻结提交、运行日志及对局记录复核并公开结论。赛后公开种子、逐局比分、故障状态、名次和回放。

## 验证边界

自动测试覆盖赛程、排序、BO5、现场种子、暂停恢复及真实策略子进程故障恢复。部分集成检查使用短局加快验证，不能冒充正式完整长度准入。实际参赛选手尚未提交，完整正式赛事和独立隔离部署验收仍需在正式机器上执行。
