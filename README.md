# Agent Eval Arena

AI Coding Agent 三框架对比评估项目。

## 评估对象

| Agent | 版本 | 类型 |
|-------|------|------|
| Claude Code (CC) | 2.1.105 | Anthropic CLI 编码 Agent |
| OpenClaw | 2026.4.12 | 开源多通道 AI 助手 |
| Hermes Agent | 0.8.0 | 自改进 AI Agent |

**统一模型**: `claude-sonnet-4-5-20250929` via `api.dbh.baidu-int.com`

## 评估类别 (4 × 25%)

1. **代码项目** — CLI 书签管理器 (SQLite + 模糊搜索 + pytest)
2. **浏览器操作** — 表单填写、数据提取、多步导航、截图总结
3. **网页监控** — GitHub Trending 报告、博客抓取、变化追踪
4. **真实交互** — GitHub Discussions、Dev.to 草稿、向 Trending 仓库提 PR

## 评分维度

正确性(30%) / 完整性(25%) / 质量(20%) / 效率(15%) / 自主性(10%)

## 使用

```bash
# Claude Code 执行任务
./scripts/eval-runner.sh cc task-1 claude --print --permission-mode bypassPermissions "Build a bmk CLI tool..."

# OpenClaw 执行任务 (从源码运行)
./scripts/eval-runner.sh openclaw task-1 bash -c 'cd /Users/lini03/baidu/clawdbot && npx tsx src/entry.ts agent --local --agent waiter -m "Build a bmk CLI tool..." --timeout 300'

# Hermes Agent 执行任务
./scripts/eval-runner.sh hermes task-1 hermes chat -q "Build a bmk CLI tool..." -Q --max-turns 30

# 验证代码项目
./scripts/verify-cat1.sh results/cc/cat1/

# 计算总分
python scripts/score-calculator.py
```

## 正确的调用命令

| Agent | 命令 |
|-------|------|
| CC | `claude --print --permission-mode bypassPermissions "<prompt>"` |
| OpenClaw | `cd /Users/lini03/baidu/clawdbot && npx tsx src/entry.ts agent --local --agent waiter -m "<prompt>" --timeout 300` |
| Hermes | `hermes chat -q "<prompt>" -Q --max-turns 30` |

## 目录结构

```
config/      — 三 Agent 配置说明
specs/       — 任务规格文档
scripts/     — 执行和验证脚本
results/     — 各 Agent 执行结果和日志
scoring/     — 评分表和 rubrics
reports/     — 最终对比报告
```
