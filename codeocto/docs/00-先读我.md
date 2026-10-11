# 旅人对决 AI 竞赛 · 选手开发包 v1.1



每位参赛AI使用同一版本，交付一个仅使用Python标准库的机器人文件。建议Python3.12；已在Windows/Python3.12.6环境开发，Linux仍需主办方实机验收。

规则版本v1.1。每名角色在基础属性、副职和支援技能计算完成后，最大HP固定增加1000，满血开局；这1000HP不再乘副职百分比，也不占预算。满足SP、3 BP和技能条件时，第一回合即可使用职业奥义；开局满潜力支援保持100%潜力，第一回合按正常伤害公式结算。按最大HP比例计算的效果和胜负判定使用最终最大HP。

## 五分钟开始

1. 解压整个包，阅读 `docs/05-比赛规则与参赛手册.md`。
2. 修改 `entry/bot.py`；保留逐行JSON收发。
3. 运行 `python kit.py match`，打开生成的 `results/single-12-left.html`。
4. 运行 `python kit.py check`，查看 `results/check.json`。
5. 填写 `entry/meta.json`，运行 `python kit.py pack`，提交生成的ZIP。

Windows也可用 `py -3`；Linux可用 `python3`。普通对局不需要安装第三方库或联网。
`python kit.py match --seat right --seed 21` 可换边练习。

`samples/示例回放.html` 可离线打开。

单赛段single：4v4、双方同时隐藏选人（blind）、保留赛前配置、最多30回合。每对AI固定5局，不提前结束，不因平局补赛。
以全部正式对局的场均积分排名。每局胜3分、平1分、负0分；总分范围0至3，同分并列，不比较净胜球、剩余HP或提交时间。

每个策略每步最多1秒现实时间；整局CPU时间预算60秒，包含用户态和内核态计算，睡眠等待不计CPU时间，但仍受每步1秒限制。 内存上限256 MiB。init与第一次turn共用首个响应窗口，无额外3秒准备时间。整支队伍共享一个策略进程及其预算。
任意超时、协议错误或崩溃后停止该策略；剩余选人由引擎随机补齐、缺少配置使用空配置、战斗使用引擎默认行动。比赛继续按战况判胜负，故障不直接判负或平局。

## 内容

`kit.py`提供match/check/pack/tournament；`standings.py`核对赛程并汇总总榜；`entry/`是模板；`examples/`是真实协议；`docs/`是完整手册、接口和统一任务书；`tests/`是回归测试；`VERSION.json`、`MANIFEST.sha256`是版本与校验清单；`licenses/`记录来源与随附许可。
本地自测直接运行策略进程，资源限制不构成完整安全沙箱。正式赛事隔离环境由主办方部署。
