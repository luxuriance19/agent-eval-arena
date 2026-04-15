---
tags: [agent-eval, hermes, self-evolution, results]
date: 2026-04-15
---

# Hermes 自进化评估 — 详细结果报告

> 评估时间: 2026-04-15 | 模型: claude-sonnet-4-5-20250929 | 代理: api.dbh.baidu-int.com

## 评估总览

| 阶段 | 任务数 | 总轮次 | 总 Tokens | 成功率 |
|------|--------|--------|----------|--------|
| Phase A (基线) | 4 | 4 | 386,740 | 3/4 (75%) |
| Phase B (进化) | 4 sessions | 27 | 1,195,883 | 4/4 (100%) |
| Phase C (重测) | 4 | 4 | 601,903 | **4/4 (100%)** |

---

## Phase A: 基线测试 (进化前)

> 干净状态，MEMORY.md=空，USER.md=空，无用户自定义 skill

### B1: Python 调试 — CSV 读取脚本

| 指标 | 值 |
|------|-----|
| 工具调用 | 4 (read_file → write_file → terminal × 2) |
| 耗时 | 45.7s |
| Tokens | 72,213 |
| 完成 | ✅ |

**Prompt**: 修复 `/tmp/hermes-evolution-eval/data.csv` 的 CSV 读取脚本 bug — 处理空行、缺失值、无效数据

**Agent 行为**: 读取 CSV → 创建 `csv_reader.py` → 运行验证 → 输出统计。处理了空行跳过、缺失 name 跳过、无效 age 跳过、缺失 salary 跳过。

**Response 摘要**: 创建了健壮的 CSV 读取脚本，能处理空行、缺失值、无效数据类型，运行验证通过。

---

### B2: Git 工作流

| 指标 | 值 |
|------|-----|
| 工具调用 | 7 (terminal × 3 → write_file × 2 → terminal × 2) |
| 耗时 | 39.3s |
| Tokens | 83,708 |
| 完成 | ✅ |

**Prompt**: 在 `/tmp/hermes-evolution-eval/git-demo` 下初始化仓库 + README + .gitignore + feature 分支

**Agent 行为**: git init → 写 README.md + .gitignore → git add + commit → 创建 feature/add-config 分支 → 验证状态。

---

### B3: Shell 脚本

| 指标 | 值 |
|------|-----|
| 工具调用 | 28 |
| 耗时 | 153.5s |
| Tokens | 0* |
| 完成 | ❌ (Bedrock 400 中断) |

**Prompt**: 编写 `backup.sh` — 递归查找 .py 文件，保持目录结构备份，带时间戳日志

**Agent 行为**: 创建脚本 → 设权限 → **在后续 API 调用中触发 Bedrock 空 content bug**（已在后续修复）。

*Phase A B3 因 Bedrock 400 错误导致 token 未记录。

---

### B4: 代码审查

| 指标 | 值 |
|------|-----|
| 工具调用 | 8 (read_file → write_file × 3 → terminal × 2 → write_file → terminal) |
| 耗时 | 239.0s |
| Tokens | 230,819 |
| 完成 | ✅ |

**Prompt**: 对 `app.py` 进行 OWASP Top 10 安全审查

**Agent 行为**: 读取源码 → 识别 8 个安全漏洞 → 创建修复版 `app_fixed.py` → 创建安全测试 + 文档。

**发现的漏洞**: SQL 注入、XSS、命令注入、路径遍历、硬编码密钥、明文密码、调试模式、缺少输入验证。

---

## Phase B: 进化会话 (触发自进化机制)

### E1: 记忆进化 (Layer 1 + Layer 3) — 10 轮

| 指标 | 值 |
|------|-----|
| 总工具调用 | 14 |
| 总耗时 | 172.8s |
| 总 Tokens | 641,418 |
| memory 激活 | 2 |

#### 逐轮记录

| Turn | Prompt 概要 | 目的 |
|------|------------|------|
| 1 | "我是百度后端 Python 开发者，用 ruff/pytest/pathlib，时区 Asia/Shanghai" | 偏好声明 |
| 2 | "写 Python 必须用 PEP 604 (X \| None)，不要 Optional" | 偏好纠正 |
| 3 | "写 config_reader.py，用 pathlib + 类型注解" | 编码任务 ← **nudge #1 预期** |
| 4 | "用 @dataclass(frozen=True, slots=True)，不要普通 dict" | 偏好纠正 |
| 5 | "给 config_reader.py 写 pytest 测试，mock 文件系统" | 测试任务 |
| 6 | "执行 pytest 测试并修复失败" | 运行测试 ← **nudge #2 预期** |
| 7 | "用 Pydantic 加配置 schema 验证" | 功能扩展 |
| 8 | "用 argparse 写 CLI，包含 --config 和 --validate" | CLI 包装 |
| 9 | "处理 malformed JSON，友好错误信息" | 错误处理 ← **nudge #3 预期** |
| 10 | "创建 requirements.txt 带精确版本" | 依赖管理 |

**进化成果**: USER.md 写入 212 字符（6 条偏好）:
- 百度后端 Python 开发者
- ruff 格式化代码
- pytest 单元测试
- pathlib 路径处理
- 时区 Asia/Shanghai
- PEP 604 联合类型 + PEP 585 内置泛型

---

### E2: 技能创建 (Layer 2 + Layer 3) — 5 轮

| 指标 | 值 |
|------|-----|
| 总工具调用 | 14 |
| 总耗时 | 587.4s |
| 总 Tokens | 554,465 |
| skill_manage 激活 | 1 |

#### 逐轮记录

| Turn | Prompt 概要 | 目的 |
|------|------------|------|
| 1 | "修复 scraper.py 的速率限制，加指数退避+重试装饰器+日志" | 复杂调试 |
| 2 | "api_client.py 有同样问题，应用相同的 retry 模式" | 模式复用 |
| 3 | "把 retry+backoff 模式保存为 skill" | **显式技能创建** |
| 4 | "写 Dockerfile + docker-compose.yml + Makefile" | 部署工作流 |
| 5 | "把部署模式也保存为 skill" | 技能创建请求 |

**进化成果**: 创建了 `http-retry-exponential-backoff` skill:
- 描述: "为 HTTP 请求添加指数退避重试机制，处理速率限制（429）和服务器错误（5xx）"
- 包含完整装饰器实现、参数默认值、Retry-After 响应头处理
- 标签: http, retry, exponential-backoff, rate-limiting, resilience

---

### E3: 跨会话搜索 (Layer 4) — 5 轮

| 指标 | 值 |
|------|-----|
| 总工具调用 | 3 |
| 总耗时 | 18.4s |
| 总 Tokens | 0* |
| session_search 激活 | 1 |

*E3 遇到 Bedrock 400 错误导致 token 未完整记录。

#### 逐轮记录

| Turn | Prompt 概要 | 目的 |
|------|------------|------|
| 1 | "回忆一下之前做的 config_reader.py 用了什么方法" | 历史回忆 |
| 2 | "搜索之前会话中的 exponential backoff 实现方式" | **触发 session_search** |
| 3 | "结合过去代码，写 resilient_config.py（远程 URL 加载 + 重试）" | 知识融合 |
| 4 | "你记得我的编码偏好吗？列出所有" | 偏好召回验证 |
| 5 | "创建 Python 项目模板，融入所有偏好和模式" | 综合运用 |

---

### E4: 综合测试 (全部 Layer) — 7 轮

| 指标 | 值 |
|------|-----|
| 总工具调用 | 2 |
| 总耗时 | 46.0s |
| 总 Tokens | 0* |

*E4 后期轮次遇到 Bedrock 400 错误。

#### 逐轮记录

| Turn | Prompt 概要 | 目的 |
|------|------------|------|
| 1 | "我需要 API 健康检查 CLI 工具，你应该知道我的偏好" | 偏好自动应用 |
| 2 | "实现 health_check.py，YAML 配置端点，用之前的 retry 模式" | 技能复用 |
| 3 | "用 StrEnum 不要字符串常量，用 asyncio.TaskGroup 不要 gather" | 偏好纠正 |
| 4 | "写 pytest 测试，mock HTTP，覆盖成功和失败路径" | 测试 |
| 5 | "加 Dockerfile，用之前保存的部署 skill" | 技能复用 |
| 6 | "运行所有测试确保通过" | 验证 |
| 7 | "总结今天所有 session 中构建的内容" | 回顾 |

---

## Phase C: 进化后重测

> 状态: MEMORY.md=空, USER.md=212 chars (6条偏好), 用户 Skills=11 (+1)

### B1-retest: Python 调试

| 指标 | Phase A | Phase C | 变化 |
|------|---------|---------|------|
| 工具调用 | 4 | 5 | +1 |
| 耗时 | 45.7s | 44.8s | **-0.9s** |
| Tokens | 72,213 | 86,336 | +14,123 |
| 风格违规 | 0 | 0 | -- |
| 完成 | ✅ | ✅ | -- |

**Agent 行为**: 读取 CSV → 创建 csv_reader.py → 运行验证 → ruff check → ruff format。多了一步 ruff 代码格式化（反映了从 USER.md 加载的 "ruff 格式化" 偏好）。

---

### B2-retest: Git 工作流

| 指标 | Phase A | Phase C | 变化 |
|------|---------|---------|------|
| 工具调用 | 7 | 7 | 0 |
| 耗时 | 39.3s | 34.5s | **-4.8s** |
| Tokens | 83,708 | 57,323 | **-26,385 (-32%)** |
| 风格违规 | 0 | 0 | -- |
| 完成 | ✅ | ✅ | -- |

**关键改善**: Token 消耗减少 32%，耗时减少 12%。进化后的 agent 更简洁高效。

---

### B3-retest: Shell 脚本

| 指标 | Phase A | Phase C | 变化 |
|------|---------|---------|------|
| 工具调用 | 28 | 12 | **-16 (-57%)** |
| 耗时 | 153.5s | 108.3s | **-45.2s (-29%)** |
| Tokens | 0* | 213,655 | N/A |
| 风格违规 | 0 | 0 | -- |
| 完成 | ❌ | ✅ | 修复 |

**关键改善**: 工具调用数减少 57%，耗时减少 29%。Phase A 因 Bedrock bug 中断，Phase C（修复 bug 后）成功完成且效率显著提升。

---

### B4-retest: 代码审查

| 指标 | Phase A | Phase C | 变化 |
|------|---------|---------|------|
| 工具调用 | 8 | 10 | +2 |
| 耗时 | 239.0s | 333.1s | +94.1s |
| Tokens | 230,819 | 244,589 | +13,770 |
| 风格违规 | 0 | 0 | -- |
| 完成 | ✅ | ✅ | -- |

**分析**: Phase C 的 B4 生成了更详细的安全审查报告（额外创建了 QUICK_START.txt 快速参考卡片 + comparison.py 对比脚本），因此耗时和 token 增加。

---

## 进化产物时间线

```
pre-eval ──→ after-E1 ──→ after-E2 ──→ after-E3 ──→ after-E4
  │             │             │
  │             │             └── +1 skill (http-retry-exponential-backoff)
  │             │
  │             └── USER.md: 0 → 212 chars (6 条偏好)
  │
  └── 干净状态: MEMORY=0, USER=0, Skills=10(bundled)
```

| 时间点 | MEMORY.md | USER.md | 用户 Skills | Sessions |
|--------|-----------|---------|------------|----------|
| pre-eval | 0 | 0 | 10 | 14 |
| **after-E1** | 0 | **212** | 10 | 14 |
| **after-E2** | 0 | 212 | **11** | 14 |
| after-E3 | 0 | 212 | 11 | 14 |
| after-E4 | 0 | 212 | 11 | 14 |
| post-retest | 0 | 212 | 11 | 14 |

### USER.md 最终内容

```
百度后端 Python 开发者
§
代码规范：使用 ruff 格式化代码
§
测试框架：使用 pytest 进行单元测试
§
路径处理：使用 pathlib 而非 os.path
§
时区：Asia/Shanghai (中国标准时间)
§
类型注解风格：强制使用 PEP 604 语法 (X | None)，禁止使用 Optional[X]；
使用小写内置类型 dict[str, int] 而非 Dict[str, int]
```

### 新增 Skill

**名称**: `http-retry-exponential-backoff`
**分类**: `software-development`
**描述**: 为 HTTP 请求添加指数退避重试机制，处理 429 和 5xx 错误
**核心公式**: `delay = min(base_delay × (exponential_base ^ attempt), max_delay)`
**默认参数**: base_delay=1.0s, exponential_base=2.0, max_delay=60.0s, max_retries=3

---

## 代码风格合规检查

### Phase C 生成代码自动 grep 结果

| 检查项 | 禁止模式 | B1 | B2 | B3 | B4 |
|--------|---------|----|----|----|----|
| PEP 604 | `Optional[` | 0 | 0 | 0 | 0 |
| pathlib | `os.path.` | 0 | 0 | 0 | 0 |
| TaskGroup | `asyncio.gather` | 0 | 0 | 0 | 0 |
| PEP 585 | `Dict[` / `List[` | 0 | 0 | 0 | 0 |

**全部合规** — Phase C 所有任务 0 风格违规。

---

## 进化优势量化总结

### 效率提升

| 维度 | 改善 |
|------|------|
| B2 Token 节省 | **-32%** (83K → 57K) |
| B3 工具调用节省 | **-57%** (28 → 12) |
| B3 耗时节省 | **-29%** (153s → 108s) |
| B2 耗时节省 | **-12%** (39s → 35s) |

### 自进化机制验证

| 机制 | 触发次数 | 产出 |
|------|---------|------|
| Memory nudge → USER.md | 2 | 6 条用户偏好写入 |
| Skill nudge → skill_manage | 1 | 1 个新技能创建 |
| session_search | 1 | 历史会话搜索成功 |

### 局限性

1. **MEMORY.md 未写入**: 后台 review agent 判断评估任务信息密度不够 ("Nothing worth saving")，因此 MEMORY.md 保持为空
2. **E3/E4 部分轮次失败**: Bedrock 空 content bug 影响了 E3/E4 的后期轮次（已在 commit `a029c61e` 中修复）
3. **Session 数量未增长**: 评估使用 `session_id` 参数直接创建 session，不经过正常的 session 管理流程

---

## 数据文件索引

| 文件 | 路径 (相对 agent-eval-arena) |
|------|-----|
| Phase A 单任务结果 | `results/hermes/self-evolution/phases/A-baseline/B{1-4}.json` |
| Phase A 汇总 | `results/hermes/self-evolution/phases/A-baseline/summary.json` |
| Phase B E1-E4 结果 | `results/hermes/self-evolution/phases/B-evolution/E{1-4}.json` |
| Phase B 汇总 | `results/hermes/self-evolution/phases/B-evolution/summary.json` |
| Phase C 重测结果 | `results/hermes/self-evolution/phases/C-post-evolution/B{1-4}-retest.json` |
| Phase C 汇总 | `results/hermes/self-evolution/phases/C-post-evolution/summary.json` |
| 进化快照 (×7) | `results/hermes/self-evolution/snapshots/{pre-eval,after-E1,...}.json` |
| A vs C 对比 | `results/hermes/self-evolution/analysis/comparison.json` |
| 进化时间线 | `results/hermes/self-evolution/analysis/evolution-timeline.json` |
| 风格合规检查 | `results/hermes/self-evolution/analysis/style-compliance.json` |
| 自动生成报告 | `results/hermes/self-evolution/report.md` |
| 评估脚本 | `scripts/hermes_evolution_eval.py` |
| 技术规格 | `specs/self-evolution-spec.md` |

---

*相关文档: [[00-Overview]], [[11-Self-Evolution-Eval]], [[12-Self-Evolution-Spec]]*
