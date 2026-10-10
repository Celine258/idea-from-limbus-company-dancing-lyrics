#!/bin/bash
# Remove this checkout's Python environment; keep all personal data and Homebrew.
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
    printf '%s\n' '此卸载脚本仅用于 macOS。' >&2
    exit 2
fi
printf '%s' '退出歌词程序后，删除本目录的 .venv？设置、字体、预设和歌曲偏移均保留。[y/N] '
read -r task_answer
case "$task_answer" in
    y|Y)
        if [ -L .venv ]; then
            printf '%s\n' '.venv 为符号链接，请手动处理；未删除任何内容。' >&2
            exit 1
        fi
        if [ -d .venv ]; then
            rm -rf -- "$PWD/.venv"
        fi
        printf '%s\n' '已移除运行环境；.state、源码及共用外部工具均保留。'
        ;;
    *) printf '%s\n' '已取消。' ;;
esac
