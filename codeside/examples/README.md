# 协议样例

这些 JSON 由本包运行器生成。round1 / round2 / finals 分别使用公开练习 seed 12 / 21 / 34，均为左侧玩家和 tick 0。
init 和 turn 是裁判发来的消息，action 是合法的静止回复，只用于格式参考，不是强策略。
JSON 文件为便于阅读使用缩进；真实管道消息必须压成一行并以换行结束。init 回复另发 {"ready":true}。
