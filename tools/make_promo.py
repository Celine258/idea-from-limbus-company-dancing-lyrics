"""Encode a 30-second captioned demo using genuine Qt captures and original preview frames.

Developer-only tool: Pillow and an explicitly selected FFmpeg executable are required.
No music is included; the animation scenes use synthetic preview lyrics.
"""
import argparse
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def compose_frame(source, caption, subtitle):
    frame = Image.new("RGB", (1280, 720), "#11161d")
    source = source.convert("RGB")
    source.thumbnail((1200, 550), Image.Resampling.LANCZOS)
    frame.paste(source, ((1280-source.width)//2, 36+(550-source.height)//2))
    draw = ImageDraw.Draw(frame)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
    small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    draw.text((40, 608), caption, font=font, fill="#ff557b")
    draw.text((40, 661), subtitle, font=small, fill="#cbd3dc")
    return frame


def create(smoke, recording, installer, ffmpeg, output):
    smoke, recording, output = Path(smoke), Path(recording), Path(output)
    scenes = [
        (0, 5, smoke / "theme-light/effects-default-top.png", "跳动的歌词 · Windows 桌面音乐伴侣", "音乐由网易云播放；这个工具专注桌面歌词效果。"),
        (16, 19, smoke / "preset-quiet-settings.png", "安静办公 · 保存自己的效果方案", "字体、颜色、透明度与动画参数一次切换。"),
        (19, 22, smoke / "preset-lively-settings.png", "轻快律动 · 字体发光与逐字动画", "预设、字体导入和可用歌曲的演唱强调。"),
        (22, 26, smoke / "theme-special/effects-default-top.png", "特殊主题 · FACE THE SIN. SAVE THE E.G.O", "默认、深色和特殊主题；钟头图标随特殊主题切换。"),
        (26, 30, Path(installer), "下载 ZIP → 完整解压 → 双击安装", "GitHub: Celine258 / idea-from-limbus-company-dancing-lyrics"),
    ]
    manifest = json.loads((recording / "recording.json").read_text(encoding="utf-8"))
    if not manifest["nativeWindowVisible"]:
        raise ValueError("动画录制缺少真实原生窗口证据。")
    cached = {path: Image.open(path).convert("RGB") for _, _, path, _, _ in scenes}
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [str(ffmpeg), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1280x720", "-r", "30",
               "-i", "pipe:0", "-an", "-c:v", "libx264", "-threads", "1", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(output)]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL) as encoder:
        for index in range(900):
            second = index / 30
            if 5 <= second < 16:
                animation_frame = (index - 150) % manifest["frames"]
                with Image.open(recording / "frames" / f"{animation_frame:04d}.png") as source:
                    frame = compose_frame(source, "波纹·波动 / 波纹·抖动 / 跌落·波动 / 跌落·抖动",
                                          "实际 Qt 动画预览 · 原创示例歌词；演示不操作网易云播放。")
            else:
                scene = next(scene for scene in scenes if scene[0] <= second < scene[1])
                frame = compose_frame(cached[scene[2]], scene[3], scene[4])
            encoder.stdin.write(frame.tobytes())
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError("演示视频编码失败。")
    report = {"frames": 900, "fps": 30, "durationSeconds": 30, "size": [1280,720], "audio": False,
              "source": "genuine Qt screenshots and native animation preview captures", "musicControlled": False,
              "cleanMachine": False}
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--recording", type=Path, default=ROOT / "artifacts/animations-demo")
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/releases/dancing-lyrics-demo-30s.mp4")
    args = parser.parse_args()
    create(args.smoke, args.recording, args.installer, args.ffmpeg, args.output)
