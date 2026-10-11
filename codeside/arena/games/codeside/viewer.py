"""把 CodeSide 回放渲染成一个独立 HTML（离线可看）。

画面按官方 app-src/src/renderer 的 Fancy 模式绘制，像素素材来自官方仓库 app-src/static/assets
（raic-2019 以 GPL-3.0 发布），音效是 assets/sfx 下的真实录音加工版，出处都见 assets/SOURCE.md，全部以 data URI 内嵌。
"""
import base64
import html
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_ASSETS = os.path.join(_DIR, "assets")
_cache = None


def _assets_json() -> str:
    global _cache
    if _cache is None:
        out = {}
        for root, _, files in os.walk(_ASSETS):
            for name in sorted(files):
                ext = os.path.splitext(name)[1]
                mime = {".png": "image/png", ".mp3": "audio/mpeg"}.get(ext)
                if not mime:
                    continue
                path = os.path.join(root, name)
                key = os.path.relpath(path, _ASSETS).replace(os.sep, "/")
                with open(path, "rb") as f:
                    out[key] = f"data:{mime};base64," + base64.b64encode(f.read()).decode()
        _cache = json.dumps(out, separators=(",", ":"))
    return _cache


def render(replay: dict) -> str:
    with open(os.path.join(_DIR, "viewer.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(_DIR, "viewer.js"), encoding="utf-8") as f:
        js = f.read()
    data = json.dumps(replay, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = f"{replay['bots'][0]} vs {replay['bots'][1]} · CodeSide"
    # 比赛数据最后替换，免得里面（比如机器人的 stderr）碰巧含有占位符
    return (page.replace("__TITLE__", html.escape(title))
                .replace("__SCRIPT__", js.replace("</script", "<\\/script"))
                .replace("@@ASSETS@@", _assets_json())
                .replace("@@DATA@@", data))
