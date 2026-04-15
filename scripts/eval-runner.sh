#!/bin/bash
# 评估任务执行器 — 计时 + 日志 + macOS 通知
# 用法: ./eval-runner.sh <agent> <task-id> <command...>
# 示例: ./eval-runner.sh cc task-1 claude --print "build bmk project"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARENA_DIR="$(dirname "$SCRIPT_DIR")"

AGENT="${1:?用法: eval-runner.sh <agent> <task-id> <command...>}"
TASK="${2:?缺少 task-id 参数}"
shift 2

LOG_DIR="${ARENA_DIR}/results/${AGENT}"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/${TASK}.log"

echo "========================================" | tee "$LOG_FILE"
echo "Agent: ${AGENT}" | tee -a "$LOG_FILE"
echo "Task:  ${TASK}" | tee -a "$LOG_FILE"
echo "Command: $*" | tee -a "$LOG_FILE"
echo "Start: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

START=$(date +%s)

# 执行命令，同时输出到终端和日志
set +e
"$@" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}
set -e

END=$(date +%s)
DURATION=$((END - START))

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "End:      $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "Duration: ${DURATION}s" | tee -a "$LOG_FILE"
echo "Exit:     ${EXIT_CODE}" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 写入 metrics
METRICS_FILE="${LOG_DIR}/metrics.json"
if [ ! -f "$METRICS_FILE" ]; then
    echo '{}' > "$METRICS_FILE"
fi

# 用 python 更新 metrics JSON（避免依赖 jq）
python3 -c "
import json, sys
f = '${METRICS_FILE}'
with open(f) as fp:
    data = json.load(fp)
data['${TASK}'] = {
    'duration_seconds': ${DURATION},
    'exit_code': ${EXIT_CODE},
    'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)',
    'log_file': '${LOG_FILE}'
}
with open(f, 'w') as fp:
    json.dump(data, fp, indent=2, ensure_ascii=False)
"

# macOS 通知
if [ $EXIT_CODE -eq 0 ]; then
    osascript -e "display notification \"耗时 ${DURATION}s\" with title \"[${AGENT}] ${TASK} 完成\" sound name \"Glass\""
else
    osascript -e "display notification \"退出码: ${EXIT_CODE}，请检查日志\" with title \"[${AGENT}] ${TASK} 失败\" sound name \"Basso\""
fi

# 人工评分提醒（延迟 2 秒后弹出，避免通知堆叠）
sleep 2
osascript -e "display notification \"请对 ${AGENT} 的 ${TASK} 进行评分\" with title \"等待人工评分\" sound name \"Ping\""

exit $EXIT_CODE
