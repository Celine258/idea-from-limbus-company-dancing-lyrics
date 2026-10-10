#!/bin/bash
# macOS source setup. No sudo, bundled helper, or changes to the music client.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
    printf '%s\n' '此安装脚本仅用于 macOS。' >&2
    exit 2
fi
if ! command -v nowplaying-cli >/dev/null 2>&1 &&
   [ ! -x /opt/homebrew/bin/nowplaying-cli ] && [ ! -x /usr/local/bin/nowplaying-cli ] &&
   [ ! -x "${NOWPLAYING_CLI:-/nonexistent}" ]; then
    printf '%s\n' '请先通过 Homebrew 安装外部工具：brew install nowplaying-cli' >&2
    exit 1
fi
task_python=''
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 12)))'; then
        task_python="$candidate"
        break
    fi
done
if [ -z "$task_python" ]; then
    printf '%s\n' '需要 Python 3.10–3.12，推荐：brew install python@3.12' >&2
    exit 1
fi
if [ -d .venv ] && [ ! -x .venv/bin/python ]; then
    printf '%s\n' '.venv 不是可用的 macOS 环境。请先备份并移走此目录，再重新安装。' >&2
    exit 1
fi
if [ ! -d .venv ]; then
    "$task_python" -m venv .venv
fi
.venv/bin/python -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 12)))'
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import controls, overlay, macos_netease'
.venv/bin/python main_mac.py --check
chmod +x start.sh 启动.command
printf '%s\n' '安装完成。打开网易云并播放歌曲，然后双击启动.command。' \
    'macOS 联动仍为实验支持；系统、客户端版本与芯片的真机验证情况见 MACOS.md。'
