#!/bin/bash
set -eu
if [ "$(uname -s)" != Darwin ]; then
    echo "此入口仅用于 macOS。"
    exit 1
fi
if command -v nowplaying-cli >/dev/null 2>&1 || [ -x /opt/homebrew/bin/nowplaying-cli ] || [ -x /usr/local/bin/nowplaying-cli ]; then
    echo "已找到播放读取工具，直接打开都市回响.app 即可。"
else
    brew_path="$(command -v brew || true)"
    if [ -z "$brew_path" ]; then
        for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
            if [ -x "$candidate" ]; then brew_path="$candidate"; break; fi
        done
    fi
    if [ -z "$brew_path" ]; then
        echo "请先按照 https://brew.sh/ 的说明安装 Homebrew，再重新打开此文件。"
        echo "完成后只需 brew install nowplaying-cli，无需安装 Python。"
    elif "$brew_path" install nowplaying-cli; then
        echo "安装完成，请重新打开都市回响.app。"
    else
        echo "安装失败，请检查网络后重新运行。"
        exit 1
    fi
fi
if [ -t 0 ]; then read -r -p "按回车关闭窗口…"; fi
