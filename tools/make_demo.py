"""Generate a small original synthesized backing track, not a recording of a song."""
from pathlib import Path
import wave
import numpy as np


def make_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    rate, duration = 22050, 24
    t = np.arange(rate * duration) / rate
    audio = np.zeros_like(t)
    beat = 60 / 100
    chords = ((261.63, 329.63, 392.00), (220, 261.63, 329.63),
              (174.61, 220, 261.63), (196, 246.94, 293.66))
    for n, start in enumerate(np.arange(0, duration, beat)):
        age = t - start
        mask = (age >= 0) & (age < beat)
        a = age[mask]
        # Soft kick and plucked chord; predictable pulses make RMS movement easy to see.
        kick = np.sin(2 * np.pi * (55 * a + 2 * (1 - np.exp(-a * 30)))) * np.exp(-a * 20)
        chord = chords[(n // 8) % len(chords)]
        pluck = sum(np.sin(2 * np.pi * f * a) for f in chord) / 3 * np.exp(-a * 7)
        audio[mask] += 0.32 * kick + 0.16 * pluck
    audio *= np.minimum(1, t * 5) * np.minimum(1, (duration - t) / 1.5)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(directory / "demo.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    (directory / "demo.lrc").write_text(
        "[ti:轻松节奏（原创合成演示）]\n"
        "[00:00.40]给今天一点节奏\n[00:03.20]让文字轻轻跳动\n"
        "[00:06.00]灵感在屏幕边缘\n[00:09.00]陪你写下一行代码\n"
        "[00:12.00]不着急 慢慢来\n[00:15.00]专注也可以有趣\n"
        "[00:18.00]听见一点小快乐\n[00:21.00]把今天写成喜欢的样子\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    make_demo(Path(__file__).resolve().parents[1] / "assets")
