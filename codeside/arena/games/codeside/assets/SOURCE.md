# 素材来源

除新增的 `shinjuku/` 目录外，本目录原有像素图（`*.png`）和 `heal.mp3` 取自 Russian AI Cup 2019 "CodeSide" 官方仓库：

- 仓库：https://github.com/MailRuChamps/raic-2019 （commit 1a57e49，2020-10-08）
- 原路径：`app-src/static/assets/`（图片原样复制；`heal.mp3` 由官方 `heal.wav` 用 ffmpeg 转码，内容未改）
- 许可证：GNU GPL-3.0（见仓库根目录 LICENSE）。版权归原作者（Mail.Ru Group / Russian AI Cup 团队）所有。

`viewer.py` 把这些文件以 data URI 内嵌进回放 HTML，回放页面因此也属于 GPL-3.0 素材的再分发，请保留本说明。

## sfx/ 目录：真实枪械音效

枪声、爆炸、换弹、跳弹等是真实录音加工而成，由 `sfx/make_sfx.py` 生成（裁剪、淡出、叠层、归一化）：

- 录音取自 Minetest 模组 Simple Shooter（https://github.com/stujones11/shooter），原始录音来自 freesound.org：
  - flobert1_20070728.wav，作者 Nonoo，CC BY 3.0
  - shot.wav，作者 Sergenious，CC BY 3.0
  - GUNSHOT.WAV，作者 erkanozan，CC0
  - winchester-rifle-cock-reload.wav，作者 MentalSanityOff，CC0
  - trigger-with-hammer-fall.wav，作者 Nanashi，CC0
  - woosh.wav，作者 ReadeOnly，CC0
  - AGM-114 Hellfire Rocket Missile Launch.flac，作者 qubodup，CC0
  - explosion10.wav，作者 V-ktor，CC0
- 跳弹声 `ricochet1-3` 取自 Warzone 2100（https://github.com/Warzone2100/warzone2100，`data/base/audio/sfx/explons/richet*.ogg`），GPL-2.0-or-later。
- `hit.mp3`（中弹闷响）、`mine_beep.mp3`（地雷报警）以及爆炸里的次低频层是 `make_sfx.py` 合成的。

## shinjuku/：东京新宿 1987 新视觉素材

2026-10-07 使用内置 imagegen，参考用户选定的新宿像素街机概念图生成。完整提示词及图集内容见 `shinjuku/GENERATION.txt`。

- city.png：新宿霓虹城市远景。
- actors.png：红／蓝队人物，站立、两帧跑动、跳跃、攀爬各五种姿态。
- items.png：医疗包、军用补给箱、手枪、步枪、火箭筒、地雷、弹药和弹匣。

这些 PNG 是本次新增素材，不属于前述直接复制的官方图片。原音效与其他原素材的来源说明继续保留。
