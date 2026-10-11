"""小游戏注册表。新增游戏：实现 arena.game.Game 子类，然后加到 GAMES 里。"""
from .football.game import Football

GAMES = {
    Football.name: Football,
}


def get_game(name: str):
    try:
        return GAMES[name]
    except KeyError:
        raise ValueError(f"未知游戏 {name!r}，可选: {', '.join(GAMES)}") from None
