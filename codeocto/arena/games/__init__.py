"""小游戏注册表（这份打包只含八方旅人对决 octopath；完整框架里还有 football、codeside）。"""
from .octopath.game import Octopath

GAMES = {
    Octopath.name: Octopath,
}


def get_game(name: str):
    try:
        return GAMES[name]
    except KeyError:
        raise ValueError(f"未知游戏 {name!r}，可选: {', '.join(GAMES)}") from None
