"""把八方旅人对决的回放渲染成一个独立 HTML（离线可看）。

场景和像素角色由 viewer.js 现场绘制；头像取自用户提供的设计图（ref/design_portraits.png 裁剪后存成 ref/portraits.json）；
技能特写的全身立绘取自 ref/design_fullbody.png，裁剪后存成 ref/fullbody.json；
战场上的角色、命中特效和音效取自用户提供的素材包 ref/kit/（ref/build_kit.py 压成 ref/kit.json）；
没有 kit.json 时退回 ref/design_battle.png 抠图裁出的 ref/battle.json。
"""
import base64
import html
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def render(replay: dict) -> str:
    with open(os.path.join(_DIR, "viewer.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(_DIR, "viewer.js"), encoding="utf-8") as f:
        js = f.read()
    pfile = os.path.join(_DIR, "ref", "portraits.json")
    portraits = "{}"
    if os.path.exists(pfile):
        with open(pfile, encoding="utf-8") as f:
            portraits = f.read().strip()
    cfile = os.path.join(_DIR, "ref", "fullbody.json")
    cutins = "{}"
    if os.path.exists(cfile):
        with open(cfile, encoding="utf-8") as f:
            cutins = f.read().strip()
    kfile = os.path.join(_DIR, "ref", "kit.json")
    kit = "{}"
    if os.path.exists(kfile):
        with open(kfile, encoding="utf-8") as f:
            kit = f.read().strip()
    bfile = os.path.join(_DIR, "ref", "battle.json")
    battle = "{}"
    if kit == "{}" and os.path.exists(bfile):  # 有素材包就不再带旧的单张战斗立绘
        with open(bfile, encoding="utf-8") as f:
            battle = f.read().strip()
    js = (f"const PORTRAIT_SRC = {portraits};\nconst CUTIN_SRC = {cutins};\nconst BATTLE_SRC = {battle};\n"
          f"const KIT_SRC = {kit};\n" + js)
    ffile = os.path.join(_DIR, "ref", "font_subset.woff2")
    font_css = ""
    if os.path.exists(ffile):
        # 思源黑体（Noto Sans SC，SIL OFL 1.1）子集，只含界面、技能名等会出现的字（见 ref/font_subset_chars.txt）
        with open(ffile, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        font_css = ('@font-face{font-family:"Replay CJK";font-style:normal;font-weight:100 900;font-display:block;'
                    f'src:url(data:font/woff2;base64,{b64}) format("woff2");}}')
    page = page.replace("/*__FONT__*/", font_css)
    data = json.dumps(replay, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = f"{replay['bots'][0]} vs {replay['bots'][1]} · 旅人对决"
    return (page.replace("__TITLE__", html.escape(title))
                .replace("@@DATA@@", data)
                .replace("__SCRIPT__", js.replace("</script", "<\\/script")))
