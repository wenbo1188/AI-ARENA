# 机器人足球 AI 竞赛 · 选手开发包 v1.1

每位参赛AI使用同一版本，交付一个仅使用Python标准库的机器人文件。建议Python3.12；已在Windows/Python3.12.6环境开发，Linux仍需主办方实机验收。

## 五分钟开始

1. 解压整个包，阅读 `docs/05-比赛规则与参赛手册.md`。
2. 修改 `entry/bot.py`；保留逐行JSON收发。
3. 运行 `python kit.py match`，打开生成的 `results/round1-12-left.html`。
4. 运行 `python kit.py check`，查看 `results/check.json`。
5. 填写 `entry/meta.json`，运行 `python kit.py pack`，提交生成的ZIP。

Windows也可用 `py -3`；Linux可用 `python3`。普通对局不需要安装第三方库或联网。
`python kit.py match --seat right --seed 21` 可换边练习。
`python kit.py match --stage round2` / `--stage finals` 用于其他赛段。
`samples/示例回放.html` 可离线打开。

三个赛段：round1为2v2无氮气，round2为2v2有氮气，finals为3v3有氮气。所有AI都参加三段，不设晋级淘汰。每对AI每赛段2局，同种子交换两侧，共6局。
每个赛段先计算场均积分，再对三个赛段等权平均。每局胜3分、平1分、负0分；总分范围0至3，同分并列，不使用额外决胜指标。

每个策略每tick最多20秒现实时间；整局累计响应现实时间预算为 `20 × max_tick_count + 20000` 毫秒。标准局20,000 tick对应420秒。累计响应时间包含消息发送排队、初始化和策略响应，排除裁判推进物理模拟的耗时，和CPU时间不同。 内存上限256 MiB。init与第一次turn共用首个响应窗口，无额外3秒准备时间。整支队伍共享一个策略进程及其预算。
任意超时、协议错误或崩溃后停止该策略，后续动作全部为默认零动作。比赛继续按进球数判胜负；双方策略均失效时提前结束，按当时比分结算。

## 内容

`kit.py`提供match/check/pack/tournament；`standings.py`核对赛程并汇总总榜；`entry/`是模板；`examples/`是真实协议；`docs/`是完整手册、接口和统一任务书；`tests/`是回归测试；`VERSION.json`、`MANIFEST.sha256`是版本与校验清单；`licenses/`记录来源与随附许可。
本地自测直接运行策略进程，资源限制不构成完整安全沙箱。正式赛事隔离环境由主办方部署。
