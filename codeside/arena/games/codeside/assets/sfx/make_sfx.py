"""重新生成 CodeSide 回放音效（离线工具，回放运行时不需要；依赖 numpy 和 ffmpeg）。

真实录音来源（许可证见同目录 SOURCE.md）：
  minetest-mods shooter（github.com/stujones11/shooter）里的 freesound 录音
  Warzone 2100（github.com/Warzone2100/warzone2100）的跳弹声，GPL-2.0-or-later
用法：python3 make_sfx.py SHOOTER_SOUNDS_DIR WARZONE_SFX_DIR
"""
import os
import subprocess
import sys

import numpy as np

SR = 48000
OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(2019)


def load(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def sec(x, a, b=None):
    return x[int(a * SR): None if b is None else int(b * SR)]


def fade(x, fin=0.002, fout=0.08):
    x = x.copy()
    n1, n2 = int(fin * SR), int(fout * SR)
    if n1: x[:n1] *= np.linspace(0, 1, n1)
    if n2: x[-n2:] *= np.linspace(1, 0, n2) ** 2
    return x


def onepole_lp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); s = 0.0
    for i, v in enumerate(x):
        s = (1 - a) * v + a * s; y[i] = s
    return y


def hp(x, fc):
    return x - onepole_lp(x, fc)


def drive(x, k):
    return np.tanh(k * x) / np.tanh(k)


def norm(x, peak=0.89):
    return x / (np.abs(x).max() + 1e-9) * peak


def decay_env(n, tau, hold=0.0):
    t = np.arange(n) / SR
    return np.where(t < hold, 1.0, np.exp(-(t - hold) / tau))


def mix(*parts):
    n = max(len(p) for p in parts); out = np.zeros(n)
    for p in parts: out[:len(p)] += p
    return out


def save(name, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-ar", "44100", "-b:a", "96k", os.path.join(OUT, name + ".mp3")], input=pcm, check=True)
    print(name, f"{len(x) / SR:.2f}s")


def main(shooter, warzone):
    S = lambda n: load(os.path.join(shooter, n))
    pistol, shotgun, rocket = S("shooter_pistol.ogg"), S("shooter_shotgun.ogg"), S("shooter_rocket_fire.ogg")
    explode, reload_, click, throw = S("shooter_explode.ogg"), S("shooter_reload.ogg"), S("shooter_click.ogg"), S("shooter_throw.ogg")

    # 手枪：原始录音，去掉低频轰鸣、收短尾音
    on = np.argmax(np.abs(pistol) > 0.05)
    p = hp(pistol[max(0, on - 48):], 120)
    save("pistol", norm(fade(sec(p, 0, 0.5), 0.001, 0.25)))

    # 突击步枪：手枪录音的枪口爆音做瞬态 + 霰弹枪录音的低频枪身，尾音短、带一点饱和，更“冲”
    on2 = np.argmax(np.abs(shotgun) > 0.1)
    body = onepole_lp(sec(shotgun[max(0, on2 - 24):], 0, 0.42), 2500) * decay_env(int(0.42 * SR), 0.09, 0.012)
    crack = hp(sec(p, 0, 0.12), 900) * decay_env(int(0.12 * SR), 0.03)
    save("assault_rifle", norm(fade(drive(norm(mix(body * 0.9, crack * 1.1)), 1.6), 0.001, 0.15)))

    # 火箭筒：点火爆音 + 导弹发射的呼啸
    on3 = np.argmax(np.abs(rocket) > 0.05)
    roar = sec(rocket[on3:], 0, 1.3) * decay_env(int(1.3 * SR), 0.45, 0.15)
    pop = onepole_lp(sec(shotgun[max(0, on2 - 24):], 0, 0.25), 1200) * decay_env(int(0.25 * SR), 0.06)
    save("rocket_launcher", norm(fade(mix(pop * 0.8, roar), 0.001, 0.3)))

    # 爆炸：录音 + 合成的次低频冲击（40-70 Hz 下滑正弦），更有分量
    on4 = np.argmax(np.abs(explode) > 0.1)
    n = int(0.9 * SR); t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(38 + 40 * np.exp(-t / 0.12)) / SR) * decay_env(n, 0.28, 0.02)
    save("explosion", norm(fade(drive(norm(mix(sec(explode[on4:], 0, 1.9), sub * 0.7)), 1.3), 0.001, 0.5)))

    # 换弹：栓动上膛录音
    save("reload", norm(fade(reload_, 0.001, 0.05), 0.7))
    # 捡枪：上膛录音的前一半（拉栓）
    save("pickup", norm(fade(sec(reload_, 0, 0.3), 0.001, 0.06), 0.6))
    # 放地雷 / 捡地雷：扳机击锤声
    save("click", norm(fade(click, 0.0005, 0.03), 0.6))
    # 跳板：挥动的呼呼声
    save("pad", norm(fade(throw, 0.01, 0.1), 0.5))

    # 跳弹（子弹打墙）：Warzone 2100 的三段跳弹录音
    for k in (1, 2, 3):
        x = load(os.path.join(warzone, "explons", f"richet{k}.ogg"))
        save(f"ricochet{k}", norm(fade(x, 0.001, 0.12), 0.55))

    # 中弹：合成的闷击声（下滑低频 + 低通噪声冲击 + 衣物摩擦的高频）
    n = int(0.18 * SR); t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(55 + 110 * np.exp(-t / 0.02)) / SR) * decay_env(n, 0.04)
    noise = rng.standard_normal(n)
    smack = onepole_lp(noise, 1400) * decay_env(n, 0.014) * 3
    cloth = hp(noise, 3000) * decay_env(n, 0.006) * 0.35
    save("hit", norm(fade(drive(mix(thump, smack, cloth), 1.2), 0.0005, 0.04), 0.8))

    # 地雷触发：压电蜂鸣器两声短促报警
    beep_n = int(0.07 * SR); t = np.arange(beep_n) / SR
    beep = (np.sin(2 * np.pi * 3100 * t) + 0.25 * np.sin(2 * np.pi * 9300 * t)) * np.minimum(1, t / 0.002) * np.minimum(1, (0.07 - t) / 0.01)
    save("mine_beep", norm(np.concatenate([beep, np.zeros(int(0.06 * SR)), beep]), 0.35))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
