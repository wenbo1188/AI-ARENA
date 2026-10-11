"""关卡生成，逐行移植官方 app-src/src/model/level/{mod.rs, complex.rs}。

tiles[x][y]，x 向右、y 向上，(0, 0) 是左下角。地块用官方枚举名字符串表示。
官方用 Rust 的 rand 随机数，这里换成 Python 的 random.Random，生成算法相同，但同一个种子得到的地图和原版不同。
"""
from __future__ import annotations

import os
import random

EMPTY, WALL, PLATFORM, LADDER, JUMP_PAD = "EMPTY", "WALL", "PLATFORM", "LADDER", "JUMP_PAD"

WALKABLE = {WALL, PLATFORM, LADDER}          # Tile::is_walkable
CAN_PLANT_MINE = {WALL, PLATFORM}            # Tile::can_plant_mine


def parse(text: str):
    """官方 LevelOptions::parse：# 墙  . 空  ^ 平台  H 梯子  T 跳板  P / 数字 出生点。"""
    lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
    spawn, extra = [], []
    tiles: list[list[str]] = []
    for y, line in enumerate(lines):
        for x, c in enumerate(line):
            while x >= len(tiles):
                tiles.append([])
            while y >= len(tiles[x]):
                tiles[x].append(EMPTY)
            if c == "#":
                t = WALL
            elif c == ".":
                t = EMPTY
            elif c == "^":
                t = PLATFORM
            elif c == "H":
                t = LADDER
            elif c == "T":
                t = JUMP_PAD
            elif c == "P":
                spawn.append([x + 0.5, y])
                t = EMPTY
            elif c.isdigit():
                extra.append((int(c), [x + 0.5, y]))
                t = EMPTY
            else:
                raise ValueError(f"关卡里有无法识别的字符 {c!r}")
            tiles[x][y] = t
    extra.sort(key=lambda e: e[0])
    spawn += [p for _, p in extra]
    h = len(tiles[0])
    for col in tiles:
        if len(col) != h:
            raise ValueError("关卡每一行长度必须相同")
        col.reverse()
    for p in spawn:
        p[1] = h - p[1] - 1
    return tiles, spawn


def empty_box(width: int = 40, height: int = 30):
    tiles = [[WALL if x in (0, width - 1) or y in (0, height - 1) else EMPTY for y in range(height)]
             for x in range(width)]
    spawn = []
    for i in range(1, width // 2):
        spawn.append([i + 0.5, 1.0])
        spawn.append([width - i - 0.5, 1.0])
    return tiles, spawn


def simple(rng: random.Random):
    """LevelOptions::Simple（官方第一、二轮用的关卡）。"""
    width, height = 40, 30
    tiles = [[EMPTY] * height for _ in range(width)]
    for y in range(height):
        tiles[0][y] = WALL
    step = 5
    y = 0
    spawn = []
    for x in range(width // 2):
        tiles[x][height - 1] = WALL
        if x % step == 0:
            next_y = rng.randrange(0, height - 5)
            for yy in range(min(y, next_y), max(y, next_y) + 1):
                tiles[x][yy] = WALL
            if x != 0:
                options = 3 if max(next_y, y) - min(next_y, y) < 10 else 2
                kind = rng.randrange(0, options)
                if kind == 0:
                    lx = x - 1 if next_y > y else x + 1
                    for yy in range(min(y, next_y) + 1, max(y, next_y) + 1):
                        tiles[lx][yy] = LADDER
                elif kind == 1:
                    xr = range(x - 2, x) if next_y > y else range(x + 1, x + 3)
                    for px in xr:
                        for yy in list(range(min(y, next_y), max(y, next_y) + 1, 3))[1:]:
                            tiles[px][yy] = PLATFORM
                else:
                    jx = x - 1 if next_y > y else x + 1
                    tiles[jx][min(y, next_y) + 1] = JUMP_PAD
            y = next_y
        tiles[x][y] = WALL
        if x > 0:
            spawn.append([x + 0.5, y + 1.0])
            spawn.append([width - x - 0.5, y + 1.0])
    for x in range(width // 2):
        for yy in range(height):
            tiles[width - 1 - x][yy] = tiles[x][yy]
    return tiles, spawn


def complex_(rng: random.Random):
    """LevelOptions::Complex（官方决赛用的关卡）：5×5 大格子组成的随机连通迷宫，左右对称。"""
    width, height, w, h = 40, 30, 5, 5
    sw, sh = width // w // 2, height // h
    left = [[False] * sh for _ in range(sw)]
    down = [[False] * sh for _ in range(sw)]
    nx = [[(i, j) for j in range(sh)] for i in range(sw)]

    def root(p):
        while nx[p[0]][p[1]] != p:
            p = nx[p[0]][p[1]]
        return p

    def connected():
        r0 = root((0, 0))
        return all(root((i, j)) == r0 for i in range(sw) for j in range(sh))

    def unite(p1, p2):
        r1, r2 = root(p1), root(p2)
        nx[r1[0]][r1[1]] = r2

    while not connected():
        options = []
        for i in range(sw):
            for j in range(sh):
                if i > 0 and not left[i][j]:
                    options.append((i, j, 0))
                if j > 0 and not down[i][j]:
                    options.append((i, j, 1))
        i, j, side = options[rng.randrange(0, len(options))]
        if side == 0:
            left[i][j] = True
            unite((i, j), (i - 1, j))
        else:
            down[i][j] = True
            unite((i, j), (i, j - 1))

    tiles = [[EMPTY] * height for _ in range(width)]
    for i in range(sw):
        j = 0
        while j < sh:
            nj = j + 1
            mx = rng.randrange(1, 3)
            while nj < j + mx + 1 and nj < sh and down[i][nj]:
                nj += 1
            nj -= 1
            y = nj * h
            if nj > j:
                if nj + 1 < sh and down[i][nj + 1]:
                    for x in range(i * w, (i + 1) * w):
                        tiles[x][y] = PLATFORM
                if nj - j == 2:
                    x = rng.randrange(i * w + 2, (i + 1) * w - 1)
                    if not (nj + 1 < sh and down[i][nj + 1]) or rng.random() < 0.5:
                        tiles[x][j * h + 1] = JUMP_PAD
                    else:
                        for yy in range(j * h + 1, nj * h + 1):
                            tiles[x][yy] = LADDER
                j = nj
            else:
                j += 1
    for i in range(sw):
        for j in range(sh):
            if not left[i][j]:
                x = i * w
                for yy in range(j * h, (j + 1) * h + 1):
                    if yy < height:
                        tiles[x][yy] = WALL
            if not down[i][j]:
                y = j * h
                for x in range(i * w, (i + 1) * w + 1):
                    tiles[x][y] = WALL
    for x in range(width // 2):
        for yy in range(height):
            tiles[width - 1 - x][yy] = tiles[x][yy]
    for x in range(width):
        tiles[x][height - 1] = WALL
    spawn = []
    for i in range(1, 3):
        spawn.append([i + 0.5, 1.0])
        spawn.append([width - i - 0.5, 1.0])
    return tiles, spawn


def official_txt():
    """官方仓库 app-src/static/levels/level.txt（本地比赛程序自带的固定关卡）。"""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "level.txt"), encoding="utf-8") as f:
        return parse(f.read())


LEVELS = {
    "simple": simple,
    "complex": complex_,
    "level.txt": lambda rng: official_txt(),
    "empty": lambda rng: empty_box(),
}


def create(name: str, rng: random.Random):
    if name in LEVELS:
        return LEVELS[name](rng)
    if os.path.exists(name):          # 自定义关卡文件，格式同官方 level.txt
        with open(name, encoding="utf-8") as f:
            return parse(f.read())
    raise ValueError(f"未知关卡 {name!r}，可选: {', '.join(LEVELS)}，或一个 .txt 关卡文件路径")
