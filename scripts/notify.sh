#!/bin/bash
# macOS 系统通知包装器
# 用法: ./notify.sh "标题" "内容" [sound]
# sound 选项: Glass(成功), Basso(失败), Ping(需人工), Hero(里程碑)
TITLE="${1:-Agent Eval}"
MSG="${2:-任务完成}"
SOUND="${3:-Glass}"
osascript -e "display notification \"$MSG\" with title \"$TITLE\" sound name \"$SOUND\""
