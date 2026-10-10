#!/bin/bash
task_root="$(cd -- "$(dirname -- "$0")" && pwd)"
bash "$task_root/start.sh" "$@"
task_status=$?
if [ "$task_status" -ne 0 ] && [ -t 0 ]; then
    printf '%s\n' '启动未完成，请保留上方提示。按回车关闭。'
    read -r task_answer
fi
exit "$task_status"
