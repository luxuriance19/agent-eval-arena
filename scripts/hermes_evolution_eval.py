#!/usr/bin/env python3
"""Hermes Self-Evolution Evaluation Runner.

通过 Python API 直接驱动 AIAgent 进行多轮多会话测试，
触发并量化 Hermes 5 层自进化机制的实际效果。

用法:
    python hermes_evolution_eval.py                 # 执行全部阶段
    python hermes_evolution_eval.py --phase A       # 仅基线测试
    python hermes_evolution_eval.py --phase B       # 仅进化会话
    python hermes_evolution_eval.py --phase C       # 仅进化后重测
    python hermes_evolution_eval.py --report        # 仅生成报告
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# 将 hermes-agent 项目加入 sys.path
HERMES_ROOT = Path("/Users/lini03/baidu/hermes-agent")
sys.path.insert(0, str(HERMES_ROOT))

from run_agent import AIAgent  # noqa: E402

# ── 路径常量 ──────────────────────────────────────────────────
RESULTS_DIR = Path("/Users/lini03/baidu/agent-eval-arena/results/hermes/self-evolution")
SNAPSHOTS_DIR = RESULTS_DIR / "snapshots"
PHASE_A_DIR = RESULTS_DIR / "phases" / "A-baseline"
PHASE_B_DIR = RESULTS_DIR / "phases" / "B-evolution"
PHASE_C_DIR = RESULTS_DIR / "phases" / "C-post-evolution"
ANALYSIS_DIR = RESULTS_DIR / "analysis"

HERMES_HOME = Path.home() / ".hermes"
MEMORY_MD = HERMES_HOME / "memories" / "MEMORY.md"
USER_MD = HERMES_HOME / "memories" / "USER.md"
STATE_DB = HERMES_HOME / "state.db"
SKILLS_DIR = HERMES_HOME / "skills"

WORK_DIR = Path("/tmp/hermes-evolution-eval")

# 默认模型（与 cli-config.yaml 一致）
DEFAULT_MODEL = "custom/claude-sonnet-4-5-20250929"

# 后台 review 线程等待时间（秒）
BACKGROUND_REVIEW_WAIT = 10


# ── 数据类 ────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class TurnResult:
    """单轮对话结果。"""
    turn: int
    prompt: str
    response: str | None
    tool_calls: list[dict]
    tool_call_count: int
    api_calls: int
    duration_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    completed: bool
    memory_tool_used: bool
    skill_manage_used: bool
    session_search_used: bool


@dataclass(frozen=True, slots=True)
class EvolutionSnapshot:
    """进化状态快照。"""
    label: str
    timestamp: str
    memory_md_content: str
    memory_md_chars: int
    user_md_content: str
    user_md_chars: int
    user_skills: list[dict]
    user_skill_count: int
    session_count: int


# ── 工具函数 ──────────────────────────────────────────────────
def _read_file_safe(path: Path) -> str:
    """安全读取文件，不存在则返回空字符串。"""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def _count_sessions() -> int:
    """从 state.db 统计 session 数量。"""
    try:
        conn = sqlite3.connect(str(STATE_DB))
        cursor = conn.execute("SELECT COUNT(*) FROM sessions;")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _list_user_skills() -> list[dict]:
    """列出用户创建的 skills（排除 bundled）。"""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    # 解析 bundled manifest（格式：每行 "skill-name:hash"）
    bundled_names: set[str] = set()
    manifest = SKILLS_DIR / ".bundled_manifest"
    if manifest.exists():
        for line in _read_file_safe(manifest).splitlines():
            line = line.strip()
            if ":" in line:
                bundled_names.add(line.split(":")[0])

    for skill_md in SKILLS_DIR.rglob("SKILL.md"):
        rel = skill_md.relative_to(SKILLS_DIR)
        parts = rel.parts
        # 结构: category/skill-name/SKILL.md
        if len(parts) >= 2:
            category = parts[0]
            skill_name = skill_md.parent.name
            # 跳过 bundled skills
            if skill_name in bundled_names:
                continue
            content = _read_file_safe(skill_md)
            skills.append({
                "category": category,
                "name": skill_name,
                "path": str(skill_md),
                "content": content,
                "chars": len(content),
            })
    return skills


def snapshot_evolution_state(label: str) -> EvolutionSnapshot:
    """快照所有进化产物。"""
    memory_content = _read_file_safe(MEMORY_MD)
    user_content = _read_file_safe(USER_MD)
    user_skills = _list_user_skills()

    snap = EvolutionSnapshot(
        label=label,
        timestamp=datetime.now(timezone.utc).isoformat(),
        memory_md_content=memory_content,
        memory_md_chars=len(memory_content),
        user_md_content=user_content,
        user_md_chars=len(user_content),
        user_skills=user_skills,
        user_skill_count=len(user_skills),
        session_count=_count_sessions(),
    )
    # 持久化
    out_path = SNAPSHOTS_DIR / f"{label}.json"
    out_path.write_text(json.dumps(asdict(snap), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [snapshot] {label} → {out_path}")
    return snap


def create_agent(session_id: str | None = None) -> AIAgent:
    """创建标准配置的 AIAgent 实例（memory + skills 由 config.yaml 控制）。"""
    return AIAgent(
        model=DEFAULT_MODEL,
        session_id=session_id,
        quiet_mode=True,
        max_iterations=90,
    )


def _extract_tool_calls(messages: list[dict]) -> list[dict]:
    """从消息历史中提取所有工具调用。"""
    calls = []
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                calls.append({
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", ""),
                })
    return calls


def _has_tool(tool_calls: list[dict], name: str) -> bool:
    """检查工具调用列表中是否包含指定工具。"""
    return any(tc["name"] == name for tc in tool_calls)


def run_multi_turn_session(
    agent: AIAgent,
    turns: list[str],
    session_label: str,
    output_dir: Path,
) -> list[TurnResult]:
    """按顺序发送多轮消息，每轮记录指标，轮间等待后台 review。"""
    results: list[TurnResult] = []
    messages: list[dict] = []

    print(f"\n{'='*60}")
    print(f"Session: {session_label} ({len(turns)} turns)")
    print(f"{'='*60}")

    for i, turn_prompt in enumerate(turns):
        turn_num = i + 1
        print(f"\n  Turn {turn_num}/{len(turns)}: {turn_prompt[:80]}...")

        start = time.time()
        try:
            result = agent.run_conversation(
                user_message=turn_prompt,
                conversation_history=messages,
            )
        except Exception as e:
            print(f"    [ERROR] Turn {turn_num} failed: {e}")
            results.append(TurnResult(
                turn=turn_num,
                prompt=turn_prompt,
                response=f"ERROR: {e}",
                tool_calls=[],
                tool_call_count=0,
                api_calls=0,
                duration_seconds=time.time() - start,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                estimated_cost_usd=0.0,
                completed=False,
                memory_tool_used=False,
                skill_manage_used=False,
                session_search_used=False,
            ))
            continue

        duration = time.time() - start
        messages = result.get("messages", [])
        tool_calls = _extract_tool_calls(messages)

        # 本轮新增的工具调用（排除之前轮次的）
        prev_tc_count = sum(r.tool_call_count for r in results)
        turn_tool_calls = tool_calls[prev_tc_count:]

        turn_result = TurnResult(
            turn=turn_num,
            prompt=turn_prompt,
            response=result.get("final_response"),
            tool_calls=turn_tool_calls,
            tool_call_count=len(turn_tool_calls),
            api_calls=result.get("api_calls", 0),
            duration_seconds=round(duration, 2),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
            completed=result.get("completed", False),
            memory_tool_used=_has_tool(turn_tool_calls, "memory"),
            skill_manage_used=_has_tool(turn_tool_calls, "skill_manage"),
            session_search_used=_has_tool(turn_tool_calls, "session_search"),
        )
        results.append(turn_result)

        print(f"    ✓ {duration:.1f}s | tools: {len(turn_tool_calls)} | "
              f"tokens: {result.get('total_tokens', 0)} | "
              f"mem: {'Y' if turn_result.memory_tool_used else 'N'} | "
              f"skill: {'Y' if turn_result.skill_manage_used else 'N'} | "
              f"search: {'Y' if turn_result.session_search_used else 'N'}")

        # 等待后台 review 线程完成
        if i < len(turns) - 1:
            time.sleep(BACKGROUND_REVIEW_WAIT)

    # 保存 session 结果
    out_path = output_dir / f"{session_label}.json"
    out_path.write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  [saved] {out_path}")
    return results


def run_single_turn(
    task_id: str,
    prompt: str,
    output_dir: Path,
) -> TurnResult:
    """单轮独立任务执行。"""
    agent = create_agent(session_id=f"eval-{task_id}")
    results = run_multi_turn_session(
        agent=agent,
        turns=[prompt],
        session_label=task_id,
        output_dir=output_dir,
    )
    return results[0] if results else None


# ── Phase A: 基线测试 ────────────────────────────────────────
BASELINE_TASKS = {
    "B1": {
        "type": "Python 调试",
        "prompt": (
            f"请帮我修复这个 CSV 读取脚本的 bug。文件在 {WORK_DIR}/data.csv。"
            "脚本需要读取 CSV 文件并计算每个人的 salary 平均值，"
            "但遇到空行和缺失值时会崩溃。请写一个健壮的 csv_reader.py 到同目录。"
        ),
    },
    "B2": {
        "type": "Git 工作流",
        "prompt": (
            f"在 {WORK_DIR}/git-demo 目录下完成以下 Git 操作：\n"
            "1. 初始化一个新的 Git 仓库\n"
            "2. 创建 README.md，写入项目说明\n"
            "3. 创建 .gitignore（Python 项目标准）\n"
            "4. 提交初始代码\n"
            "5. 创建 feature/add-config 分支并切换到该分支"
        ),
    },
    "B3": {
        "type": "Shell 脚本",
        "prompt": (
            f"在 {WORK_DIR} 目录下编写一个 backup.sh 脚本，功能：\n"
            "1. 递归查找指定目录下所有 .py 文件\n"
            "2. 将它们备份到 backup/ 子目录（保持目录结构）\n"
            "3. 带时间戳的日志输出\n"
            "4. 完善的错误处理（目录不存在、权限不足等）\n"
            "5. 使用 getopts 解析 --source 和 --dest 参数"
        ),
    },
    "B4": {
        "type": "代码审查",
        "prompt": (
            f"请对 {WORK_DIR}/app.py 进行安全审查。"
            "找出所有安全漏洞（OWASP Top 10），逐一说明风险等级、"
            "攻击方式和修复建议。最后写出修复后的 app_fixed.py。"
        ),
    },
}


def run_phase_a() -> dict:
    """Phase A：基线测试（进化前，干净状态）。"""
    print("\n" + "=" * 70)
    print("PHASE A: 基线测试（进化前）")
    print("=" * 70)

    snapshot_evolution_state("pre-eval")

    results = {}
    for task_id, task in BASELINE_TASKS.items():
        print(f"\n--- Task {task_id}: {task['type']} ---")
        result = run_single_turn(task_id, task["prompt"], PHASE_A_DIR)
        results[task_id] = asdict(result) if result else {"error": "failed"}

    # 保存汇总
    summary_path = PHASE_A_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Phase A] 完成，结果保存到 {PHASE_A_DIR}")
    return results


# ── Phase B: 进化会话 ────────────────────────────────────────
EVOLUTION_SESSIONS = {
    "E1": {
        "label": "记忆进化 (Layer 1 + Layer 3)",
        "turns": [
            (
                "自我介绍一下：我是百度后端 Python 开发者，"
                "日常用 ruff 格式化、pytest 测试、pathlib 处理路径，"
                "时区 Asia/Shanghai。请记住这些。"
            ),
            (
                "重要偏好：写 Python 时必须用 PEP 604 联合类型 (X | None)，"
                "绝对不要用 Optional。用 dict[str, int] 不要 Dict[str, int]。"
                "请确认你记住了。"
            ),
            (
                f"在 {WORK_DIR} 下写一个 config_reader.py，"
                "用 pathlib 读取 JSON 配置文件，全部使用类型注解，"
                "包含 load_config 和 get_value 函数。"
            ),
            (
                "我要 @dataclass(frozen=True, slots=True)，不要普通 dict。"
                "请用 frozen dataclass 重写 config_reader.py 中的配置模型。"
            ),
            (
                f"给 {WORK_DIR}/config_reader.py 写 pytest 测试，"
                "放在 test_config_reader.py。mock 文件系统，不要真实读文件。"
            ),
            (
                f"请在 {WORK_DIR} 目录下执行 "
                "pytest test_config_reader.py -v 并修复所有失败的测试。"
            ),
            (
                f"给 {WORK_DIR}/config_reader.py 添加 Pydantic 配置 schema 验证，"
                "确保配置项类型正确。用 BaseModel 定义 schema。"
            ),
            (
                f"在 {WORK_DIR} 下用 argparse 写 CLI 包装 cli.py，"
                "包含 --config 指定配置路径和 --validate 执行校验。"
            ),
            (
                f"让 {WORK_DIR}/config_reader.py 优雅处理 malformed JSON，"
                "给出友好的错误信息（行号、位置、建议修复方式）。"
            ),
            (
                f"在 {WORK_DIR} 下创建 requirements.txt，"
                "包含所有用到的依赖，带精确版本号。"
            ),
        ],
    },
    "E2": {
        "label": "技能创建 (Layer 2 + Layer 3)",
        "turns": [
            (
                f"修复 {WORK_DIR}/scraper.py 的速率限制问题。"
                "添加指数退避 (exponential backoff) 重试装饰器，"
                "加入详细日志记录，处理 429 和 5xx 错误。"
            ),
            (
                f"{WORK_DIR}/api_client.py 有同样的问题，"
                "请应用与 scraper.py 相同的 retry+backoff 模式。"
            ),
            (
                "把我们刚才实现的 retry+exponential backoff 模式保存为一个 skill，"
                "这样以后遇到类似场景可以直接复用。"
            ),
            (
                f"在 {WORK_DIR} 下编写 Dockerfile + docker-compose.yml + Makefile，"
                "用于部署 Python Web 应用（Flask/FastAPI），包含多阶段构建、"
                "health check、环境变量管理。"
            ),
            (
                "把刚才的 Docker 部署模式也保存为 skill，"
                "包含 Dockerfile 多阶段构建 + compose + Makefile 的最佳实践。"
            ),
        ],
    },
    "E3": {
        "label": "跨会话搜索 (Layer 4)",
        "turns": [
            "回忆一下之前我们做的 config_reader.py 用了什么方法和模式？",
            "搜索之前会话中的 exponential backoff 实现方式，告诉我具体的实现细节。",
            (
                f"结合过去会话中的代码，在 {WORK_DIR} 写一个 resilient_config.py，"
                "能从远程 URL 加载 JSON 配置，带重试机制，"
                "用之前的 retry 模式和 pathlib 文件缓存。"
            ),
            "你记得我的编码偏好吗？列出所有你知道的关于我的编码习惯和偏好。",
            (
                f"在 {WORK_DIR} 创建一个 Python 项目模板目录 project-template/，"
                "融入我们所有会话中确立的偏好和模式：\n"
                "- pyproject.toml 配置\n"
                "- src/ 目录结构\n"
                "- tests/ 目录结构\n"
                "- Dockerfile + Makefile\n"
                "- 类型注解规范示例文件"
            ),
        ],
    },
    "E4": {
        "label": "综合测试 (全部 Layer)",
        "turns": [
            (
                "我需要一个 API 健康检查 CLI 工具，"
                "你应该已经知道我的偏好了——请直接按我的风格来写。"
            ),
            (
                f"在 {WORK_DIR} 实现 health_check.py：\n"
                "- YAML 配置文件定义要检查的端点\n"
                "- 用我们之前的 retry 模式处理网络错误\n"
                "- JSON 格式输出检查结果\n"
                "- 异步并发检查多个端点"
            ),
            (
                "纠正一下：用 StrEnum 代替字符串常量定义检查状态，"
                "用 asyncio.TaskGroup 代替 asyncio.gather 做并发。请修改。"
            ),
            (
                f"给 {WORK_DIR}/health_check.py 写 pytest 测试，"
                "mock HTTP 请求，覆盖成功和失败路径，包含边界情况。"
            ),
            (
                f"在 {WORK_DIR} 给 health_check 项目加 Dockerfile，"
                "参考我们之前保存的部署 skill。"
            ),
            (
                f"在 {WORK_DIR} 执行 pytest 运行所有测试，确保全部通过。"
            ),
            (
                "总结今天所有 session 中我们构建了什么、"
                "你学到了关于我的哪些偏好、以及保存了哪些技能。"
            ),
        ],
    },
}


def run_phase_b() -> dict:
    """Phase B：进化会话（多轮交互，触发 5 层机制）。"""
    print("\n" + "=" * 70)
    print("PHASE B: 进化会话")
    print("=" * 70)

    results = {}
    for sid, session_def in EVOLUTION_SESSIONS.items():
        label = session_def["label"]
        turns = session_def["turns"]

        agent = create_agent(session_id=f"eval-{sid}")
        session_results = run_multi_turn_session(
            agent=agent,
            turns=turns,
            session_label=sid,
            output_dir=PHASE_B_DIR,
        )
        results[sid] = {
            "label": label,
            "turns": [asdict(r) for r in session_results],
            "total_tool_calls": sum(r.tool_call_count for r in session_results),
            "total_duration": sum(r.duration_seconds for r in session_results),
            "total_tokens": sum(r.total_tokens for r in session_results),
            "memory_tool_activations": sum(1 for r in session_results if r.memory_tool_used),
            "skill_manage_activations": sum(1 for r in session_results if r.skill_manage_used),
            "session_search_activations": sum(1 for r in session_results if r.session_search_used),
        }

        # session 间快照
        snapshot_evolution_state(f"after-{sid}")

        # session 间等待，确保后台 review 完成
        print(f"\n  [wait] 等待 {BACKGROUND_REVIEW_WAIT}s 后台 review 完成...")
        time.sleep(BACKGROUND_REVIEW_WAIT)

    # 保存汇总
    summary_path = PHASE_B_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Phase B] 完成，结果保存到 {PHASE_B_DIR}")
    return results


def run_phase_c() -> dict:
    """Phase C：进化后重测（同基线任务）。"""
    print("\n" + "=" * 70)
    print("PHASE C: 进化后重测")
    print("=" * 70)

    snapshot_evolution_state("pre-retest")

    results = {}
    for task_id, task in BASELINE_TASKS.items():
        print(f"\n--- Task {task_id} (retest): {task['type']} ---")
        result = run_single_turn(
            f"{task_id}-retest",
            task["prompt"],
            PHASE_C_DIR,
        )
        results[task_id] = asdict(result) if result else {"error": "failed"}

    snapshot_evolution_state("post-retest")

    # 保存汇总
    summary_path = PHASE_C_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Phase C] 完成，结果保存到 {PHASE_C_DIR}")
    return results


# ── 分析和报告 ────────────────────────────────────────────────
def _check_style_compliance(code: str) -> dict:
    """检查代码风格合规性。"""
    violations = {
        "Optional[": {
            "pattern": r"Optional\[",
            "expected": "X | None (PEP 604)",
            "count": len(re.findall(r"Optional\[", code)),
        },
        "os.path": {
            "pattern": r"os\.path\.",
            "expected": "pathlib.Path",
            "count": len(re.findall(r"os\.path\.", code)),
        },
        "asyncio.gather": {
            "pattern": r"asyncio\.gather",
            "expected": "asyncio.TaskGroup",
            "count": len(re.findall(r"asyncio\.gather", code)),
        },
        "Dict[": {
            "pattern": r"\bDict\[",
            "expected": "dict[...] (PEP 585)",
            "count": len(re.findall(r"\bDict\[", code)),
        },
        "List[": {
            "pattern": r"\bList\[",
            "expected": "list[...] (PEP 585)",
            "count": len(re.findall(r"\bList\[", code)),
        },
    }
    total_violations = sum(v["count"] for v in violations.values())
    return {
        "violations": violations,
        "total_violations": total_violations,
        "compliant": total_violations == 0,
    }


def _extract_code_from_response(response: str | None) -> str:
    """从 agent 回复中提取代码块。"""
    if not response:
        return ""
    # 提取 ```python ... ``` 代码块
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)
    return "\n".join(blocks)


def generate_comparison(phase_a: dict, phase_c: dict) -> dict:
    """生成 Phase A vs Phase C 对比分析。"""
    comparison = {}
    for task_id in BASELINE_TASKS:
        a = phase_a.get(task_id, {})
        c = phase_c.get(task_id, {})

        # 代码风格检查
        a_code = _extract_code_from_response(a.get("response"))
        c_code = _extract_code_from_response(c.get("response"))
        a_style = _check_style_compliance(a_code)
        c_style = _check_style_compliance(c_code)

        comparison[task_id] = {
            "type": BASELINE_TASKS[task_id]["type"],
            "baseline": {
                "tool_calls": a.get("tool_call_count", 0),
                "duration": a.get("duration_seconds", 0),
                "tokens": a.get("total_tokens", 0),
                "completed": a.get("completed", False),
                "style_violations": a_style["total_violations"],
            },
            "post_evolution": {
                "tool_calls": c.get("tool_call_count", 0),
                "duration": c.get("duration_seconds", 0),
                "tokens": c.get("total_tokens", 0),
                "completed": c.get("completed", False),
                "style_violations": c_style["total_violations"],
            },
            "delta": {
                "tool_calls": c.get("tool_call_count", 0) - a.get("tool_call_count", 0),
                "duration": round(
                    c.get("duration_seconds", 0) - a.get("duration_seconds", 0), 2
                ),
                "tokens": c.get("total_tokens", 0) - a.get("total_tokens", 0),
                "style_violations": (
                    c_style["total_violations"] - a_style["total_violations"]
                ),
            },
            "style_detail": {
                "baseline": a_style,
                "post_evolution": c_style,
            },
        }

    comparison_path = ANALYSIS_DIR / "comparison.json"
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[analysis] 对比结果 → {comparison_path}")
    return comparison


def generate_evolution_timeline() -> dict:
    """生成进化产物时间线。"""
    timeline = {}
    for snap_file in sorted(SNAPSHOTS_DIR.glob("*.json")):
        try:
            data = json.loads(snap_file.read_text(encoding="utf-8"))
            timeline[data["label"]] = {
                "timestamp": data["timestamp"],
                "memory_md_chars": data["memory_md_chars"],
                "user_md_chars": data["user_md_chars"],
                "user_skill_count": data["user_skill_count"],
                "session_count": data["session_count"],
            }
        except Exception:
            pass

    timeline_path = ANALYSIS_DIR / "evolution-timeline.json"
    timeline_path.write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[analysis] 时间线 → {timeline_path}")
    return timeline


def generate_style_compliance_report(phase_c: dict) -> dict:
    """生成代码风格合规报告。"""
    report = {}
    for task_id in BASELINE_TASKS:
        c = phase_c.get(task_id, {})
        code = _extract_code_from_response(c.get("response"))
        report[task_id] = _check_style_compliance(code)

    report_path = ANALYSIS_DIR / "style-compliance.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[analysis] 风格合规 → {report_path}")
    return report


def generate_report(
    phase_a: dict,
    phase_b: dict,
    phase_c: dict,
    comparison: dict,
    timeline: dict,
) -> None:
    """生成最终 Markdown 报告。"""

    # 汇总进化会话统计
    total_memory_activations = sum(
        s.get("memory_tool_activations", 0) for s in phase_b.values()
    )
    total_skill_activations = sum(
        s.get("skill_manage_activations", 0) for s in phase_b.values()
    )
    total_search_activations = sum(
        s.get("session_search_activations", 0) for s in phase_b.values()
    )

    # 快照对比
    pre_eval = timeline.get("pre-eval", {})
    post_retest = timeline.get("post-retest", {})

    report = f"""# Hermes 自进化评估报告

> 生成时间：{datetime.now(timezone.utc).isoformat()}

## 概述

本报告评估 Hermes Agent 五层自进化机制在多轮、多会话场景下的实际效果。
通过三阶段实验（基线 → 进化 → 重测），量化进化前后的性能差异。

## 评估配置

- **模型**: {DEFAULT_MODEL}
- **memory.nudge_interval**: 3 (默认 10)
- **memory.flush_min_turns**: 2 (默认 6)
- **skills.creation_nudge_interval**: 5 (默认 10)

## Phase A: 基线测试

| 任务 | 类型 | 工具调用 | 耗时(s) | Tokens | 完成 |
|------|------|---------|---------|--------|------|
"""

    for task_id in ("B1", "B2", "B3", "B4"):
        c = comparison.get(task_id, {}).get("baseline", {})
        task = BASELINE_TASKS[task_id]
        report += (
            f"| {task_id} | {task['type']} | "
            f"{c.get('tool_calls', 'N/A')} | "
            f"{c.get('duration', 'N/A')} | "
            f"{c.get('tokens', 'N/A')} | "
            f"{'✅' if c.get('completed') else '❌'} |\n"
        )

    report += f"""
## Phase B: 进化会话

### 进化机制触发统计

| 指标 | 数值 |
|------|------|
| memory 工具激活次数 | {total_memory_activations} |
| skill_manage 工具激活次数 | {total_skill_activations} |
| session_search 工具激活次数 | {total_search_activations} |

### 各 Session 详情

"""

    for sid, session in phase_b.items():
        report += f"""#### {sid}: {session.get('label', '')}

- 总工具调用: {session.get('total_tool_calls', 0)}
- 总耗时: {session.get('total_duration', 0):.1f}s
- 总 tokens: {session.get('total_tokens', 0)}
- memory 激活: {session.get('memory_tool_activations', 0)}
- skill_manage 激活: {session.get('skill_manage_activations', 0)}
- session_search 激活: {session.get('session_search_activations', 0)}

"""

    report += f"""### 进化产物增长

| 时间点 | MEMORY.md (chars) | USER.md (chars) | 用户 Skills | Sessions |
|--------|-------------------|-----------------|------------|----------|
"""

    for label in ("pre-eval", "after-E1", "after-E2", "after-E3", "after-E4", "pre-retest", "post-retest"):
        t = timeline.get(label, {})
        report += (
            f"| {label} | "
            f"{t.get('memory_md_chars', 0)} | "
            f"{t.get('user_md_chars', 0)} | "
            f"{t.get('user_skill_count', 0)} | "
            f"{t.get('session_count', 0)} |\n"
        )

    report += """
## Phase C: 进化后重测

| 任务 | 类型 | 工具调用 | 耗时(s) | Tokens | 完成 | 风格违规 |
|------|------|---------|---------|--------|------|---------|
"""

    for task_id in ("B1", "B2", "B3", "B4"):
        c = comparison.get(task_id, {}).get("post_evolution", {})
        task = BASELINE_TASKS[task_id]
        report += (
            f"| {task_id} | {task['type']} | "
            f"{c.get('tool_calls', 'N/A')} | "
            f"{c.get('duration', 'N/A')} | "
            f"{c.get('tokens', 'N/A')} | "
            f"{'✅' if c.get('completed') else '❌'} | "
            f"{c.get('style_violations', 'N/A')} |\n"
        )

    report += """
## Phase A vs Phase C 对比

| 任务 | 工具调用变化 | 耗时变化(s) | Token 变化 | 风格违规变化 |
|------|------------|------------|-----------|------------|
"""

    for task_id in ("B1", "B2", "B3", "B4"):
        d = comparison.get(task_id, {}).get("delta", {})
        report += (
            f"| {task_id} | "
            f"{d.get('tool_calls', 0):+d} | "
            f"{d.get('duration', 0):+.1f} | "
            f"{d.get('tokens', 0):+d} | "
            f"{d.get('style_violations', 0):+d} |\n"
        )

    report += f"""
## 进化优势分析

### 1. 记忆驱动的偏好一致性

Phase A（无记忆）vs Phase C（从 MEMORY.md/USER.md 加载偏好），
MEMORY.md 从 {pre_eval.get('memory_md_chars', 0)} chars 增长到 {post_retest.get('memory_md_chars', 0)} chars，
USER.md 从 {pre_eval.get('user_md_chars', 0)} chars 增长到 {post_retest.get('user_md_chars', 0)} chars。

### 2. 技能复用的效率提升

Phase B 中 skill_manage 被激活 {total_skill_activations} 次，
用户创建 skills 从 {pre_eval.get('user_skill_count', 0)} 个增长到 {post_retest.get('user_skill_count', 0)} 个。

### 3. 跨会话知识积累

session_search 在 Phase B 中被激活 {total_search_activations} 次（主要在 E3 跨会话搜索），
验证了 Layer 4 的会话搜索能力。

### 4. 对 CC/OC 的差异化优势

- **Claude Code**: 无持久记忆系统，无技能创建/复用机制，无跨会话搜索
- **OpenClaw**: 无自进化机制，无后台 nudge 自主学习
- **Hermes**: 5 层自进化（记忆 + 技能 + 用户画像 + 会话搜索 + 后台 review），
  是三框架中唯一具备自主学习和知识积累能力的 Agent

---

*报告由 hermes_evolution_eval.py 自动生成*
"""

    report_path = RESULTS_DIR / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n[report] 最终报告 → {report_path}")


# ── 主入口 ────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes 自进化评估")
    parser.add_argument(
        "--phase",
        choices=["A", "B", "C", "all"],
        default="all",
        help="执行指定阶段 (默认: all)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="仅从已有数据生成报告",
    )
    args = parser.parse_args()

    print(f"Hermes 自进化评估 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"结果目录: {RESULTS_DIR}")
    print(f"工作目录: {WORK_DIR}")

    if args.report:
        # 仅报告模式：从已有数据生成
        phase_a = json.loads((PHASE_A_DIR / "summary.json").read_text(encoding="utf-8"))
        phase_b = json.loads((PHASE_B_DIR / "summary.json").read_text(encoding="utf-8"))
        phase_c = json.loads((PHASE_C_DIR / "summary.json").read_text(encoding="utf-8"))
        comparison = generate_comparison(phase_a, phase_c)
        timeline = generate_evolution_timeline()
        generate_style_compliance_report(phase_c)
        generate_report(phase_a, phase_b, phase_c, comparison, timeline)
        return

    phase_a_data = {}
    phase_b_data = {}
    phase_c_data = {}

    if args.phase in ("A", "all"):
        phase_a_data = run_phase_a()

    if args.phase in ("B", "all"):
        phase_b_data = run_phase_b()

    if args.phase in ("C", "all"):
        phase_c_data = run_phase_c()

    # 生成分析报告
    if args.phase == "all":
        comparison = generate_comparison(phase_a_data, phase_c_data)
        timeline = generate_evolution_timeline()
        generate_style_compliance_report(phase_c_data)
        generate_report(
            phase_a_data, phase_b_data, phase_c_data, comparison, timeline
        )

    print("\n" + "=" * 70)
    print("评估完成！")
    print(f"结果目录: {RESULTS_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
