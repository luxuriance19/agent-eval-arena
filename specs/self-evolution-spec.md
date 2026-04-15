---
tags: [agent-eval, hermes, self-evolution, spec]
date: 2026-04-15
---

# Hermes 自进化机制 — 技术规格

> 本文档基于 Hermes Agent 源码分析 + 实际评估数据，详述 5 层自进化机制的实现细节、触发条件、数据流和评估结论。

## 架构总览

```
System Prompt 组装顺序（12 层）
──────────────────────────────────────────────
 1. Agent identity (SOUL.md)
 2. Tool-aware behavioral guidance
    ├─ MEMORY_GUIDANCE        ← Layer 1
    ├─ SESSION_SEARCH_GUIDANCE ← Layer 4
    └─ SKILLS_GUIDANCE        ← Layer 2
 3. Nous subscription prompt
 4. Tool-use enforcement
 5. User/gateway system message
 6. MEMORY.md frozen snapshot  ← Layer 1
 7. USER.md frozen snapshot    ← Layer 3
 8. External memory provider
 9. Skills index              ← Layer 2
10. Context files (.hermes.md)
11. Timestamp + session/model
12. Environment hints
──────────────────────────────────────────────
```

```
数据流
──────────────────────────────────────────────

用户对话 ──┬── 每 N turn ──→ Memory Nudge ──→ 后台 Review Agent
           │                                   ├→ MEMORY.md (Layer 1)
           │                                   └→ USER.md  (Layer 3)
           │
           ├── 每 M iter ──→ Skill Nudge ──→ 后台 Review Agent
           │                                   └→ SKILL.md (Layer 2)
           │
           ├── model 主动 ──→ session_search ──→ state.db FTS5 (Layer 4)
           │
           └── 上下文压缩 / session 结束 ──→ flush_memories
                                              ├→ MEMORY.md
                                              └→ USER.md
```

---

## Layer 1: 持久记忆 (MEMORY.md)

### 源码位置

| 组件 | 位置 |
|------|------|
| MemoryStore 类 | `tools/memory_tool.py:100` |
| memory 工具函数 | `tools/memory_tool.py:439` |
| MEMORY_SCHEMA 工具定义 | `tools/memory_tool.py:489-538` |
| 注入 system prompt | `run_agent.py:3175-3179` |
| flush_memories | `run_agent.py:6587-6746` |
| 后台 review (memory 部分) | `run_agent.py:2140-2239` |

### 工具定义

```yaml
name: memory
actions: [add, replace, remove]
targets:
  memory: "Agent personal notes (max 2200 chars)"
  user:   "User profile (max 1375 chars)"
parameters:
  action:   required, enum [add/replace/remove]
  target:   required, enum [memory/user]
  content:  string, required for add/replace
  old_text: string, required for replace/remove (substring match)
```

### 存储机制

- **路径**: `~/.hermes/memories/MEMORY.md`
- **条目分隔符**: `§` (section sign)
- **写入方式**: `tempfile` + `os.replace` 原子写入 + `fcntl.flock` 文件锁
- **字符限制**: memory 2200 / user 1375 (可配置 `memory.memory_char_limit` / `memory.user_char_limit`)
- **冻结快照**: `load_from_disk()` 时捕获到 `_system_prompt_snapshot`，session 内不变以保持 prefix cache 稳定

### 注入格式

```
═══════════════════════════════════════════════
MEMORY (your personal notes) [45% -- 990/2200 chars]
═══════════════════════════════════════════════
条目1 § 条目2 § 条目3
```

---

## Layer 2: 技能系统 (skill_manage)

### 源码位置

| 组件 | 位置 |
|------|------|
| skill_manage 函数 | `tools/skill_manager_tool.py:588-646` |
| SKILL_MANAGE_SCHEMA | `tools/skill_manager_tool.py:653-740` |
| _create_skill | `tools/skill_manager_tool.py:292-346` |
| build_skills_system_prompt | `agent/prompt_builder.py:575-797` |
| 注入 system prompt | `run_agent.py:3195-3211` |
| 安全扫描 | `skills_guard.scan_skill()` |

### 工具定义

```yaml
name: skill_manage
actions: [create, patch, edit, delete, write_file, remove_file]
parameters:
  action:       required, enum
  name:         required, skill name (kebab-case)
  content:      full SKILL.md (create/edit)
  old_string:   patch source
  new_string:   patch target
  category:     optional, directory grouping
  file_path:    write_file/remove_file
  file_content: write_file
```

### 存储结构

```
~/.hermes/skills/
├── .bundled_manifest          # skill-name:hash per line
├── {category}/
│   └── {skill-name}/
│       ├── SKILL.md           # frontmatter + body
│       ├── references/        # 参考文件
│       ├── templates/         # 模板文件
│       └── scripts/           # 脚本文件
└── .skills_prompt_snapshot.json  # 磁盘缓存
```

### 技能创建流程

```
1. skill_manage(action="create") 调用
2. _create_skill() 验证名称/分类/frontmatter
3. 检查名称冲突（bundled vs user）
4. 创建目录 → 原子写入 SKILL.md
5. skills_guard.scan_skill() 安全扫描
6. 高危则回滚删除
7. clear_skills_system_prompt_cache() 清除缓存
8. 下次 turn 的 system prompt 包含新 skill 索引
```

### 注入格式

```xml
## Skills (mandatory)
Before replying, scan the skills below...

<available_skills>
  software-development:
    - http-retry-exponential-backoff: 为 HTTP 请求添加指数退避重试机制
  mlops:
    - trl-fine-tuning: Fine-tune LLMs using TRL
</available_skills>
```

缓存策略：两层 — in-process LRU (max 8) + 磁盘 `.skills_prompt_snapshot.json`

---

## Layer 3: 用户画像 (USER.md)

### 源码位置

| 组件 | 位置 |
|------|------|
| USER.md 路径定义 | `tools/memory_tool.py:156-160` |
| USER.md 格式化 | `tools/memory_tool.py:367-383` |
| user_profile_enabled 配置 | `run_agent.py:1127, 1136` |
| 注入 system prompt | `run_agent.py:3180-3184` |

### 与 Layer 1 的关系

- 共用 `memory` 工具，通过 `target="user"` 区分
- 共用 `MemoryStore` 实例
- **独立开关**: `user_profile_enabled` 可单独启用/禁用，不受 `memory_enabled` 影响

### 存储路径

`~/.hermes/memories/USER.md`

### 注入格式

```
═══════════════════════════════════════════════
USER PROFILE (who the user is) [15% -- 212/1375 chars]
═══════════════════════════════════════════════
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
类型注解风格：强制使用 PEP 604 语法 (X | None)，禁止使用 Optional[X]；使用小写内置类型 dict[str, int] 而非 Dict[str, int]
```

---

## Layer 4: 跨会话搜索 (session_search)

### 源码位置

| 组件 | 位置 |
|------|------|
| session_search 函数 | `tools/session_search_tool.py:297-480` |
| SESSION_SEARCH_SCHEMA | `tools/session_search_tool.py:492-536` |
| _summarize_session (LLM 摘要) | `tools/session_search_tool.py:175-236` |
| state.db schema | `hermes_state.py:36-112` |

### 工具定义

```yaml
name: session_search
description: "Search past conversations or browse recent sessions"
modes:
  browse: query 为空 → 返回最近 session 列表（无 LLM 开销）
  search: query 非空 → FTS5 关键词搜索 + LLM 摘要
parameters:
  query:       optional, FTS5 syntax (OR/NOT/phrase/prefix)
  role_filter: optional, comma-separated roles
  limit:       optional, default 3, max 5
```

### state.db Schema

```sql
-- 核心表
sessions (id PK, source, user_id, model, started_at, ended_at,
          message_count, tool_call_count, token counts..., title)

messages (id PK AUTO, session_id FK, role, content, tool_call_id,
          tool_calls, tool_name, timestamp, token_count, reasoning...)

-- FTS5 全文搜索
messages_fts (content) -- 同步触发器: INSERT/DELETE/UPDATE
```

### 搜索流程

```
1. FTS5 搜索: db.search_messages(query) → 匹配消息 (limit=50)
2. Session 分组: 解析子 session → 父 session (delegation chain)
3. 排除当前 session lineage
4. 截断: _truncate_around_matches() → 以匹配位置为中心 100k 字符窗口
5. LLM 摘要: 并行 async_call_llm(task="session_search") → 聚焦摘要
6. 返回 JSON: {session_id, when, source, model, summary}
```

### 触发方式

**无自动触发** — 仅在 model 主动调用时执行。通过 `SESSION_SEARCH_GUIDANCE` 引导 model 在需要历史上下文时使用。

---

## Layer 5: Nudge 机制 (后台 Review)

### 源码位置

| 组件 | 位置 |
|------|------|
| _turns_since_memory 计数器 | `run_agent.py:1130` |
| _iters_since_skill 计数器 | `run_agent.py:1131` |
| Memory nudge 检查 | `run_agent.py:7829-7836` |
| Skill nudge 递增 | `run_agent.py:8080-8083` |
| Skill nudge 检查 | `run_agent.py:10544-10550` |
| _spawn_background_review | `run_agent.py:2140-2239` |
| Review prompts | `run_agent.py:2105-2138` |
| 触发调用 | `run_agent.py:10562-10572` |

### 触发条件

| Nudge 类型 | 计数单位 | 默认阈值 | 配置项 | 重置条件 |
|-----------|---------|---------|-------|---------|
| Memory | 用户 turn | 10 | `memory.nudge_interval` | `memory` 工具被调用 |
| Skill | tool iteration | 10 | `skills.creation_nudge_interval` | `skill_manage` 工具被调用 |

**重要**: 两个计数器**不会**在 `run_conversation()` 开头重置，以便 CLI 多 turn 模式下正确跨轮累积。

### Memory Nudge 触发代码

```python
# run_agent.py:7829-7836
if (self._memory_nudge_interval > 0
        and "memory" in self.valid_tool_names
        and self._memory_store):
    self._turns_since_memory += 1
    if self._turns_since_memory >= self._memory_nudge_interval:
        _should_review_memory = True
        self._turns_since_memory = 0
```

### Skill Nudge 触发代码

```python
# run_agent.py:8080-8083 — 每个 tool iteration 递增
if (self._skill_nudge_interval > 0
        and "skill_manage" in self.valid_tool_names):
    self._iters_since_skill += 1

# run_agent.py:10546-10550 — turn 结束后检查
if (self._skill_nudge_interval > 0
        and self._iters_since_skill >= self._skill_nudge_interval
        and "skill_manage" in self.valid_tool_names):
    _should_review_skills = True
    self._iters_since_skill = 0
```

### 后台 Review Agent

```python
# run_agent.py:10562-10572 — 触发点
if final_response and not interrupted and (_should_review_memory or _should_review_skills):
    self._spawn_background_review(
        messages_snapshot=list(messages),
        review_memory=_should_review_memory,
        review_skills=_should_review_skills,
    )
```

#### Fork 过程

1. 根据 nudge 类型选择 prompt:
   - memory + skill → `_COMBINED_REVIEW_PROMPT`
   - 仅 memory → `_MEMORY_REVIEW_PROMPT`
   - 仅 skill → `_SKILL_REVIEW_PROMPT`

2. 创建新 `AIAgent`:
   - `max_iterations=8, quiet_mode=True`
   - 共享 `_memory_store`, `_memory_enabled`, `_user_profile_enabled`
   - **关键**: `_memory_nudge_interval=0`, `_skill_nudge_interval=0`（防止递归 nudge）
   - stdout/stderr → `/dev/null`

3. 执行 `review_agent.run_conversation(prompt, messages_snapshot)`

4. 扫描结果中的 tool 调用 → 汇总打印成功操作

5. 以 **daemon thread** 运行 (`threading.Thread(daemon=True, name="bg-review")`)

---

## 评估实证数据

### 评估配置

| 参数 | 默认值 | 评估值 | 说明 |
|------|--------|--------|------|
| `memory.nudge_interval` | 10 | 3 | 每 3 轮触发 memory review |
| `memory.flush_min_turns` | 6 | 2 | 最少 2 轮即可 flush |
| `skills.creation_nudge_interval` | 10 | 5 | 每 5 次工具迭代触发 skill review |

配置文件: `~/.hermes/config.yaml`（由 `hermes_cli.config.load_config()` 加载）

### 进化产物增长时间线

| 时间点 | MEMORY.md | USER.md | 用户 Skills | Sessions |
|--------|-----------|---------|------------|----------|
| pre-eval | 0 chars | 0 chars | 10 | 14 |
| after-E1 (记忆进化) | 0 chars | **212 chars** | 10 | 14 |
| after-E2 (技能创建) | 0 chars | 212 chars | **11** (+1) | 14 |
| after-E3 (跨会话搜索) | 0 chars | 212 chars | 11 | 14 |
| after-E4 (综合测试) | 0 chars | 212 chars | 11 | 14 |

- **USER.md** 在 E1 中由 memory nudge 后台 review 成功写入 6 条偏好
- **MEMORY.md** 未写入 — 后台 review 判断 "Nothing worth saving"（评估任务偏短，信息密度不够）
- **新 Skill**: `http-retry-exponential-backoff`（E2 中由 skill_manage 创建）

### 进化机制触发统计 (Phase B)

| 指标 | E1 | E2 | E3 | E4 | 总计 |
|------|----|----|----|----|------|
| memory 工具激活 | 2 | 0 | 0 | 0 | **2** |
| skill_manage 激活 | 0 | 1 | 0 | 0 | **1** |
| session_search 激活 | 0 | 0 | 1 | 0 | **1** |

### Phase A vs Phase C 对比 (进化前 vs 进化后)

| 任务 | 类型 | A 工具数 | C 工具数 | A 耗时 | C 耗时 | A Tokens | C Tokens |
|------|------|---------|---------|--------|--------|----------|----------|
| B1 | Python 调试 | 4 | 5 | 45.7s | 44.8s | 72K | 86K |
| B2 | Git 工作流 | 7 | 7 | 39.3s | 34.5s | 84K | 57K |
| B3 | Shell 脚本 | 28 | 12 | 153.5s | 108.3s | 0* | 214K |
| B4 | 代码审查 | 8 | 10 | 239.0s | 333.1s | 231K | 245K |

*Phase A B3 因 Bedrock 400 错误未记录 tokens（已在后续修复中解决）

**关键发现**:
- B2 token 减少 32%（57K vs 84K），耗时减少 12%
- B3 工具调用减少 57%（12 vs 28），耗时减少 29%
- 全部 Phase C 任务 0 风格违规（进化后 model 从 USER.md 加载了偏好）

---

## 已修复的 Bug

### Bedrock 空 content 验证错误 (HTTP 400)

**问题**: 模型返回仅含 tool_calls 无文本 content 的 assistant 消息时，`run_agent.py:6438` 将 `content` 设为空字符串 `""`。Bedrock 的 Anthropic 模型拒绝接受 `text content blocks must be non-empty`。

**修复** (commit `a029c61e`):

1. `run_agent.py:6436-6448` — 当 content 为空 + 有 tool_calls 时，设 `content=None`
2. `run_agent.py:6199-6219` — `_build_api_kwargs` 中在发送 API 前，移除 assistant 消息中空 content + tool_calls 的 content 字段（带 lazy deepcopy 保护原始数据）

**验证**: 修复后 Phase C 全部 4 个任务成功完成（之前 B1/B3 因此 bug 中断）。

---

## 对 CC/OC 的差异化优势

| 能力 | Hermes | Claude Code | OpenClaw |
|------|--------|-------------|----------|
| 持久记忆 (MEMORY.md) | `memory` 工具 + 冻结快照注入 | `auto_memory` (MEMORY.md) | 无 |
| 用户画像 (USER.md) | 自动提取 + 独立开关 | 无独立用户画像 | 无 |
| 技能系统 | `skill_manage` + 安全扫描 + 缓存 | Skills (`.claude/skills/`) | 无 |
| 跨会话搜索 | `session_search` + FTS5 + LLM 摘要 | 无 | 无 |
| 后台 Nudge | daemon thread + fork agent | 无自动 nudge | 无 |
| 触发机制 | turn-based + iteration-based 双计数器 | 无（手动保存） | 无 |

### Hermes 独有优势

1. **自主学习闭环**: Nudge → 后台 Review Agent → 自动写入 MEMORY/USER/SKILL → 下一个 turn 注入 system prompt → 行为改变
2. **用户画像独立于记忆**: USER.md 有独立开关，即使关闭 memory 仍可注入用户偏好
3. **安全扫描**: Agent 创建的 skill 会被 `skills_guard.scan_skill()` 扫描，高危自动回滚
4. **FTS5 全文搜索**: 历史会话可被精确搜索，不依赖 embedding，支持 boolean 语法

### Claude Code 可借鉴

- CC 的 `auto_memory` 写入比较被动（仅在对话结束时考虑），可借鉴 Hermes 的 turn-based nudge 主动触发
- CC 无 USER.md 概念，可考虑加入用户画像抽取
- CC 的 Skills 系统与 Hermes 类似但缺少安全扫描和自动 nudge

---

## 文件索引

| 文件 | 说明 |
|------|------|
| `tools/memory_tool.py` | Layer 1+3: MemoryStore + memory 工具 |
| `tools/skill_manager_tool.py` | Layer 2: skill_manage 工具 |
| `tools/session_search_tool.py` | Layer 4: session_search 工具 |
| `agent/prompt_builder.py` | Guidance + Skills 索引构建 |
| `run_agent.py:1124-1232` | 初始化: memory/skill 配置加载 |
| `run_agent.py:2105-2239` | Layer 5: Review prompts + _spawn_background_review |
| `run_agent.py:3100-3211` | System prompt 12 层组装 |
| `run_agent.py:6587-6746` | flush_memories 实现 |
| `run_agent.py:7829-7836` | Memory nudge 计数器 |
| `run_agent.py:8080-8083` | Skill nudge 计数器 |
| `run_agent.py:10544-10572` | Nudge 检查 + 触发后台 review |
| `hermes_state.py:36-112` | state.db schema (sessions/messages/FTS5) |

---

*相关文档: [[00-Overview]], [[10-Architecture-Diff-Analysis]], [[11-Self-Evolution-Eval]]*
