"""Create a BetterNCM plugin archive with a per-installation local bridge secret."""
import argparse
import json
from pathlib import Path
import secrets
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package_plugin(state_dir, output, command):
    state_dir, output = Path(state_dir), Path(output)
    state_dir.mkdir(parents=True, exist_ok=True)
    config_path = state_dir / "netease-bridge.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        token = config.get("token", "")
        if not isinstance(token, str) or len(token) != 64:
            raise ValueError("现有连接配置无效，请先备份后删除 netease-bridge.json。")
    else:
        token = secrets.token_hex(32)
    config = {"token": token, "command": command}
    contents = json.dumps(config, ensure_ascii=False, indent=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Replace only this app's bridge configuration, never the user's lyric preferences.
    config_path.write_text(contents, encoding="utf-8")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("manifest.json", "adapter.js", "index.js"):
            archive.write(ROOT / "plugins" / "netease" / name, name)
        archive.writestr("bridge-config.json", contents)
    return output


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
