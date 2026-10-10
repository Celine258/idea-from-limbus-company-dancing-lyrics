#!/bin/bash
# macOS source launcher; adapted from qingyin-alice-zhong's mac-version.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
    printf '%s\n' '此入口仅用于 macOS；Windows 请使用启动.bat。' >&2
    exit 2
fi
if [ ! -x .venv/bin/python ]; then
    printf '%s\n' '尚未安装 macOS 环境，请先运行：bash 安装.sh' >&2
    exit 1
fi
exec .venv/bin/python main_mac.py "$@"
