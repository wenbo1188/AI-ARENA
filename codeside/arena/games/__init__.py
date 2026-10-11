"""小游戏注册表。新增游戏：实现 arena.game.Game 子类，然后加到 GAMES 里。

（这份导出只包含 CodeSide；完整竞技场里还注册了 football 和 octopath。）
"""
from .codeside.game import CodeSide

GAMES = {
    CodeSide.name: CodeSide,
}


def get_game(name: str):
    try:
        return GAMES[name]
    except KeyError:
        raise ValueError(f"未知游戏 {name!r}，可选: {', '.join(GAMES)}") from None
