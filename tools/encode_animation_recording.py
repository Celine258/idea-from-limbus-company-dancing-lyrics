"""Encode Qt captures with an existing developer Pillow installation (not an app dependency)."""
import argparse
import json
from pathlib import Path
from PIL import Image


def encode(directory):
    manifest = json.loads((directory / "recording.json").read_text(encoding="utf-8"))
    paths = sorted((directory / "frames").glob("*.png"))
    if len(paths) != manifest["frames"] or not manifest["nativeWindowVisible"]:
        raise ValueError("录制帧或原生窗口验证不完整。")
    size = tuple(manifest["logicalSize"])
    frames = []
    for path in paths:
        with Image.open(path) as source:
            frames.append(source.convert("RGB").resize(size, Image.Resampling.LANCZOS))
    # GIF durations use 10ms units; 30/30/40ms preserves an average 30fps clock.
    durations = [30 if index % 3 != 2 else 40 for index in range(len(frames))]
    outputs = []
    for index, style in enumerate(manifest["styles"]):
        left, top = (index % 2) * 590, (index // 2) * 280
        cropped = [frame.crop((left, top, left + 590, top + 280)) for frame in frames]
        target = directory / f"{style}.gif"
        cropped[0].save(target, save_all=True, append_images=cropped[1:], duration=durations, loop=0, disposal=2)
        with Image.open(target) as result:
            duration = 0
            for frame in range(result.n_frames):
                result.seek(frame)
                duration += result.info["duration"]
            if duration != sum(durations) or result.n_frames < 100:
                raise ValueError(f"动图时长或帧数不完整：{style}")
            outputs.append({"file": target.name, "frames": result.n_frames, "durationMs": duration, "size": result.size})
    (directory / "encoded.json").write_text(json.dumps(outputs, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    encode(parser.parse_args().directory)
