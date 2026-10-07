"""Create a BetterNCM plugin archive with a per-installation local bridge secret."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from netease_install import package_plugin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, default=ROOT / "dist/FloatingLyrics/.state")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/netease-plugin/FloatingLyrics.plugin")
    parser.add_argument("--source", action="store_true")
    args = parser.parse_args()
    if args.source:
        exe = Path(sys.executable).with_name("pythonw.exe")
        command = f'"{exe}" "{ROOT / "main.py"}" --netease --background'
    else:
        exe = ROOT / "dist/FloatingLyrics/FloatingLyrics.exe"
        if not exe.is_file():
            parser.error("请先运行 build.ps1 构建桌面歌词引擎。")
        command = f'"{exe}" --netease --background'
    print(package_plugin(args.state_dir, args.output, command))


if __name__ == "__main__":
    main()
