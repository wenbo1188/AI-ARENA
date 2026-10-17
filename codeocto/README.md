# codeocto · 独立比赛开发入口 v2.0

- [旅人对决 4v4](../participant-materials/travelers/完整参赛说明.md)

每项只须提交 bot.py 和自由格式策略说明文档，文档不评分；无需元信息、报告或打包。
每项各 120 分钟，独立排名。正式规则与赛事入口见 [统一规则](../RULES.md) 和 [主办方运行说明](../ORGANIZER.md)。

```text
python kit.py match
python kit.py check
```

在源码目录可用 --stage 指定配置；独立发放包已固定本项配置。默认 check 是完整长度两局换边；短程调试用 --ticks 180（旅人用 --rounds 3）。
普通 tick 错误只影响当步，后续可恢复；初始化失败、进程崩溃或整局预算耗尽后默认接管、不重启。
本地子进程工具不提供完整禁网与文件隔离，正式部署须验收。
