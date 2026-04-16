---
tags: [agent-eval, hermes, self-evolution, v2, statistical-analysis]
date: 2026-04-16
---

# Hermes 自进化 V2 — 实验分析

> 生成时间: 2026-04-16 | 模型: claude-sonnet-4-5-20250929 | N=5 | 总执行: 60 次

**前置文档**: [[11-Self-Evolution-Eval]] [[12-Self-Evolution-Spec]] [[13-Self-Evolution-Results]]

---

## 一、实验概述

V2 采用 **反默认偏好**（模型默认不会选择的库/模式）+ **N=5 重复** + **三组控制变量** 设计。核心问题：Hermes 的自进化机制（记忆 + 技能 + 后台审查）对 agent 的行为和能力产生了怎样的影响？

| 组 | 配置 | system prompt 内容 |
|----|------|-------------------|
| G1-control | `skip_memory=True` | 仅 base_prompt |
| G2-fresh | 正常启动，空白记忆 | base_prompt + 空 USER.md + 记忆框架 |
| G3-evolved | 正常启动，训练后 | base_prompt + USER.md(470c) + Skill 索引(~430c) + mandatory 强制加载指令 |

---

## 二、进化产生了什么

Phase B 训练（20 轮对话）产出三类产物：

### 2.1 USER.md（470 chars）

nudge 在 E1 偏好训练中每 3 轮触发后台 review agent，review agent 将用户声明的编码偏好归类为「用户画像」写入 USER.md（而非 MEMORY.md 工作笔记），语义区分正确。内容为 8 条「正面指令 + 反面禁止」规范。

### 2.2 Skill `httpx-retry-pattern`（18,009 chars）— 一个反面教材

E2 技能训练中，Turn 2 产生了 23 次工具调用，触发 Skill Nudge（阈值=5），后台 review agent 自动创建了此 Skill。

**核心问题：87% 是原始 Python 代码**。18,009 chars 中包含 20 个代码块，合计 15,676 chars（87%）的 Python 源码——constants.py 全文、api_client.py 全文、测试代码、使用示例、demo 脚本。非代码部分仅 2,333 chars（13%）。这不是一份「技能模板」，而是一个代码仓库的 dump。

对比理想的 Skill 形态：一份 500 chars 的精炼摘要（函数签名 + 核心参数 + 关键约束 + 常见陷阱）完全够用。review agent 没有体积/质量引导，优化目标是「完整性」而非「可用性」，导致产出物膨胀了 36 倍。

### 2.3 MEMORY.md（空）

训练内容是偏好声明和编码任务，nudge 的 review prompt 将其导向了 USER.md 而非 MEMORY.md。

---

## 三、实验数据

### 3.1 任务完成率

| Group      |  T1 健康检查   |  T2 格式转换  |  T3 短链服务  |  T4 测试套件  |   总体    |
| ---------- | :--------: | :-------: | :-------: | :-------: | :-----: |
| G1-control | 2/5 (40%)  | 0/5 (0%)  | 3/5 (60%) | 0/5 (0%)  | **25%** |
| G2-fresh   | 5/5 (100%) | 0/5 (0%)  | 4/5 (80%) | 1/5 (20%) | **50%** |
| G3-evolved |  0/5 (0%)  | 1/5 (20%) | 2/5 (40%) | 2/5 (40%) | **25%** |

### 3.2 偏好合规率（仅统计适用任务）

| 偏好 | G1 | G2 | G3 |
|------|:--:|:--:|:--:|
| parametrize | 0% | 0% | **100%** |
| msgspec | 0% | 0% | 20% |
| TOML | 0% | 0% | 13% |
| httpx | 50% | 0% | 20% |
| loguru | 50% | 0% | 20% |
| Result 模式 | 0% | 0% | 0% |
| click | 20% | 0% | 0% |
| constants.py | 27% | 27% | 20% |

### 3.3 统计检验

| 对比 | p 值 | Cliff's delta |
|------|------|---------------|
| G1 vs G3 (T4) | **0.002** | 1.0 (large) |
| G2 vs G3 (T4) | **0.031** | 1.0 (large) |
| G1 vs G3 (总体合规) | 0.069 | 0.23 (small) |

### 3.4 逐 Run 明细

| Group | Task |   run-1   |   run-2   |   run-3   |   run-4   |   run-5   |
| ----- | ---- | :-------: | :-------: | :-------: | :-------: | :-------: |
| G1    | T1   |   F(1)    |   F(3)    | **T(32)** | **T(25)** |   F(2)    |
| G1    | T2   |   F(2)    |   F(2)    |   F(1)    |   F(0)    |   F(0)    |
| G1    | T3   |   F(1)    |   F(2)    | **T(18)** | **T(19)** | **T(22)** |
| G1    | T4   |   F(5)    |   F(4)    |   F(4)    |   F(3)    |   F(3)    |
| G2    | T1   | **T(25)** | **T(22)** | **T(26)** | **T(36)** | **T(19)** |
| G2    | T2   |   F(1)    |   F(0)    |   F(0)    |   F(1)    |   F(0)    |
| G2    | T3   | **T(29)** | **T(23)** |   F(2)    | **T(33)** | **T(27)** |
| G2    | T4   |   F(5)    |   F(4)    |   F(4)    | **T(4)**  |   F(4)    |
| G3    | T1   |   F(2)    |   F(1)    |   F(1)    |   F(2)    |   F(2)    |
| G3    | T2   |   F(1)    |   F(1)    |   F(2)    |   F(3)    | **T(23)** |
| G3    | T3   | **T(24)** | **T(25)** |   F(2)    |   F(2)    |   F(2)    |
| G3    | T4   | **T(21)** | **T(16)** |   F(7)    |   F(7)    |   F(6)    |

T=完成, F=未完成, 括号=tool_call_count。成功运行通常 16-36 次工具调用，失败运行 0-7 次。

---

## 四、可借鉴之处

### 4.1 USER.md 画像机制：轻量、有效、低成本

USER.md 是本实验中效果最清晰的进化产物。

- **体积小**（470B），对 context window 的开销可忽略
- **语义精准**：nudge 的 review agent 正确将偏好声明归类为用户画像（USER.md）而非工作笔记（MEMORY.md），体现了 target 参数设计的合理性
- **效果显著**：parametrize 偏好从 G1/G2 的 0% 提升到 G3 的 100%（p=0.002）；TOML、msgspec 从 0% 提升到 13%/20%
- **不干扰完成率**：470B 的注入量不会显著挤占 context

**借鉴点**：用户画像作为 system prompt 的轻量注入，是改变模型行为的高性价比手段。关键在于保持小体量（Hermes 上限 1,375 chars）和高信息密度。

### 4.2 Nudge 机制：后台审查 + LLM 驱动的分类

Hermes 的 nudge 设计有几个值得注意的特点：

**双计数器独立触发**：Memory Nudge 按用户回合计数，Skill Nudge 按工具调用迭代计数。两个维度独立追踪，避免相互干扰。

**后台 fork 执行**：review agent 是主 agent 的完整 fork（相同模型，quiet_mode=True），拿到完整对话历史后独立决策。主 agent 不被阻塞，用户无感知。

**LLM 驱动的写入决策**：review agent 收到的 prompt 引导它区分三类输出——用户画像（USER.md）、工作笔记（MEMORY.md）、可复用技能（Skill）。本实验中 E1 训练的结果证明这个分类机制是准确的。

**借鉴点**：后台异步审查 + LLM 自由分类的模式，在决策质量和系统复杂度之间找到了平衡。对比 OpenClaw 的 3 阶段评分管道（6 个加权信号 + 阈值门限），Hermes 的方案更轻、部署成本更低，在偏好识别这类场景下效果不差。

### 4.3 G2 > G1：记忆框架本身对任务执行有正面影响

G2（有记忆框架但空白）的完成率（50%）显著高于 G1（skip_memory=True，25%）。两组的 system prompt 内容差异很小（G2 多了空的 USER.md/MEMORY.md 占位），但完成率差了一倍。

可能解释：记忆框架的存在改变了 system prompt 的结构和工具集，即使没有实际记忆内容，也可能影响模型的任务规划行为。这个现象值得进一步验证。

### 4.4 T4 同时提升了完成率和合规率

T4（写测试套件）是唯一一个 G3 完成率（40%）高于 G1（0%）的任务，同时 parametrize 合规率达 100%。可能原因：USER.md 中的 parametrize 指令给了模型清晰的执行策略，减少了探索式工具调用，反而节省了 context。

**借鉴点**：当进化产物（偏好指令）与任务高度匹配时，它不仅改变行为风格，还能提升任务效率。

---

## 五、有待考量之处

### 5.1 Skill 加载链：索引 → 强制指令 → skill_view → 上下文溢出

这是本实验暴露的最大问题。源码追踪揭示的实际机制与直觉不同：

**Hermes 并非将 Skill 全文注入 system prompt**。`prompt_builder.py:769-791` 的 `build_skills_system_prompt()` 只注入了 Skill 索引（`name: description`，约 430 chars），体积可控。但问题出在索引上方的 mandatory 强制加载指令：

```
## Skills (mandatory)
Before replying, scan the skills below. If a skill matches or is even partially
relevant to your task, you MUST load it with skill_view(name) and follow its
instructions. Err on the side of loading — it is always better to have context
you don't need than to miss critical steps, pitfalls, or established workflows.
```

`MUST load`、`even partially relevant`、`Err on the side of loading` 三重强制措辞，使模型在几乎所有编码任务开头都会调用 `skill_view('httpx-retry-pattern')`。该工具（`skills_tool.py:779`）读取 SKILL.md 全文并作为 tool result 返回——18,009 chars 一次性进入对话上下文。

**G3 失败链**：system prompt 中 Skill 索引(~430c) → mandatory `MUST load` 指令 → 模型首轮调用 `skill_view()` → 18KB tool result 进入 context → 仅剩 1-2 次工具调用额度 → context 溢出。实际数据：G3 的 15 次失败运行中，11 次（73%）的第一个工具调用就是 `skill_view('httpx-retry-pattern')`。

对比 OpenClaw 的做法：只将 `name: description`（约 100 chars/skill）注入索引，agent 需要时通过 `read` 调用按需加载，且不使用 mandatory 强制措辞。两种策略的权衡：

| 策略 | 优势 | 劣势 |
|------|------|------|
| Hermes 索引 + mandatory 强制加载 | 确保 Skill 不被遗漏 | 强制 `skill_view` 导致大 Skill 挤占 context |
| OpenClaw 索引 + 自由加载 | prompt 开销恒定，不受 Skill 体积影响 | 模型可能「忘记」加载 |

**考量**：问题不在索引注入，而在两处——(1) mandatory 指令过于强硬，应改为「建议加载」或按任务相关性条件加载；(2) `skill_view` 应支持摘要模式（返回签名+关键约束，而非全文）。当前 `MAX_SKILL_CONTENT_CHARS = 100,000` 的上限也过于宽松。

### 5.2 进化产物缺乏成本感知和质量门控

nudge 的 review agent 在创建 Skill 时存在两个层面的缺陷：

**内容质量问题**：review agent 将 E2 训练中产出的所有 Python 文件（constants.py、api_client.py、测试、示例）原封不动 dump 进 SKILL.md，占比 87% 的内容是可直接执行的源码。这不是「记录模式」，而是「复制粘贴代码仓库」。一个合格的 Skill 应该是精炼的知识摘要——函数签名、核心参数、关键约束、常见陷阱——而非完整实现。

**体积成本无感知**：review prompt 中没有任何关于「产出物体积」或「context 成本」的引导。review agent 优化的目标是「完整性」——尽可能详尽地记录，所以产出了 18KB。但这个 18KB 通过 `skill_view` 进入对话 context 后，直接导致了 G3 的 75% 失败率。

**根因**：Skill 创建流程缺乏两道防线——(1) review prompt 级：引导 agent 产出精炼摘要而非代码 dump；(2) 系统级：`skill_manager_tool.py` 的 `MAX_SKILL_CONTENT_CHARS = 100,000` 上限形同虚设，应降至 2,000-3,000 chars 并在超限时要求 agent 精简。

### 5.3 进化决策的可控性

Hermes 的进化决策完全由 LLM 自由判断，没有评分门限或质量检查。对比 OpenClaw 的梦境系统：

| 维度 | Hermes | OpenClaw |
|------|--------|----------|
| 决策者 | LLM（review agent） | 3 阶段评分管道 |
| 写入条件 | LLM 认为"值得保存" | minScore≥0.8, minRecallCount≥3, minUniqueQueries≥3 |
| 调度 | 对话中实时触发 | cron 离线（默认每天凌晨 3 点） |
| 控制力 | 低（依赖 prompt 引导） | 高（硬编码阈值） |

Hermes 的优势是实时性——E1 训练中途就写入 USER.md，后续轮次立即受益。OpenClaw 需要等到下一个 cron 周期。但代价是缺乏安全阀，V2 实验的 18KB Skill 就是一个例证。

**考量**：能否在保留实时性的同时引入轻量级检查？比如 Skill 创建后检查 system prompt 总体积是否超出预算。

### 5.4 反默认偏好的模型依赖性

G1 控制组的 httpx/loguru 合规率达 50%——所有成功完成的 G1 运行都自然选择了 httpx + loguru。这意味着这两个偏好对 claude-sonnet-4-5 并非"反默认"。

实际有效的反默认偏好（G1=0%）只有 4 个：TOML、msgspec、Result 模式、parametrize。constants.py 在 G1/G2 都是 27%（T3 prompt 本身暗示了"集中管理常量"）。

**考量**：反默认偏好的选择需要按模型版本验证基线。不同模型版本可能有不同的"自然偏好"。

### 5.5 统计效力

N=5 导致大多数对比无法达到 p<0.05。唯一显著的结果是 T4 parametrize（p=0.002），而总体合规率对比 p=0.069 未达到常规显著性水平。原始 report.md 使用了"显著高于"的措辞，不够严谨。

加之 G3 有 75% 的运行因上下文溢出失败（completed=false），实际产出代码的样本更少。失败运行被记为全偏好不合规（score=0），混淆了"不愿合规"和"没机会合规"。

**考量**：后续实验建议区分 ITT（intent-to-treat，包含失败）和 PP（per-protocol，仅完成运行）两种统计口径。

---

## 六、进化触发机制

### 6.1 两个触发器

**Memory Nudge**：计数器 `_turns_since_memory` 每用户回合 +1，到达阈值（默认 10，本实验配 3）后标记 `_should_review_memory`。

**Skill Nudge**：计数器 `_iters_since_skill` 每工具调用迭代 +1，到达阈值（默认 10，本实验配 5）后标记 `_should_review_skills`。agent 主动调用 `skill_manage` 时计数器归零。

触发后调用 `_spawn_background_review()`：fork 完整 AIAgent（相同模型，max_iterations=8，quiet_mode=True），传入完整对话历史 + review prompt。

### 6.2 Review Prompt

| 审查类型 | prompt 核心 | 写入目标 |
|---------|-----------|---------|
| Memory | "用户是否暴露了偏好、身份、工作风格？" | USER.md 或 MEMORY.md |
| Skill | "是否有非平凡方法、试错过程、用户期望的不同做法？" | SKILL.md |
| Combined | 两者合并 | 视情况而定 |

决策不是硬编码的，完全由 LLM 基于 prompt 引导做出。

---

## 七、与 OpenClaw 的对比

### 7.1 架构对比

| 维度 | Hermes | OpenClaw |
|------|--------|----------|
| 记忆文件 | MEMORY.md + USER.md | MEMORY.md + USER.md + 每日笔记 + DREAMS.md |
| 记忆搜索 | session_search（关键词） | 混合 BM25 + 向量检索，3 种后端 |
| 用户画像 | USER.md（nudge 写入） | USER.md（手动）+ Honcho 自动建模 |
| 技能注入 | 索引注入 system prompt + mandatory `skill_view` 强制加载全文 | 仅注入元数据索引，按需加载 |
| 进化触发 | 对话中实时（计数器 → 后台 review） | cron 离线（默认每天凌晨 3 点） |
| 进化决策 | LLM 自由判断 | 3 阶段评分管道 + 阈值门限 |
| 主动记忆 | 无 | 阻塞式子 agent 预检索 |
| 上下文控制 | USER.md 1,375c / MEMORY.md 2,200c / Skill 无总量限制 | 单文件 20Kc / 总引导 150Kc |

### 7.2 各有取舍

**Hermes 的优势**：
- **实时进化**：对话中途即可更新记忆和技能，后续轮次立即受益。OpenClaw 的梦境系统是离线 cron，无法在交互中实时响应。
- **架构简单**：计数器 → fork review agent → LLM 决定写什么。没有评分管道、多阶段、插件系统。易理解、易调试。
- **语义分类准确**：USER.md / MEMORY.md 的 target 参数设计在本实验中表现正确。

**OpenClaw 的优势**：
- **Skill 按需加载**：prompt 开销恒定，不因 Skill 体积增长而挤占 context。本实验直接暴露了 Hermes mandatory 强制加载 + 低质量大 Skill 组合的风险。
- **进化质量门控**：梦境系统的 6 信号评分 + 阈值门限机制，避免了低质量或过大的进化产物。
- **主动记忆预检索**：agent 不需要"想起来要搜索记忆"，系统自动完成。
- **上下文预算管理**：单文件 20K chars 截断 + 总引导 150K chars 上限，系统级保障 context 不溢出。

### 7.3 两种进化哲学

| | Hermes | OpenClaw |
|--|--------|----------|
| 理念 | 激进探索：快速写入，有问题再修 | 保守积累：充分验证后才写入 |
| 时效 | 实时（秒级） | 延迟（小时级） |
| 风险 | 可能写入过大/低质量产物 | 可能错过值得保存的内容 |
| 适用场景 | 长对话、快速迭代 | 长期项目、稳定性优先 |

---

## 八、总结

### 实验揭示的事实

1. **USER.md 是高性价比的行为引导机制**：470B 的注入量几乎不影响 context，但在 parametrize 上实现了 0% → 100% 的行为改变（p=0.002）
2. **Skill mandatory 强制加载 + 低质量 Skill = 系统性风险**：system prompt 中的 `MUST load` 指令迫使模型在首轮调用 `skill_view`，18KB 的代码 dump（87% 原始 Python）一次性涌入 context，导致 G3 完成率从 G2 的 50% 降到 25%，T1 从 100% 降到 0%
3. **记忆框架本身有正面影响**：G2（空白记忆）50% > G1（无记忆）25%，即使没有进化产物
4. **nudge 的语义分类是准确的**：review agent 正确区分了用户画像和工作笔记
5. **反默认偏好假设需要按模型版本验证**：httpx/loguru 对 claude-sonnet-4-5 并非反默认（G1 基线 50%）

### 可借鉴

- 用户画像（USER.md）作为轻量 system prompt 注入，改变模型行为的性价比很高
- 后台 fork review agent 的异步审查模式，在简洁性和效果之间取得了好的平衡
- 双计数器（回合数 + 工具调用数）独立触发 memory 和 skill 审查，设计合理
- 实时进化在长对话中有独特优势

### 有待考量

- Skill 加载机制需要修正：mandatory 强制加载指令过于强硬、`skill_view` 缺乏摘要模式、`MAX_SKILL_CONTENT_CHARS` 上限过于宽松
- 进化产物缺乏质量门控：review agent 将代码 dump 进 SKILL.md（87% 原始 Python），无体积约束和内容质量引导
- LLM 自由决策缺乏安全阀：没有阈值门限阻止过大或低质量的写入
- 统计设计：N=5 效力不足，失败运行与不合规运行未区分
