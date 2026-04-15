#!/bin/bash
# Category 1: CLI 书签管理器 自动验证脚本
# 用法: ./verify-cat1.sh <项目目录路径>

set -uo pipefail

PROJECT_DIR="${1:?用法: verify-cat1.sh <项目目录路径>}"
SCORE=0
TOTAL=0
DETAILS=""

check() {
    local desc="$1"
    local result="$2"
    TOTAL=$((TOTAL + 1))
    if [ "$result" -eq 0 ]; then
        SCORE=$((SCORE + 1))
        DETAILS="${DETAILS}\n  PASS: ${desc}"
    else
        DETAILS="${DETAILS}\n  FAIL: ${desc}"
    fi
}

echo "=== Category 1 自动验证: ${PROJECT_DIR} ==="
echo ""

# 1. 文件结构检查
echo "--- 文件结构 ---"
for f in pyproject.toml README.md; do
    test -f "${PROJECT_DIR}/${f}"
    check "文件存在: ${f}" $?
done

# 检查 src 布局或扁平布局
if [ -d "${PROJECT_DIR}/src/bmk" ]; then
    for f in __init__.py cli.py db.py; do
        test -f "${PROJECT_DIR}/src/bmk/${f}"
        check "源文件: src/bmk/${f}" $?
    done
elif [ -d "${PROJECT_DIR}/bmk" ]; then
    for f in __init__.py cli.py db.py; do
        test -f "${PROJECT_DIR}/bmk/${f}"
        check "源文件: bmk/${f}" $?
    done
else
    check "源文件目录存在 (src/bmk/ 或 bmk/)" 1
fi

# 测试文件
find "${PROJECT_DIR}" -name "test_*.py" -o -name "*_test.py" | grep -q .
check "测试文件存在" $?

# 2. 安装检查
echo ""
echo "--- 安装检查 ---"
cd "${PROJECT_DIR}"
pip install -e . --quiet 2>/dev/null
check "pip install -e . 成功" $?

bmk --help >/dev/null 2>&1
check "bmk --help 可执行" $?

# 3. 功能检查
echo ""
echo "--- 功能检查 ---"
export BMK_DB="/tmp/bmk-verify-$$.db"
rm -f "$BMK_DB"

bmk add https://example.com --title "Verify Test" --tags verify,test 2>/dev/null
check "bmk add 成功" $?

bmk list 2>/dev/null | grep -q "example.com"
check "bmk list 显示已添加的书签" $?

bmk search "verify" 2>/dev/null | grep -q .
check "bmk search 返回结果" $?

bmk tags 2>/dev/null | grep -q .
check "bmk tags 列出标签" $?

bmk export --format json --output /tmp/bmk-verify-export-$$.json 2>/dev/null
check "bmk export json 成功" $?

bmk import /tmp/bmk-verify-export-$$.json 2>/dev/null
check "bmk import 成功" $?

bmk stats 2>/dev/null | grep -q .
check "bmk stats 显示统计" $?

# 4. 测试检查
echo ""
echo "--- pytest 检查 ---"
cd "${PROJECT_DIR}"
python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/bmk-pytest-$$.log
PYTEST_EXIT=$?
check "pytest 全部通过" $PYTEST_EXIT

TEST_COUNT=$(grep -c "PASSED\|FAILED" /tmp/bmk-pytest-$$.log 2>/dev/null || echo 0)
if [ "$TEST_COUNT" -ge 8 ]; then
    check "测试数量 >= 8" 0
else
    check "测试数量 >= 8 (实际: ${TEST_COUNT})" 1
fi

# 清理
rm -f "$BMK_DB" /tmp/bmk-verify-export-$$.json /tmp/bmk-pytest-$$.log

# 汇总
echo ""
echo "=== 验证结果 ==="
echo -e "$DETAILS"
echo ""
echo "通过: ${SCORE}/${TOTAL}"
echo "得分: $(python3 -c "print(round(${SCORE}/${TOTAL}*10, 1))")/10"
