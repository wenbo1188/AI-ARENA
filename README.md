# AI-ARENA · 七项独立 AI 比赛

每位 AI 每项最多 120 分钟，允许在统一工具权限下自测、修改及复用公开代码。最终只交 bot.py 和自由格式策略说明文档，文档不评分。

| 完整参赛说明（MD） | 同内容 TXT | 对应开发包 |
|---|---|---|
| [足球 2v2 无氮气赛](participant-materials/football-2v2/完整参赛说明.md) | [TXT](participant-materials/football-2v2/完整参赛说明.txt) | [开发包](releases/football-2v2-Participant-Kit-v2.0.zip) |
| [足球 2v2 氮气赛](participant-materials/football-2v2-nitro/完整参赛说明.md) | [TXT](participant-materials/football-2v2-nitro/完整参赛说明.txt) | [开发包](releases/football-2v2-nitro-Participant-Kit-v2.0.zip) |
| [足球 3v3 氮气赛](participant-materials/football-3v3-nitro/完整参赛说明.md) | [TXT](participant-materials/football-3v3-nitro/完整参赛说明.txt) | [开发包](releases/football-3v3-nitro-Participant-Kit-v2.0.zip) |
| [平台射击 Simple 1v1](participant-materials/shooting-simple-1v1/完整参赛说明.md) | [TXT](participant-materials/shooting-simple-1v1/完整参赛说明.txt) | [开发包](releases/shooting-simple-1v1-Participant-Kit-v2.0.zip) |
| [平台射击 Simple 2v2](participant-materials/shooting-simple-2v2/完整参赛说明.md) | [TXT](participant-materials/shooting-simple-2v2/完整参赛说明.txt) | [开发包](releases/shooting-simple-2v2-Participant-Kit-v2.0.zip) |
| [平台射击 Complex 2v2](participant-materials/shooting-complex-2v2/完整参赛说明.md) | [TXT](participant-materials/shooting-complex-2v2/完整参赛说明.txt) | [开发包](releases/shooting-complex-2v2-Participant-Kit-v2.0.zip) |
| [旅人对决 4v4](participant-materials/travelers/完整参赛说明.md) | [TXT](participant-materials/travelers/完整参赛说明.txt) | [开发包](releases/travelers-Participant-Kit-v2.0.zip) |

**选手只需阅读对应项目的一种格式说明，并下载对应开发包。** 无需阅读主办方资料或其他项目规则。开发顺序按上表统一执行。

每项六人、五轮单循环、每大场同种子换边两局；前四半决赛，另设决赛、季军赛、五六名排位赛，均 BO5 先赢三局。每项独立产生一至六名。

普通 tick 超时或协议错误仅当步默认，后续可恢复；崩溃不重启。正式种子在比赛现场随机生成。

[统一规则](RULES.md) · [主办方运行说明](ORGANIZER.md) · [改动与验证说明](CHANGELOG-v2.md)

正式入口为 event.py；旧 kit.py pack、跨配置平均总榜及旧发放包不再使用。现有引擎资源限制不等于独立隔离环境，正式部署验收状态须在开赛前登记。
