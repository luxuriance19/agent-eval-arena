---
tags: [agent-eval, analysis, architecture, deep-dive]
date: 2026-04-15
cssclass: wide-page
---

# 执行差异根因分析 — 源码级深度对比

> 本文基于三个 Agent 的**源码**、**执行日志**和**工具配置**，解释为什么同一模型下表现差异如此显著。
> 关联报告: [[09-Comprehensive-Report]] | [[08-Final-Report]]

---

## 0. 核心结论先行

三个 Agent 的表现差异可以归结为 **5 个架构维度的根本性差异**：

```
差异维度            CC 得分影响    OC 得分影响    HA 得分影响
───────────────────────────────────────────────────────────
① 上下文管理策略    中性           -1.5 分        +0.5 分
② 工具选择策略      -0.3 分        -0.5 分        +0.8 分
③ 错误恢复机制      -1.0 分        -0.8 分        +0.3 分
④ 安全策略粒度      无影响         -0.5 分        无影响
⑤ 并发/会话模型     无影响         -1.0 分        无影响
───────────────────────────────────────────────────────────
净影响              -1.3 分        -4.3 分        +1.6 分
```

> 以上为定性估算，基于各因素对具体任务得分的实际影响推算。

### 各架构按任务类型的最佳可借鉴点

> 供脚手架搭建参考：每种架构在特定任务类型下展现了独到优势，以下按任务类别梳理值得复用的设计模式。

#### Cat1 代码项目 — 最佳实践

| 借鉴来源 | 优势设计 | 源码依据 | 建议复用方式 |
|---------|---------|---------|------------|
| **OC** | 极致生成速度 (179s) | 单轮工具链简洁：`write_file` → `exec bash` → `write_file`，无额外检查开销 | 代码生成类任务减少前置检查，信任模型首次输出 |
| **HA** | Python 3.9 兼容性自适应 | `prompt_builder.py` 中 MODEL-SPECIFIC GUIDANCE 检测运行环境版本 | 系统提示注入目标环境版本信息，让模型自动适配 |
| **CC** | PEP 604 现代类型注解 | 闭源但输出质量表明内部有 Python 风格指导 | 脚手架默认规则中预置 Python 现代风格指引 |

#### Cat2 浏览器操作 — 最佳实践

| 借鉴来源 | 优势设计 | 源码依据 | 建议复用方式 |
|---------|---------|---------|------------|
| **HA** | Bot 检测 → 自动策略切换 | `browser_tool.py`: 检测 Cloudflare/CAPTCHA 标题模式 → 注入警告到工具结果 → 模型自主切换 API-first | 浏览器工具返回值中增加反爬标记字段，系统提示指导模型在检测到标记时降级到 HTTP/RSS |
| **HA** | 快照自动精简 | `browser_tool.py`: 页面快照 >8000 tokens → LLM 自动精简摘要 | 浏览器工具对大页面结果做摘要压缩再返回，保护上下文空间 |
| **CC** | 创造性绕行 (Web Archive) | 执行日志：Cloudflare 拦截后自动想到 `web.archive.org` 缓存 | 系统提示中预置"备用数据源"列表（Web Archive、Google Cache、RSS） |
| **HA** | Session 隔离 | 每个任务独立浏览器实例，无跨任务状态污染 | 脚手架设计中每次浏览器任务 spawn 独立 context/session |

#### Cat3 网页监控 — 最佳实践

| 借鉴来源 | 优势设计 | 源码依据 | 建议复用方式 |
|---------|---------|---------|------------|
| **HA** | API-first 工具策略 | task-3a 直接 HTTP GET + 结构化解析 (139s vs CC 331s) | 监控类任务默认走 HTTP API 而非浏览器，仅在 API 失败时降级浏览器 |
| **HA** | 并行工具执行 | `run_agent.py`: `ThreadPoolExecutor(max_workers=8)` + 路径重叠检测 | 多 URL 抓取场景自动拆分并行执行，IO-bound 任务并发度 4-8 |
| **HA** | 失败透明记录 | task-3c: worldtime 连接重置后完整记录重试详情和失败原因，不编造数据 | 工具失败时返回结构化错误（含重试次数、错误码），系统提示要求"如实记录失败" |
| **OC** | worldtime 唯一成功 | 自动 compaction 后仍保持足够上下文重试 | 特定高价值端点可配置更高重试次数 + 更长超时 |
| **HA** | Unified diff 格式 | task-3c 变化追踪输出标准 diff 格式 | 报告模板预置 diff 格式指引，确保变化追踪输出可机器解析 |

#### Cat4 真实交互 — 最佳实践

| 借鉴来源 | 优势设计 | 源码依据 | 建议复用方式 |
|---------|---------|---------|------------|
| **CC** | `gh` CLI 深度集成 | task-4a/4c: 直接调用 `gh discussion create`、`gh repo fork`、`gh pr create` | 脚手架内置 `gh` CLI wrapper 工具，封装常用 GitHub 操作为原子工具 |
| **HA** | Discussion 内容质量 | task-4a: 结构化正文 300-500 字，评分与 CC 并列 8.85 | 系统提示预置"结构化写作模板"（摘要 → 方法 → 结论 → 下一步） |
| **CC** | PR 工作流最完整 | task-4c: fork → branch → 代码修改 → push 尝试（走得最远） | Git 工作流工具链：原子化 fork/branch/commit/push/PR，每步有校验 |
| **HA** | 错误分类+降级 | `error_classifier.py`: 12 类错误 × 恢复策略矩阵 | 所有外部交互工具统一使用错误分类器，429/401/timeout 各有专属恢复路径 |

#### 跨任务通用 — 架构级借鉴

| 借鉴来源 | 优势设计 | 建议复用方式 |
|---------|---------|------------|
| **HA** | 三层上下文纵深防御 | **必须复用**: ① 工具级截断 → ② 大结果持久化到磁盘（上下文只留摘要+路径）→ ③ 轮次级总预算（200K chars） |
| **HA** | 结构化压缩摘要 (10 字段) | 上下文压缩时生成包含 key_findings / files_modified / current_status 等标准字段的摘要，标记 "REFERENCE ONLY" |
| **HA** | 强制工具执行系统提示 | "You MUST use your tools to take action" — 防止模型空转描述而不执行 |
| **CC** | 无状态执行模式 | `--print` 每次调用独立进程，天然避免 session 锁/状态污染 — 适合批量任务调度 |
| **OC** | 模型故障转移链 | 多 provider 配置 + failover 机制 — 适合需要高可用的生产环境（需修复 context overflow 不进入 failover 的 bug） |
| **HA** | 指数退避 + 抖动 + 心跳 | `min(5 × 2^(attempt-1), 120) + jitter`，退避期间每 30s 心跳防网关超时 — 429 恢复最佳实践 |

#### 脚手架搭建优先级建议

```
优先级    借鉴项                          来源    预估收益
────────────────────────────────────────────────────────
P0       三层上下文纵深防御                 HA      消除 context overflow (+1.5 分)
P0       错误分类 + 分层恢复策略            HA      消除 429 即死 (+1.0 分)
P1       Bot 检测 → API-first 策略切换     HA      浏览器任务效率翻倍
P1       并行工具执行 + 路径重叠检测        HA      IO-bound 任务 2-4x 提速
P1       gh CLI 原子工具封装               CC      真实交互任务成功率提升
P2       无状态批量执行模式                 CC      避免 session 锁竞争
P2       模型故障转移链 (修复版)            OC      生产环境高可用
P2       结构化写作模板                    CC+HA   报告/Discussion 输出质量
P3       代码生成快速路径                   OC      减少前置检查开销
P3       --thinking 参数动态调控           OC 教训  避免思考块膨胀上下文
```

---

## 1. 上下文管理：三种截然不同的策略

这是导致 **OpenClaw 不稳定性** 的最大根因。

### 1.1 Hermes：三层纵深防御

```
源码: hermes-agent/tools/tool_result_storage.py
      hermes-agent/agent/context_compressor.py

┌─────────────────────────────────────────────────────────┐
│ Layer 1: 工具级截断                                      │
│   每个工具在返回结果前自行截断                              │
│   → 问题在源头解决                                       │
├─────────────────────────────────────────────────────────┤
│ Layer 2: 结果持久化 (maybe_persist_tool_result)           │
│   当单个结果超过阈值 → 写入临时文件                        │
│   上下文中只保留 <persisted-output> 预览 + 文件路径       │
│   模型后续用 read_file + offset/limit 按需读取            │
│   → 大结果永远不会撑爆上下文                              │
├─────────────────────────────────────────────────────────┤
│ Layer 3: 轮次级总预算 (enforce_turn_budget)               │
│   一轮所有工具结果 > 200K chars → 最大的结果溢出到磁盘     │
│   → 即使多个中等结果叠加也不会溢出                         │
└─────────────────────────────────────────────────────────┘

压缩触发: prompt_tokens >= context_length × 50%
压缩算法 (5 阶段):
  1. 裁剪旧工具结果 (>200 chars → "[cleared]")
  2. 保护头部 (系统提示 + 首轮交互, 永不压缩)
  3. 保护尾部 (~20K tokens 的最新消息)
  4. 中间部分 → 结构化摘要 (含 10 个标准字段)
  5. 迭代更新 (后续压缩更新已有摘要而非重建)

关键设计: 摘要标记为 "REFERENCE ONLY" 防止模型当作指令执行
```

**评估中的表现**: 10 个任务**零次**上下文溢出。三层防御确保大结果从未进入上下文。

### 1.2 OpenClaw：激进阈值 + 思考块膨胀

```
源码: clawdbot/src/agents/pi-embedded-runner/tool-result-context-guard.ts
      clawdbot/src/agents/pi-embedded-runner/run/preemptive-compaction.ts

┌─────────────────────────────────────────────────────────┐
│ 上下文防护 (tool-result-context-guard.ts)                │
│                                                         │
│ maxContextChars = contextWindowTokens × 4 × 0.9         │
│                                                         │
│ 单个工具结果最大占比: 50% 上下文窗口                       │
│ 默认最大活跃工具结果: 40,000 字符                         │
│                                                         │
│ 超出 → 抛出 "context overflow: estimated context size    │
│         exceeds safe threshold during tool loop"         │
│                                                         │
│ ⚠ 上下文溢出 **永远不触发模型故障转移**                    │
│   (代码 run.ts:814: if isLikelyContextOverflowError     │
│    → throw err, 不进入 fallback 路径)                    │
└─────────────────────────────────────────────────────────┘

致命问题: --thinking high 的影响
  ↓
  思考块保留在最新一轮助手消息中 (dropThinkingBlocks 只清除旧轮)
  ↓
  每次工具循环周期, 最新的思考块持续消耗上下文
  ↓
  tool-result-char-estimator.ts (106-107行):
    if (typed.type === "thinking") { chars += typed.thinking.length }
  ↓
  上下文快速逼近 90% 阈值 → 触发溢出
```

**评估中的实际表现**:

| 任务      | 溢出发生?           | 消息数     | 恢复结果       |
| ------- | --------------- | ------- | ---------- |
| task-2b | 是 (attempt 1/3) | 155 条消息 | 压缩后成功      |
| task-3a | 是               | —       | 首次失败，重试后成功 |
| task-3b | 是 (×2)          | —       | 两次失败，第三次成功 |

**日志证据** (`results/openclaw/task-2b.log`):
```
[context-overflow-diag] messages=155 error=Context overflow: estimated
context size exceeds safe threshold during tool loop.
[context overflow detected (attempt 1/3); attempting auto-compaction for
openai-completions/claude-sonnet-4-5-20250929
auto-compaction succeeded ... retrying prompt
```

### 1.3 Claude Code：黑盒但有效

CC 的上下文管理是闭源的，但从执行结果看：
- 10 个任务**零次**上下文溢出
- task-2d 的 1285s 长会话未溢出，说明有效的上下文管理
- 但缺乏 Hermes 的"结果持久化"机制——大结果直接留在上下文中

### 1.4 对比总结

```
                     Hermes              OpenClaw            CC
─────────────────────────────────────────────────────────────────
溢出次数              0                   4+                  0
防御层数              3 层                1 层+压缩            未知(有效)
大结果处理            持久化到磁盘         截断到 40K chars     未知
思考块影响            不使用 thinking      严重膨胀上下文        不适用
压缩质量              结构化 10 字段摘要   通用摘要+20%余量     未知
溢出后恢复            自动压缩3次          压缩3次,永不故障转移  未遇到

→ OC 的单层防护 + 思考块膨胀 = 上下文管理最脆弱
→ HA 的三层纵深 = 大结果永远不会进入上下文
```

---

## 2. 工具选择策略：API-First vs Browser-First

这是导致 **Hermes 效率最高**的关键因素。

### 2.1 task-2d 的三种策略对比（最能说明问题的案例）

任务: 从 OpenAI Blog 提取 5 篇最新文章 + 全文 + 截图 + 摘要

```
┌─ CC: Browser-First 策略 ─────────────────────────────────┐
│                                                           │
│  Step 1: 浏览器打开 openai.com/blog                       │
│     ↓ 成功 (但自动跳转到中文版)                             │
│  Step 2: 点击进入最新文章                                  │
│     ↓ Cloudflare Turnstile CAPTCHA 拦截!                  │
│  Step 3: 尝试 headed 模式                                 │
│     ↓ 仍然被拦截                                          │
│  Step 4: 创造性绕行 → web.archive.org 缓存版本             │
│     ↓ 成功, 但需要等待 Web Archive 加载                    │
│  Step 5: 提取内容 + 截图                                   │
│     ✓ 完成                                                │
│                                                           │
│  总耗时: 1285s    策略: 遇阻后创造性绕行                    │
└───────────────────────────────────────────────────────────┘

┌─ OC: Browser-First + SSRF 阻碍 策略 ─────────────────────┐
│                                                           │
│  Step 1: 内置浏览器尝试导航                                │
│     ↓ SSRF 策略阻止! (hostname-based navigation blocked)  │
│  Step 2: 切换到 agent-browser CLI                         │
│     ↓ Cloudflare 拦截                                     │
│  Step 3: 切换到 web_fetch HTTP API                        │
│     ↓ 成功获取内容                                        │
│  Step 4: 截图 + 提取                                      │
│     ✓ 完成                                                │
│                                                           │
│  首次: 24s 崩溃 (session lock)                             │
│  重试: 309s    策略: 被迫多次切换工具路径                    │
└───────────────────────────────────────────────────────────┘

┌─ HA: API-First 策略 ─────────────────────────────────────┐
│                                                           │
│  Step 1: 直接获取 RSS feed (openai.com/blog/rss.xml)     │
│     ↓ 获得 5 篇文章元数据 (无需浏览器!)                    │
│  Step 2: Jina Reader 镜像获取全文                         │
│     ↓ r.jina.ai/http://... 绕过 bot 检测                 │
│  Step 3: 生成本地 HTML 页面                               │
│  Step 4: 浏览器只用于截图本地页面                          │
│     ✓ 完成                                                │
│                                                           │
│  总耗时: 284s    策略: 完全避开反爬虫                       │
│  ← CC 的 4.5 倍速度                                       │
└───────────────────────────────────────────────────────────┘
```

**日志证据** (`results/hermes/task-2d.log`):
```
openai.com/blog returned bot-protection in this browser session,
so I extracted the recent posts from OpenAI's RSS feed and the
latest post text from a readable mirror of the article.
I still used browser automation to open an overview page, click
into the latest post, and capture the screenshots based on the
extracted content.
```

### 2.2 task-3a 的策略差异

任务: GitHub Trending 日/周/月 Top 10 + 交叉分析

```
Agent    耗时    策略                               效果
─────────────────────────────────────────────────────────
HA       139s   直接 HTTP 抓取 + 结构化解析         最快
OC       230s*  web_fetch API 调用                  中等(重试后)
CC       331s   浏览器自动化(DOM 抓取)              最慢

* OC 首次因 session lock 崩溃
```

### 2.3 源码层面的策略差异原因

**Hermes 的工具编排** (`run_agent.py`):
```
源码: hermes-agent/run_agent.py

工具选择完全由 LLM 决定 (ReAct 模式)
但系统提示中有关键指导:

  agent/prompt_builder.py → TOOL_USE_ENFORCEMENT_GUIDANCE:
  "You MUST use your tools to take action -- do not describe
   what you would do or plan to do without actually doing it."

  + SKILLS_GUIDANCE → 如果有匹配的 Skill, 必须加载
  + 浏览器工具的 bot 检测警告 (browser_tool.py):
    检测 Cloudflare/CAPTCHA 模式 → 自动警告模型
```

Hermes 的浏览器工具内置了 bot 检测（`browser_tool.py` 中检测 Cloudflare/CAPTCHA 页面标题模式），当检测到反爬时会主动警告模型，促使模型切换到 API-first 策略。

**OpenClaw 的工具路径冲突**:
```
源码: clawdbot/extensions/browser/ → 内置浏览器 (受 SSRF 策略)
      clawdbot/skills/agent-browser/ → 外部 CLI (不受 SSRF 策略)

两个浏览器工具并存, 但:
  - 内置浏览器的 SSRF 严格模式阻止 hostname 导航
  - agent-browser CLI 不受 SSRF 限制
  - 模型需要"试错"才能发现应该用哪个
  → 额外的工具切换开销
```

**CC 的浏览器偏好**:
CC 通过 agent-browser skill 调用浏览器，没有 SSRF 限制，但默认策略是 browser-first。遇到 Cloudflare 后需要创造性绕行（Web Archive），没有像 Hermes 那样的 bot 检测 → API 切换机制。

### 2.4 对效率分数的直接影响

```
task-2d 效率分:
  CC: 5/10  (1285s, Cloudflare 绕行耗时巨大)
  OC: 6/10  (309s 重试, 多次工具切换)
  HA: 8/10  (284s, API-first 一次完成)

task-3a 效率分:
  CC: 8/10  (331s, 浏览器方案可行但慢)
  OC: 6/10  (230s 重试, 首次 session lock 崩溃)
  HA: 9/10  (139s, 直接 HTTP 最高效)
```

---

## 3. 错误恢复机制：从源码看韧性

### 3.1 Hermes：12 类错误分类 + 分层恢复

```
源码: hermes-agent/agent/error_classifier.py
      hermes-agent/agent/retry_utils.py

classify_api_error() 分类管线 (优先级从高到低):
  1. Provider 特征识别 (thinking block 签名)
  2. HTTP 状态码 + 消息细化 (400/401/402/413/429/500/502/503/529)
  3. 错误码分类 (from body)
  4. 消息模式匹配 (billing vs rate_limit vs context_overflow vs auth)
  5. 传输层启发式 (timeout, connection reset)
  6. 服务器断连 + 大会话 = context overflow
  7. 兜底: unknown (retryable with backoff)

每个 ClassifiedError 携带恢复提示:
  { retryable, should_compress, should_rotate_credential, should_fallback }

恢复策略矩阵:
┌──────────────────┬────────────────────────────────────┐
│ 429 Rate Limit   │ 抖动退避 + 凭证池轮转               │
│ Context Overflow │ 压缩 (最多 3 次)                    │
│ 413 Payload Big  │ 压缩 + 重试                        │
│ 401/403 Auth     │ Provider 特定刷新                   │
│ Thinking Block   │ 剥离 reasoning_details (一次性)     │
│ 500/502/503      │ 抖动指数退避                        │
│ Timeout          │ 重建客户端 + 重试                   │
│ Model Not Found  │ 激活 fallback 模型                  │
│ Billing (402)    │ 凭证池轮转到下一个 API key           │
└──────────────────┴────────────────────────────────────┘

退避公式: min(5 × 2^(attempt-1), 120) + random jitter
重试上限: 3 次/API 调用
退避期间: 每 30s 发心跳防止网关超时
```

**评估中的表现**: task-3c 遇到 worldtimeapi.org 连接重置，Hermes 重试后完整记录了失败原因，没有编造数据：
```
# 日志证据 (results/hermes/task-3c.log):
"I attempted worldtimeapi.org with retries, but from this environment
the server consistently reset the connection. I recorded that failure
in both the report and raw JSON instead of fabricating data."
```

### 3.2 OpenClaw：模型故障转移但无细粒度退避

```
源码: clawdbot/src/agents/model-fallback.ts
      clawdbot/src/agents/failover-error.ts

错误分类 (FailoverReason):
  rate_limit (429) → 故障转移到下一个模型候选
  billing (402)    → 故障转移
  auth (401/403)   → 故障转移
  overloaded (503) → 故障转移
  context_overflow → ⚠ 永不故障转移, 直接重新抛出!
  model_not_found  → 故障转移

关键限制:
  - 429 处理: 不是退避重试, 而是直接切到另一个模型
    → 如果只配置了一个 provider, 进入冷却期
    → 冷却期内仅 30s 间隔探测 (MIN_PROBE_INTERVAL_MS = 30000)
  - context_overflow: 代码明确排除在故障转移之外
    (run.ts:814: if isLikelyContextOverflowError → throw)
    → 只能压缩恢复, 最多 3 次, 失败就彻底崩溃
```

**评估中的表现**: 因为只配置了一个 provider (`openai-completions`)，429 没有故障转移目标。context overflow 多次发生但压缩恢复不稳定。

### 3.3 Claude Code：429 = 即死

CC 是闭源的，但从日志看其 429 处理：

```
# results/cc/task-2c.log (完整日志内容):
API Error: Request rejected (429) · 当前分组上游负载已饱和，请稍后再试

# results/cc/task-3c.log (完整日志内容):
API Error: Request rejected (429) · 当前分组上游负载已饱和，请稍后再试

# results/cc/task-4c.log (2068s 后):
API Error: Request rejected (429) · 当前分组上游负载已饱和，请稍后再试
```

**三个任务的日志都只有一行错误信息**——没有工具调用记录、没有重试痕迹、没有退避。这说明 CC 在遇到 429 时**立即终止**，没有内置的退避重试机制（至少在 `--print` 非交互模式下）。

### 3.4 429 影响量化

```
CC 因 429 丢失的分数:
  task-2c: 首次失败, 重试成功 → 效率分 -4 (9→5)
  task-3c: 失败, 部分输出 → 正确性 -2, 完整性 -3, 效率 -3, 自主性 -3
  task-4c: 失败 → 已被 PR 任务本身难度掩盖

  估计 429 导致 CC 总分下降: ~0.8-1.0 分

如果 CC 有 Hermes 级别的退避重试:
  task-3c 可能从 6.95 → 8.5+
  task-2c 不需要手动重试 → 效率分 +2
  → CC 总分可能从 7.71 → 8.0+ (接近 Hermes)
```

---

## 4. 安全策略粒度：OC 的 SSRF 困境

### 4.1 SSRF 策略源码分析

```
源码: clawdbot/src/infra/net/ssrf.ts
      clawdbot/src/agents/tools/web-guarded-fetch.ts

两层检查:
  Layer 1 (hostname/IP): 阻止 localhost, .local, .internal, RFC 1918
  Layer 2 (DNS 钉扎): 解析后检查所有 IP 是否为私有

Web 工具获取模式:
  fetchWithWebToolsNetworkGuard() → withStrictGuardedFetchMode()
  → 严格模式: 所有 SSRF 检查 + DNS 钉扎
  → 没有 dangerouslyAllowPrivateNetwork 选项!

只有 withTrustedWebToolsEndpoint() 才允许私有网络
  → 仅用于操作员配置的特定端点, 不是通用 Web 工具
```

### 4.2 Task 2A 的实际影响

```
# OC 日志 (results/openclaw/task-2a.log):
[tools] browser failed: Navigation blocked: strict browser SSRF
policy requires an IP-literal URL because browser DNS rebinding
protections are unavailable for hostname-based navigation
raw_params={"action":"open","url":"https://demoqa.com/automation-practice-form"}
```

OC 的内置浏览器工具将 `demoqa.com` 视为潜在的 DNS 重绑定攻击向量——因为在浏览器环境中无法进行 DNS 钉扎验证。这导致了一连串连锁反应：

```
SSRF 阻止 demoqa.com
  ↓ 切换到 agent-browser CLI (不受 SSRF 策略)
  ↓ agent-browser 成功打开页面
  ↓ 但广告遮挡了提交按钮
  ↓ 需要关闭广告
  ↓ 页面刷新, 需要重新填写
  ↓ Subjects 下拉菜单没有成功填入
  ↓ 最终: 8/9 字段正确, Subjects 为空

耗时: 298s (vs CC 179s, HA 132s)
效率分: 5/10
正确性: 7/10 (Subjects 漏填)
```

**对比**: CC 和 HA 的浏览器工具都没有这种限制——直接导航到 `demoqa.com` 成功。

### 4.3 OC 的脚本预检限制

```
源码: 推测在 Pi SDK 的执行沙盒中

# OC 日志 (results/openclaw/task-3b-retry2.log):
[tools] exec failed: exec preflight: complex interpreter invocation
detected; refusing to run without script preflight validation. Use
a direct `python <file>.py` or `node <file>.js` command.
```

OC 拒绝执行 inline Python heredoc 脚本，要求先保存为文件再执行。这增加了额外步骤和延迟。

**Hermes 对比**: Hermes 的 `execute_code` 工具也有安全检查（检测危险命令如 `rm -rf`、SQL DROP），但允许 inline 脚本执行。在 task-4c 中，Hermes 因 `rm -rf` 被拒绝（合理的安全防护），但 inline Python 脚本不受限制。

---

## 5. 并发/会话模型：OC 的致命缺陷

### 5.1 Session File Locking

这是 OC 在 Cat3/Cat4 中表现最差的**真正根因**——不是模型能力问题，而是基础设施 bug。

```
# OC 日志 (多个任务重复出现):

results/openclaw/task-2d.log (24s, exit=1):
  Error: session file locked (timeout 10000ms): pid=XXXXX
  /Users/lini03/.openclaw/agents/waiter/sessions/
  fd1affbc-bc6d-4adf-bfaa-2e9a10872945.jsonl.lock

results/openclaw/task-3a.log (31s, exit=1):
  Error: session file locked (timeout 10000ms): pid=XXXXX
  (同一个 session 文件!)

results/openclaw/task-3b.log (31s, exit=1):
  Error: session file locked (timeout 10000ms): pid=XXXXX

results/openclaw/task-4a.log (23s, exit=1):
  Error: session file locked (timeout 10000ms): pid=XXXXX
```

**问题分析**:
```
所有 OC 代理实例共享同一个 session 文件:
  ~/.openclaw/agents/waiter/sessions/fd1affbc-...jsonl

当前一个进程未完全释放锁时:
  → 后续实例在 10s 超时后崩溃
  → 不是 context overflow, 不是模型问题
  → 纯粹的文件锁竞争

影响的任务: task-2d, task-3a, task-3b, task-3b-retry, task-4a
→ 5 个任务首次失败, 贡献了 OC "50% 首次成功率" 的大部分
```

**Hermes 对比**: Hermes 使用每任务独立的终端会话（通过 `ShellFileOperations` 绑定到任务的 terminal 环境），不存在跨任务的会话锁竞争。

**CC 对比**: CC 的 `--print` 模式是无状态的，每次调用是独立进程，没有 session 持久化，自然不存在锁竞争。

### 5.2 如果排除 session lock 影响

```
OC 实际因 session lock 失败的任务: task-2d, task-3a, task-3b(×2), task-4a
假设这些任务都首次成功（取重试成功的分数）:

原始 OC 总分: 5.95
去除 session lock 影响后的估算:
  task-4a: 假设与 CC/HA 类似 → ~8.5 分
  其他任务: 取实际重试成功的分数

Cat4 调整后: 4a=8.5, 4b=skip, 4c=0 → 加权 ~4.86
  (原来 0.00 → 4.86, 差值 +4.86)
Cat4 对总分影响: +4.86 × 0.25 = +1.22

调整后 OC 总分: ~7.17 (vs 原来 5.95)
→ session lock 问题单独造成了 ~1.2 分的损失!
```

---

## 6. 并行工具执行：隐藏的效率倍增器

### 6.1 Hermes 的并行工具执行

```
源码: hermes-agent/run_agent.py (lines 6833-7136)

_should_parallelize_tool_batch():
  NEVER_PARALLEL = {"clarify"}           # 交互式工具禁止并行
  PARALLEL_SAFE  = {"read_file", "search_files", "web_search",
                     "web_extract", "session_search", ...}
  PATH_SCOPED    = {"read_file", "write_file", "patch"}

  路径重叠检测 (_paths_overlap):
    如果两个文件操作目标不同路径 → 可以并行
    如果目标同一子树 → 强制串行

  执行: ThreadPoolExecutor(max_workers=8)
```

**实际效果**: 当 Hermes 需要同时读取多个文件或同时进行多个 web 搜索时，最多 8 个工具调用并行执行。这在 task-3a（需要抓取日/周/月三个页面）中显著提升了效率。

### 6.2 OpenClaw 和 CC 的情况

OC 的 Pi SDK 框架内部也支持工具并行，但日志显示其工具调用主要是串行的——可能是因为浏览器操作本质上是串行的（同一个浏览器实例）。

CC 在 `--print` 模式下的并行能力未知（闭源），但从其整体效率看，在非 429 任务上表现合理。

---

## 7. 系统提示的关键差异

### 7.1 Hermes：强制执行 + 技能加载

```
源码: hermes-agent/agent/prompt_builder.py

关键指导:
  TOOL_USE_ENFORCEMENT_GUIDANCE:
    "You MUST use your tools to take action -- do not describe
     what you would do or plan to do without actually doing it."

  SKILLS_GUIDANCE:
    "If a skill matches or is even partially relevant to your
     task, you MUST load it with skill_view(name)."

  MODEL-SPECIFIC GUIDANCE (for OpenAI-compatible):
    - 工具持久化要求
    - 必须用工具验证事实
    - 前置条件检查
    - 缺失上下文处理

  浏览器 Bot 检测:
    browser_tool.py 检测 Cloudflare/CAPTCHA 模式
    → 自动在工具结果中注入警告
    → 促使模型切换到非浏览器策略
```

这些指导确保了模型：
1. 不会"空转"（说了不做）
2. 遇到 bot 检测自动切换策略
3. 匹配 Skill 时强制加载最佳实践

### 7.2 OpenClaw：通用 + 扩展驱动

```
源码: clawdbot/src/agents/pi-embedded-runner/run/attempt.ts

系统提示组装:
  1. buildEmbeddedSystemPrompt() → 基础提示
  2. Provider 特定文本
  3. 引导文件注入 (AGENTS.md, CLAUDE.md)
  4. 技能提示注入
  5. 上下文引擎维护提示
  6. 通道能力提示
  7. 心跳提示

→ 没有发现等价于 Hermes 的 TOOL_USE_ENFORCEMENT
→ 没有浏览器 bot 检测 → 自动策略切换机制
```

### 7.3 差异影响

```
task-2d 策略选择差异的根因:
  HA: 浏览器工具检测到 bot 保护 → 工具结果注入警告 → 模型自主切换到 RSS
  CC: 浏览器遇到 CAPTCHA → 无自动提示 → 模型自己想到 Web Archive (慢)
  OC: 浏览器被 SSRF 阻止 → 强制切换 → 但没有 API-first 提示 → 走了更多弯路
```

---

## 8. 综合根因图谱

```
┌─────────────────────────────────────────────────────────────┐
│                    CC (7.71)                                 │
│                                                             │
│  ✓ 优势                        ✗ 劣势                      │
│  · 工具链成熟, 无 SSRF/lock 问题  · 429 = 即死, 零恢复能力  │
│  · 报告质量高 (中文 Summary)     · Browser-first 策略偏慢   │
│  · --print 模式无状态, 无锁竞争  · 无 bot 检测→策略切换     │
│                                                             │
│  核心瓶颈: API 代理的 429 rate limit                        │
│  如果修复: +0.8~1.0 分 → 7.71 → ~8.5 (可能超 HA)          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   OC (5.95)                                  │
│                                                             │
│  ✓ 优势                        ✗ 劣势                      │
│  · 代码生成速度最快 (task-1)     · Session file lock (致命)  │
│  · 模型故障转移链                · --thinking high 膨胀上下文│
│  · 自修复 context overflow      · SSRF 阻止 hostname 导航  │
│  · worldtime 唯一成功           · 脚本预检拒绝 inline 执行  │
│                                                             │
│  核心瓶颈: session lock + context overflow                  │
│  如果修复 lock: +1.2 分 → 5.95 → ~7.17                     │
│  如果同时修复 context: → ~7.5+                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   HA (7.84)                                  │
│                                                             │
│  ✓ 优势                        ✗ 劣势                      │
│  · 三层上下文防御 (零溢出)       · task-1 最慢 (343s)       │
│  · 12 类错误分类+分层恢复       · max-turns 30 限制 task-4c │
│  · API-first 策略 (bot 检测)    · 权限系统偶尔误拦          │
│  · 并行工具 (8 线程)            · (自进化未触发, 非劣势)    │
│  · 强制工具执行系统提示          │                          │
│                                                             │
│  核心优势: 架构设计全面, 无系统性弱点                        │
│  主要改进空间: 代码生成速度 + max-turns 提升                │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. 各工具配置对执行结果的具体影响

### 9.1 agent-browser 的不同集成方式

```
┌──────────┬───────────────────────────────────────────────┐
│  Agent   │ 浏览器工具集成方式                               │
├──────────┼───────────────────────────────────────────────┤
│  CC      │ agent-browser skill (通过 Bash 调用 CLI)       │
│          │ · 无 SSRF 限制                                │
│          │ · 无 bot 检测反馈                              │
│          │ · 截图输出直接到文件系统                         │
├──────────┼───────────────────────────────────────────────┤
│  OC      │ 双路径:                                       │
│          │ ① 内置 browser ext (Pi SDK 原生工具)           │
│          │   · 受 SSRF 严格策略                           │
│          │   · 工具结果受框架截断管理                       │
│          │   · 在上下文内运行 (占用上下文空间)              │
│          │ ② agent-browser skill (通过 Bash CLI)          │
│          │   · 不受 SSRF 限制                             │
│          │   · 结果作为 Bash stdout, 受 Bash 截断         │
│          │   · 需要模型"发现"应该用这个而不是①             │
├──────────┼───────────────────────────────────────────────┤
│  HA      │ agent-browser tool (subprocess 调用 CLI)       │
│          │ · 无 SSRF 限制 (非 cloud mode)                 │
│          │ · Bot 检测: 自动检查页面标题中的 Cloudflare 模式│
│          │ · 快照摘要: >8000 tokens 自动 LLM 精简         │
│          │ · Secret 过滤: URL 中的 API key 自动脱敏        │
│          │ · 结果持久化: 大快照自动落盘                     │
│          │ · Session 隔离: 每个任务独立浏览器实例           │
└──────────┴───────────────────────────────────────────────┘
```

### 9.2 `--thinking high` 对 OC 的具体影响

```
OpenClaw 启动命令:
  node openclaw.mjs agent --local --agent waiter -m "..." --thinking high

--thinking high 的连锁效应:
  ① 每次 LLM 回复生成大型思考块 (可能数千 tokens)
  ② thinking 块保留在最新助手消息中 (dropThinkingBlocks 仅清旧)
  ③ 压缩时也使用 reasoning: "high" → 压缩本身消耗更多 token
  ④ char estimator 将思考块计入上下文大小估算
  ⑤ 上下文更快逼近 90% 阈值
  ⑥ 更频繁触发 context overflow

如果改用 --thinking off 或 --thinking low:
  → 上下文膨胀速度大幅降低
  → context overflow 频率可能从 4+ 次降到 0-1 次
  → OC 的 Cat3 表现可能提升显著
```

### 9.3 defuddle 的使用差异

```
defuddle v0.15.0 — 网页正文提取工具

CC:  通过 Bash 调用 `defuddle parse --markdown <url>`
     → 用于博客/文档页面的正文提取
     → 适用场景: task-3b (Pragmatic Engineer 博客)

OC:  通过内置 web_fetch + 自有 HTML 解析
     → 不直接使用 defuddle
     → HTML 解析结果可能较大, 占用更多上下文

HA:  通过 web_extract 工具 (内部可能封装了 defuddle 或类似)
     → 结合 Jina Reader 镜像 (r.jina.ai) 获取 Markdown
     → 更轻量的结果, 更少的上下文占用
```

---

## 10. 如果消除各自瓶颈后的理论排名

```
场景 A: 当前状态
  #1 Hermes  7.84
  #2 CC      7.71
  #3 OC      5.95

场景 B: CC 修复 429 退避
  #1 CC      ~8.5   (+0.8)   ← 可能反超 Hermes
  #2 Hermes  7.84
  #3 OC      5.95

场景 C: OC 修复 session lock + 降低 thinking
  #1 Hermes  7.84
  #2 OC      ~7.5   (+1.5)
  #3 CC      7.71

场景 D: 三者都修复各自最大瓶颈
  #1 CC      ~8.5   (修复 429)
  #2 Hermes  ~8.2   (提升 max-turns)
  #3 OC      ~7.5   (修复 lock + thinking)
```

**结论**: 当前排名中，Hermes 的领先地位**来自架构的全面性**——没有系统性弱点。CC 的单一弱点（429 无恢复）如果修复，其底层能力实际上可能是三者中最强的。OC 的问题最多，但多数是基础设施层面可修复的 bug，而非架构设计缺陷。

---

*分析基于: hermes-agent v0.8.0 源码 · clawdbot v2026.4.12 源码 · CC v2.1.105 执行日志*
*数据来源: /Users/lini03/baidu/agent-eval-arena/results/ 全部执行日志和输出文件*
