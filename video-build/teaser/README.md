# AI 圣杯战争 · 预告片制作（teaser）

本目录是 AI 竞技场预告片《AI 圣杯战争》的完整制作流程和源码：素材录制脚本、音乐剪辑、卡点分析，以及用代码逐帧渲染整部影片的 three.js 工程。成片 73 秒，1080p 60 fps。

影片没有用剪辑软件，所有镜头、文字、转场和调色都写在 `film/src/` 里，由无头 Chromium 逐帧渲染后交给 ffmpeg 编码。引擎改自 [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video)（MIT）。

## 故事设定

2031 年，六位"御主"（五个 AI 模型加一个 UNKNOWN 席位）召唤从者，开启 AI 圣杯战争。宣战瞬间圣杯碎裂，赛场被抛回三个时代，每个时代对应一场比赛，按顺序进行：

| 时代 | 比赛 | 代码目录 |
|---|---|---|
| 中世纪 | 八方旅人（4v4 回合制） | `codeocto/` |
| 1987 | 枪战对决（CodeSide 横版射击） | `codeside/` |
| 2087 | 机器人足球（CodeBall 2v2） | `codeball/` |

三道令咒等于三份程序，开战前一次性提交，比赛中不能干预。片中队伍一律用模型名：OPUS 5.5、GPT6-Astra、DeepSeek v4.1 Flash、GLM-5.3-Flash、Minimax-M3.1-Flash-Preview，以及 UNKNOWN。

## 目录结构

```
teaser/
├── film/                 影片工程（three.js + Vite + bun）
│   ├── src/timeline.ts   时间线：每个场景的起止小节
│   ├── src/scenes/       场景，_ 开头的是共用模块
│   ├── src/engine/       pdoom-video 引擎（逐帧时钟、后期、导出）
│   ├── scripts/          render.ts（出静帧） / export2.ts（多进程导出视频）
│   └── public/           assets（从者、精灵图）、fonts、data；footage 需自行录制
├── capture/              游戏素材录制
│   ├── octopath/         八方旅人
│   ├── codeside/         枪战对决
│   ├── football/         机器人足球
│   ├── analysis/         卡点与冲击帧分析
│   └── make_unknown.py   UNKNOWN 从者剪影
└── audio/
    └── music_edit_v10.py 音乐截取与淡出
```

## 环境准备

- [bun](https://bun.sh) 1.x，Node 20+，ffmpeg，Python 3（numpy、Pillow）
- Chromium：Playwright 自带或系统安装均可，用 `CHROME_PATH` 指定路径
- 中文字体：系统需安装 Noto Serif CJK SC 和 Noto Sans CJK SC（片中中文字幕用这两款，没有打包进仓库）
- 录制脚本用 Playwright：`npm i -g playwright`，或用 `PLAYWRIGHT_MODULE` 指向已安装的模块路径

```bash
cd film && bun install
```

环境变量（都有默认值，换机器时按需覆盖）：

| 变量 | 用途 |
|---|---|
| `CHROME_PATH` | 渲染与导出用的 Chromium 可执行文件 |
| `PLAYWRIGHT_MODULE` | 录制脚本 `require` 的 playwright 模块 |
| `ARENA_ROOT` | AI-ARENA 工作目录根（含 `arena/games/*` 播放器与 `results/` 回放） |
| `BASE` | 足球录制时回放 HTML 所在目录（file:// URL） |
| `OV` | 足球录制时的球与机器人位置修正文件（如 `pos_fix10.json`） |

## 第一步：录制游戏素材

原则：**不改游戏播放器本身**。每个录制脚本先把官方回放复制一份"宣传版"（在单位、切入画面上标出 AI 名字），再用无头浏览器打开 `?clean=1&w=…&h=…`（隐藏 UI）并通过 `window.arenaCapture` 逐帧控制时间和镜头，截成 JPEG。

素材统一放到 `film/public/footage/<镜头名>/00000.jpg …`，60 fps 序列。整套素材约 4 GB，不进仓库。

### 八方旅人

```bash
python3 capture/octopath/make_oc9.py replay.json oc9/page.html     # 生成宣传版回放（切入画面写 "OPUS 5.5 · 光" 等）
python3 capture/octopath/scan_native.py                             # 扫描 m/m*.json 回放每一步的技能，挑选各职业招牌技能
node capture/octopath/capj.js oc9/page.html 1920 1080 film/public/footage capture/octopath/shots_octo10.json
python3 capture/octopath/sheet.py film/public/footage/o11_claw 4    # 拼联系表，人工找冲击帧
```

`shots_octo10*.json` 是 v10 实际使用的镜头表（种子 12 的对局，旋风、冰冻、兽之爪、斧一闪、属性混乱等）。每条镜头写明回放步数、起止帧和机位。

### 枪战对决

```bash
python3 capture/codeside/make_cs9.py replay.json cs9/page.html "OPUS 5.5" "GPT6-Astra"   # 宣传版：单位头顶写模型名，?clean=1 下保留
python3 capture/codeside/scan2.py                                   # 扫描 m/*.json 回放里的击杀、爆炸 tick
node capture/codeside/capj.js cs9/page.html 1920 1080 film/public/footage capture/codeside/shots_cs9.json
python3 capture/codeside/make_cs_trooper.py film/public/assets      # 用新宿 1987 美术生成裂隙镜头里的火箭兵
```

镜头格式 `{name, t0, t1, n, c0:[x,y], c1, z0, z1, ease?}`：tick 区间、帧数、起止镜头中心和缩放。

### 机器人足球

```bash
python3 capture/football/make_foot8.py demo.html foot8/004.html     # 复制演示回放，场馆广告牌、全息投影、充气人只保留五家
node capture/football/fgoals.js                                     # 找出所有进球 tick
node capture/football/fseg.js '[[a,b]]'                             # 导出 tick 区间内的球、车轨迹
python3 capture/football/refit.py                                   # foot_seg.json → pos_fix.json，平滑轨迹
export BASE=file://$PWD/foot8/
OV=pos_fix.json node capture/football/capj_foot.js 1920 1080 film/public/footage capture/football/shots_foot10.js
node capture/football/capj_foot.js 1920 1080 film/public/footage capture/football/shots_venue10.js   # 场馆运镜
```

足球回放慢放时球会抖。`refit.py` 用分段二次曲线（容差 0.065）重新拟合球和机器人位置，`OV` 指向它的输出，让慢动作平滑。`shots_venue10.js` 是场馆运镜（全息投影、充气人、飞越看台），`cam` 字段是随进度 `u` 变化的机位表达式。

## 第二步：音乐

音乐由作者自备（本片用八方旅人 2 风格的战斗曲，128 BPM），不在仓库里。剪辑规则：**整首连续播放，不拼接**，从乐曲第 7.852 s 开始，在乐句结尾淡出。

```bash
ffmpeg -i track.wav -f f32le -ar 48000 -ac 2 octo.f32
python3 audio/music_edit_v10.py 6.3 73.125 4 v10c_73   # 增益 dB、结束时间、淡出小节数、输出名
```

换曲子时同步修改 `film/src/timeline.ts` 和各场景里的 `BAR`、`BEAT`（本片 BAR = 1.875 s，BEAT = 0.46875 s）。

## 第三步：时间线与场景

`film/src/timeline.ts` 以小节为单位排布场景：

| 小节 | 场景 | 内容 |
|---|---|---|
| 0–2 | `reel`（open） | 开场钩子"AI 圣杯战争，谁能夺冠？"，背景素材由虚到实对焦约 1 s |
| 2–5 | `city` | 2031 都市 |
| 5–8 | `masters` | 六位御主与召唤阵、从者 |
| 8–10 | `seals` | 三道令咒 = 三份程序 |
| 10–14 | `rift` | 三场比赛的全息屏，圣杯碎裂，时空漩涡 |
| 14–18 | `era`（0） | 中世纪 · 八方旅人 |
| 18–21 | `era`（1） | 1987 · 枪战对决 |
| 21–25 | `era`（2） | 2087 · 机器人足球 |
| 25–31 | `reel`（montage） | 加速剪辑，两拍、一拍、半拍递进，三款游戏均衡 |
| 31–39 | `finale` | 圣杯、标题、行动号召、从者合影、淡出 |

素材镜头用 `Shot {clip, t0, t1, frames, zoom?}` 描述，`frames` 把影片时间映射到素材帧。`reel.ts` 里的 `Hit(clip, g, b0, b1, hit, end)` 让素材的冲击帧（出招、击杀、进球）正好落在剪辑点后 0.04 s，所以每个镜头都"砸在拍子上"。时代转场是钟面时间流（`_timewarp.ts`），不用文字标注。

## 第四步：卡点检查

```bash
python3 capture/analysis/onset.py v10c_73.wav            # 频谱通量起音检测，生成 sync/onset.npz
python3 capture/analysis/seg.py; python3 capture/analysis/grid.py 0 40   # 每小节重音与节拍网格（小节范围）
python3 capture/analysis/vis.py out/test.mp4             # 成片画面突变点，对照节拍网格
python3 capture/analysis/spikes.py o11_claw cs10_kill    # 素材内部的冲击帧
python3 capture/analysis/strip.py strip.jpg 2 o11_claw   # 冲击帧附近的胶片条，人工确认
```

`vis.py` 会列出落在网格外的强剪辑点，逐个修正镜头的 `frames`，直到只剩有意为之的动画。

## 第五步：渲染

```bash
cd film
FILM_NO_HMR=1 bunx vite --port 5401 --strictPort        # 开发服务器（关掉 HMR，长时间导出更稳定）

# 静帧检查
bun scripts/render.ts stills --url http://localhost:5401 --t 1,12.5,40 --out out/stills

# 测试版：360p 24 fps，几分钟出片，用于审片
bun scripts/export2.ts --url http://localhost:5401 --from 0 --to 73.125 --fps 24 --workers 3 \
  --preset medium --crf 20 --scale 0.3333333 --audio ../v10c_73.wav --out out/test_360p24.mp4

# 正式版：1080p 60 fps（约 1.5 小时）
bun scripts/export2.ts --url http://localhost:5401 --from 0 --to 73.125 --fps 60 --workers 3 \
  --preset medium --crf 16 --audio ../v10c_73.wav --out out/master.mp4
```

先出测试版确认，再渲染正式版。

## 第六步：交付编码

```bash
# 手机分享版（约 100 MB）
ffmpeg -i out/master.mp4 -c:v libx264 -preset slow -b:v 11M -maxrate 16M -bufsize 22M \
  -pix_fmt yuv420p -c:a aac -b:a 256k -movflags +faststart 预告_1080p60.mp4

# 高码率下载版（约 325 MB）
ffmpeg -i out/master.mp4 -c:v libx264 -preset slow -b:v 36M -maxrate 50M -bufsize 72M \
  -pix_fmt yuv420p -c:a copy -movflags +faststart 预告_高码率.mp4
```

## 许可与素材来源

- 渲染引擎：改自 pdoom-video，MIT，见 `film/LICENSE.pdoom-video`
- 字体：Archivo、Cormorant Garamond、IBM Plex Mono 为 SIL OFL；`fonts/stroke` 为 Hershey 等单线字体
- 枪战对决精灵图来自 Russian AI Cup 2019 官方仓库（GPL-3.0）；新宿 1987 美术来自参赛套件 v1.2
- 从者立绘由作者用 GPT 生成；UNKNOWN 剪影由 `capture/make_unknown.py film/public/assets/servant_unknown_a.png` 程序生成
- 音乐不包含在仓库内
