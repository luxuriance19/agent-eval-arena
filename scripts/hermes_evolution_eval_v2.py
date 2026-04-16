#!/usr/bin/env python3
"""Hermes Self-Evolution Evaluation V2 — 反默认偏好控制变量实验.

通过 **反模型默认偏好** + **多次重复 (N=5)** + **控制组/实验组对比**，
用统计方法证明 Hermes 自进化机制的价值。

核心思路：选择模型默认不会选择的技术偏好，训练进 USER.md，
然后测量进化后的 agent 是否在 *未被提示* 时主动采用这些偏好。

三组实验：
  G1 (Control)  — skip_memory=True, 无记忆/画像/技能
  G2 (Fresh)    — 正常启动, 空白 MEMORY/USER
  G3 (Evolved)  — 正常启动, Phase B 训练后

用法:
    python hermes_evolution_eval_v2.py                    # 全部阶段
    python hermes_evolution_eval_v2.py --phase setup      # 仅环境准备
    python hermes_evolution_eval_v2.py --phase G2         # 仅 G2 评估
    python hermes_evolution_eval_v2.py --phase train      # 仅 Phase B 训练
    python hermes_evolution_eval_v2.py --phase G3         # 仅 G3 评估
    python hermes_evolution_eval_v2.py --phase G1         # 仅 G1 评估
    python hermes_evolution_eval_v2.py --phase analysis   # 仅统计分析
    python hermes_evolution_eval_v2.py --report           # 仅生成报告
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


# numpy bool/int/float 在 json.dumps 时不可序列化，需要自定义 encoder
class _NumpySafeEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy scalar types."""

    def default(self, o: object) -> object:
        try:
            import numpy as np
            if isinstance(o, (np.bool_, bool)):
                return bool(o)
            if isinstance(o, (np.integer,)):
                return int(o)
            if isinstance(o, (np.floating,)):
                return float(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
        except ImportError:
            pass
        return super().default(o)


def _json_dumps(obj: object, **kwargs: object) -> str:
    """json.dumps wrapper that handles numpy types."""
    return json.dumps(obj, cls=_NumpySafeEncoder, **kwargs)

# 将 hermes-agent 项目加入 sys.path
HERMES_ROOT = Path("/Users/lini03/baidu/hermes-agent")
sys.path.insert(0, str(HERMES_ROOT))

from run_agent import AIAgent  # noqa: E402

# ── 路径常量 ──────────────────────────────────────────────────
RESULTS_DIR = Path("/Users/lini03/baidu/agent-eval-arena/results/hermes/self-evolution-v2")
RAW_DIR = RESULTS_DIR / "raw"
TRAINING_DIR = RESULTS_DIR / "training"
SNAPSHOTS_DIR = RESULTS_DIR / "snapshots"
ANALYSIS_DIR = RESULTS_DIR / "analysis"

HERMES_HOME = Path.home() / ".hermes"
MEMORY_MD = HERMES_HOME / "memories" / "MEMORY.md"
USER_MD = HERMES_HOME / "memories" / "USER.md"
STATE_DB = HERMES_HOME / "state.db"
SKILLS_DIR = HERMES_HOME / "skills"

WORK_DIR = Path("/tmp/hermes-eval-v2")

# API 配置
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_BASE_URL = "http://api.dbh.baidu-int.com/v1"
DEFAULT_API_KEY = "sk-wZFlcMYI5UZg2iDYR3uvIY350NhVnpg4id3WNx6rFwpMWiEc"

# 后台 review 等待时间（秒）
BACKGROUND_REVIEW_WAIT = 10

# 重复次数（可通过 --runs 覆盖）
N_RUNS = 5


def _set_n_runs(n: int) -> None:
    """设置全局重复次数。"""
    global N_RUNS
    N_RUNS = n

# 实验组名称
GROUP_CONTROL = "G1-control"
GROUP_FRESH = "G2-fresh"
GROUP_EVOLVED = "G3-evolved"


# ── 数据类 ────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class RunResult:
    """单次评估执行结果。"""

    group: str
    task: str
    run: int
    tool_calls: list[dict]
    tool_call_count: int
    duration_s: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    final_response: str | None
    generated_files: dict[str, str]
    preference_compliance: dict[str, bool]
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


# ── 4 个评估任务 ──────────────────────────────────────────────
# 关键：prompt 不提及任何具体库名，让 agent 自主选择
EVAL_TASKS: dict[str, dict[str, str | list[str]]] = {
    "T1": {
        "description": "HTTP API 健康检查工具",
        "prompt": (
            f"在 {WORK_DIR}/t1 目录下创建一个 Python 项目：HTTP API 健康检查工具。\n"
            "功能要求：\n"
            "1. 从配置文件读取要监控的 API 端点列表（URL、预期状态码、超时时间）\n"
            "2. 并发检查所有端点的可用性\n"
            "3. 有结构化的日志输出（包括时间戳、检查结果、响应时间）\n"
            "4. 支持命令行参数指定配置文件路径和检查间隔\n"
            "5. 如果检查失败，支持指数退避重试\n"
            "请创建完整可运行的代码文件。"
        ),
        "applicable_preferences": [
            "httpx_not_requests",
            "loguru_not_logging",
            "toml_not_json_yaml",
            "click_not_argparse",
            "constants_py",
        ],
    },
    "T2": {
        "description": "文件格式转换器",
        "prompt": (
            f"在 {WORK_DIR}/t2 目录下创建一个 Python 项目：文件格式转换器。\n"
            "功能要求：\n"
            "1. 支持 JSON、YAML、TOML 三种格式之间的相互转换\n"
            "2. 对输入数据进行严格的结构验证（定义 schema）\n"
            "3. 优雅的错误处理——不要用裸 try/except，要有明确的错误类型和恢复策略\n"
            "4. 定义好所有配置常量（支持的格式列表、默认编码、最大文件大小等）\n"
            "请创建完整可运行的代码文件。"
        ),
        "applicable_preferences": [
            "msgspec_not_pydantic",
            "result_not_try_except",
            "constants_py",
            "toml_not_json_yaml",
        ],
    },
    "T3": {
        "description": "URL 短链服务核心模块",
        "prompt": (
            f"在 {WORK_DIR}/t3 目录下创建一个 Python 项目：URL 短链服务的核心模块。\n"
            "功能要求：\n"
            "1. URL 缩短和还原的核心逻辑（使用 hash + base62 编码）\n"
            "2. HTTP 客户端，带指数退避重试，用于检查 URL 可达性\n"
            "3. 配置管理模块——从配置文件加载服务参数\n"
            "4. 结构化日志记录\n"
            "5. 将所有魔法数字和常量集中管理\n"
            "请创建完整可运行的代码文件。"
        ),
        "applicable_preferences": [
            "httpx_not_requests",
            "toml_not_json_yaml",
            "loguru_not_logging",
            "constants_py",
        ],
    },
    "T4": {
        "description": "测试套件",
        "prompt": (
            f"为 {WORK_DIR}/t3 目录下的 URL 短链服务核心模块编写完整的测试套件。\n"
            "要求：\n"
            "1. 覆盖所有核心函数：URL 缩短、还原、重试逻辑、配置加载\n"
            "2. 使用参数化测试来覆盖多种输入场景（正常URL、空URL、超长URL、特殊字符等）\n"
            "3. Mock 所有外部 HTTP 调用\n"
            "4. 包含边界条件和异常路径的测试\n"
            "请创建完整的 test 文件。"
        ),
        "applicable_preferences": [
            "parametrize",
        ],
    },
}


# ── Phase B：进化训练轮次 ─────────────────────────────────────
TRAINING_SESSIONS: dict[str, dict[str, str | list[str]]] = {
    "E1": {
        "label": "偏好训练 (Layer 1+3)",
        "turns": [
            (
                "你好！我是百度后端 Python 开发者。以下是我团队的强制编码规范，"
                "请你在后续所有对话中严格遵守：\n"
                "1. HTTP 客户端只用 httpx，绝对不用 requests\n"
                "2. 日志只用 loguru（from loguru import logger），不用标准库 logging\n"
                "3. 配置文件只用 TOML 格式，不用 JSON 或 YAML\n"
                "4. 数据验证用 msgspec（import msgspec），不用 pydantic\n"
                "5. 错误处理用 Result 模式（from result import Ok, Err, Result），不用裸 try/except\n"
                "6. CLI 用 click，不用 argparse\n"
                "7. 所有常量集中到 constants.py，不允许魔法数字和内联字符串\n"
                "8. 测试必须用 @pytest.mark.parametrize，不允许写多个独立测试函数来测同一逻辑\n"
                "请确认你了解并会遵守这些规范。"
            ),
            (
                "HTTP 客户端只能用 httpx。理由：httpx 支持 async/sync 双模式，"
                "requests 不支持 async。我们团队已经全面迁移到 httpx。"
                "之后如果我让你写任何涉及 HTTP 请求的代码，必须用 httpx。"
            ),
            (
                "日志只用 loguru。理由：loguru 零配置开箱即用，自带彩色输出和文件轮转，"
                "比标准库 logging 简洁 10 倍。导入方式固定用 from loguru import logger。"
            ),
            (
                f"用 httpx 和 loguru 写一个简单的 HTTP 健康检查脚本，放在 {WORK_DIR}/train/check.py。"
                "检查 https://httpbin.org/get 是否返回 200。用 loguru 记录结果。"
            ),
            (
                "配置文件只用 TOML 格式。理由：TOML 语义清晰，Python 3.11+ 有 tomllib 内置支持。"
                "读取用 tomllib，写入用 tomli-w。绝对不用 JSON 配置，也不用 YAML。"
            ),
            (
                "数据验证用 msgspec，不用 pydantic。理由：msgspec 比 pydantic 快 5-10 倍，"
                "内存占用更低。定义 schema 用 msgspec.Struct 而不是 BaseModel。"
            ),
            (
                f"用 TOML 配置 + msgspec 验证写一个配置加载模块，放在 {WORK_DIR}/train/config_loader.py。"
                "定义一个 AppConfig(msgspec.Struct)，从 config.toml 加载。"
            ),
            (
                "错误处理用 Result 模式（result 库），不用裸 try/except。"
                "理由：Result 模式强制调用方处理错误，避免异常被吞掉。"
                "用法：from result import Ok, Err, Result。返回 Result[T, E] 代替 raise。"
            ),
            (
                "CLI 用 click，不用 argparse。理由：click 的装饰器 API 比 argparse 优雅。"
                "所有常量必须集中到 constants.py，禁止魔法数字。"
                "测试必须用 @pytest.mark.parametrize，不允许多个独立函数测同一逻辑。"
            ),
            (
                f"用 click 写一个 CLI 工具，放在 {WORK_DIR}/train/cli.py。"
                "支持 --config 指定配置文件路径（默认 config.toml），"
                "--verbose 启用详细日志。用 loguru 输出日志，用 TOML 加载配置。"
            ),
            (
                "所有魔法数字和字符串常量都必须集中到 constants.py 文件中。"
                "测试代码中，对于同一个函数的多种输入场景，必须用 @pytest.mark.parametrize "
                "写成一个参数化测试函数，而不是拆成多个独立的 test_ 函数。"
            ),
            (
                "请把我刚才说的所有编码偏好和规范总结保存到你的记忆里，"
                "确保以后每次对话你都能记住这些偏好并主动遵守。"
            ),
        ],
    },
    "E2": {
        "label": "技能训练 (Layer 2)",
        "turns": [
            (
                f"用 httpx + loguru 写一个带指数退避重试的 HTTP 请求装饰器，放在 {WORK_DIR}/train/retry.py。"
                "重试次数、退避基数、最大等待时间都放 constants.py。失败返回 Result 类型。"
            ),
            (
                f"把同样的重试模式应用到另一个 API 客户端，放在 {WORK_DIR}/train/api_client.py。"
                "用 httpx.AsyncClient 做异步请求，loguru 记录日志，msgspec 验证响应。"
            ),
            (
                "把我们刚才写的 retry 模式保存为一个 skill，名叫 'httpx-retry-pattern'。"
                "这样以后类似的场景可以直接复用。"
            ),
            (
                f"写一个标准的 TOML 配置加载 + msgspec 验证的通用模式，放在 {WORK_DIR}/train/toml_config.py。"
                "支持默认值、环境变量覆盖、类型安全的配置访问。"
            ),
            (
                "把 TOML 配置加载模式也保存为 skill，名叫 'toml-msgspec-config'。"
            ),
        ],
    },
    "E3": {
        "label": "跨会话搜索验证 (Layer 4)",
        "turns": [
            "搜索之前我们讨论过的编码偏好，特别是关于 HTTP 客户端和日志库的要求。",
            "回忆之前创建的 httpx-retry-pattern skill 的实现细节。",
            (
                f"结合我的偏好和之前的模式，在 {WORK_DIR}/train/new_tool.py 写一个"
                "API 限流检测工具：用 httpx 发请求、loguru 记日志、TOML 配置、"
                "msgspec 验证响应、Result 模式处理错误。"
            ),
        ],
    },
}


# ── 8 条反默认偏好的合规检测 ──────────────────────────────────
def check_compliance(generated_files: dict[str, str]) -> dict[str, bool]:
    """对生成的代码文件进行偏好合规检测。

    每条偏好同时检查正向条件（用了推荐库）和反向条件（没用默认库）。
    """
    all_code = "\n".join(generated_files.values())
    filenames = set(generated_files.keys())

    # 统计 try: 块数量（排除注释和字符串中的）
    bare_try_count = all_code.count("\ntry:") + all_code.count("\n    try:")
    has_result_pattern = "Result[" in all_code or "from result" in all_code

    return {
        "httpx_not_requests": (
            "import httpx" in all_code and "import requests" not in all_code
        ),
        "loguru_not_logging": (
            "from loguru" in all_code and "import logging" not in all_code
        ),
        "toml_not_json_yaml": (
            ("tomllib" in all_code or "tomli" in all_code)
            and ".toml" in all_code
            # 不检查 json 反向条件，因为 T2 任务本身涉及 JSON 格式转换
            and "yaml.safe_load" not in all_code
            and "yaml.load" not in all_code
        ),
        "msgspec_not_pydantic": (
            "msgspec" in all_code and "from pydantic" not in all_code
        ),
        "result_not_try_except": (
            has_result_pattern and bare_try_count <= 1
        ),
        "click_not_argparse": (
            "import click" in all_code and "import argparse" not in all_code
        ),
        "constants_py": any(
            Path(f).stem == "constants" for f in filenames
        ),
        "parametrize": "parametrize" in all_code,
    }


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
    skills: list[dict] = []
    if not SKILLS_DIR.exists():
        return skills

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
        if len(parts) >= 2:
            category = parts[0]
            skill_name = skill_md.parent.name
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
    """快照所有进化产物并持久化。"""
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
    out_path = SNAPSHOTS_DIR / f"{label}.json"
    out_path.write_text(
        _json_dumps(asdict(snap), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [snapshot] {label} -> {out_path}")
    return snap


def _extract_tool_calls(messages: list[dict]) -> list[dict]:
    """从消息历史中提取所有工具调用。"""
    calls: list[dict] = []
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


def _extract_generated_files(
    messages: list[dict],
    task_id: str | None = None,
) -> dict[str, str]:
    """从工具调用中提取 agent 写入的文件内容。

    扫描 write_file 工具调用的 arguments，提取 file_path 和 content。
    同时扫描 terminal 工具调用中的 cat > / tee / echo > 模式。
    """
    files: dict[str, str] = {}

    for msg in messages:
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            continue
        for tc in msg["tool_calls"]:
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "")

            if not raw_args:
                continue

            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except (json.JSONDecodeError, TypeError):
                continue

            if name == "write_file" and isinstance(args, dict):
                fpath = args.get("file_path", "")
                content = args.get("content", "")
                if fpath and content:
                    files[fpath] = content

            elif name == "patch" and isinstance(args, dict):
                # patch 工具也包含文件路径
                fpath = args.get("file_path", "")
                if fpath:
                    # patch 只有 diff，记录路径即可
                    files.setdefault(fpath, "")

    # 从磁盘读取任务对应子目录下实际生成的文件
    subdirs: list[str] | None = None
    if task_id:
        subdirs = [task_id.lower()]
        # T4 依赖 T3 的输出，也扫描 t3 目录
        if task_id == "T4":
            subdirs.append("t3")
    _scan_workdir_for_files(files, task_subdirs=subdirs)

    return files


def _scan_workdir_for_files(
    files: dict[str, str],
    task_subdirs: list[str] | None = None,
) -> None:
    """扫描 WORK_DIR 下指定子目录的文件，补充到 files dict 中。

    只扫描 task_subdirs 指定的子目录，避免跨任务污染。
    如果 task_subdirs 为 None，则扫描整个 WORK_DIR。
    """
    if not WORK_DIR.exists():
        return

    scan_dirs: list[Path] = []
    if task_subdirs:
        for sub in task_subdirs:
            d = WORK_DIR / sub
            if d.exists():
                scan_dirs.append(d)
    else:
        scan_dirs.append(WORK_DIR)

    for scan_dir in scan_dirs:
        for py_file in scan_dir.rglob("*.py"):
            fpath = str(py_file)
            if fpath not in files:
                try:
                    files[fpath] = py_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    pass
        for ext in ("*.toml", "*.json", "*.yaml", "*.yml"):
            for cfg_file in scan_dir.rglob(ext):
                fpath = str(cfg_file)
                if fpath not in files:
                    try:
                        files[fpath] = cfg_file.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        pass


# ── Agent 工厂 ────────────────────────────────────────────────
def create_control_agent(session_id: str) -> AIAgent:
    """G1 控制组：skip_memory=True 禁用所有进化能力。"""
    return AIAgent(
        model=DEFAULT_MODEL,
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        session_id=session_id,
        quiet_mode=True,
        max_iterations=90,
        skip_memory=True,
    )


def create_normal_agent(session_id: str) -> AIAgent:
    """G2/G3：正常 agent，记忆/技能由环境状态决定。"""
    return AIAgent(
        model=DEFAULT_MODEL,
        base_url=DEFAULT_BASE_URL,
        api_key=DEFAULT_API_KEY,
        session_id=session_id,
        quiet_mode=True,
        max_iterations=90,
    )


# ── 核心执行逻辑 ──────────────────────────────────────────────
def run_eval_task(
    *,
    group: str,
    task_id: str,
    run_num: int,
    agent: AIAgent,
) -> RunResult:
    """执行单次评估任务，返回 RunResult。"""
    task = EVAL_TASKS[task_id]
    prompt = task["prompt"]

    # 确保 WORK_DIR 干净
    task_work_dir = WORK_DIR / task_id.lower()
    if task_work_dir.exists():
        shutil.rmtree(task_work_dir)
    task_work_dir.mkdir(parents=True, exist_ok=True)

    session_id_tag = f"v2-{group}-{task_id}-run{run_num}"
    print(f"\n  [{session_id_tag}] Executing...")

    start = time.time()
    try:
        result = agent.run_conversation(user_message=prompt)
    except Exception as e:
        print(f"    [ERROR] {e}")
        return RunResult(
            group=group,
            task=task_id,
            run=run_num,
            tool_calls=[],
            tool_call_count=0,
            duration_s=round(time.time() - start, 2),
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
            final_response=f"ERROR: {e}",
            generated_files={},
            preference_compliance={k: False for k in [
                "httpx_not_requests", "loguru_not_logging",
                "toml_not_json_yaml", "msgspec_not_pydantic",
                "result_not_try_except", "click_not_argparse",
                "constants_py", "parametrize",
            ]},
            completed=False,
            memory_tool_used=False,
            skill_manage_used=False,
            session_search_used=False,
        )

    duration = time.time() - start
    messages = result.get("messages", [])
    tool_calls = _extract_tool_calls(messages)
    generated_files = _extract_generated_files(messages, task_id=task_id)
    compliance = check_compliance(generated_files)

    run_result = RunResult(
        group=group,
        task=task_id,
        run=run_num,
        tool_calls=tool_calls,
        tool_call_count=len(tool_calls),
        duration_s=round(duration, 2),
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        total_tokens=result.get("total_tokens", 0),
        estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
        final_response=result.get("final_response"),
        generated_files=generated_files,
        preference_compliance=compliance,
        completed=result.get("completed", False),
        memory_tool_used=_has_tool(tool_calls, "memory"),
        skill_manage_used=_has_tool(tool_calls, "skill_manage"),
        session_search_used=_has_tool(tool_calls, "session_search"),
    )

    # 显示合规情况
    applicable = task.get("applicable_preferences", [])
    matched = sum(1 for p in applicable if compliance.get(p, False))
    print(
        f"    Done: {duration:.1f}s | tools: {len(tool_calls)} | "
        f"tokens: {result.get('total_tokens', 0)} | "
        f"compliance: {matched}/{len(applicable)} | "
        f"files: {len(generated_files)}"
    )

    return run_result


def save_run_result(run_result: RunResult) -> Path:
    """保存单次执行结果到 JSON 文件。"""
    out_dir = RAW_DIR / run_result.group / run_result.task
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"run-{run_result.run}.json"

    # generated_files 可能很大，截断 content 用于存储
    trimmed_files: dict[str, str] = {}
    for fpath, content in run_result.generated_files.items():
        trimmed_files[fpath] = content[:5000] if len(content) > 5000 else content

    data = asdict(run_result)
    data["generated_files"] = trimmed_files

    out_path.write_text(
        _json_dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


# ── 多轮训练会话 ──────────────────────────────────────────────
def run_training_session(
    session_id: str,
    turns: list[str],
    session_label: str,
) -> list[dict]:
    """按顺序发送多轮训练消息，记录每轮结果。"""
    agent = create_normal_agent(session_id=session_id)
    results: list[dict] = []
    messages: list[dict] = []

    print(f"\n{'=' * 60}")
    print(f"Training session: {session_label} ({len(turns)} turns)")
    print(f"{'=' * 60}")

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
            results.append({
                "turn": turn_num,
                "prompt": turn_prompt,
                "response": f"ERROR: {e}",
                "duration_s": round(time.time() - start, 2),
                "completed": False,
            })
            continue

        duration = time.time() - start
        messages = result.get("messages", [])
        tool_calls = _extract_tool_calls(messages)

        prev_tc_count = sum(r.get("tool_call_count", 0) for r in results)
        turn_tool_calls = tool_calls[prev_tc_count:]

        turn_data = {
            "turn": turn_num,
            "prompt": turn_prompt,
            "response": result.get("final_response"),
            "tool_calls": turn_tool_calls,
            "tool_call_count": len(turn_tool_calls),
            "duration_s": round(duration, 2),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "total_tokens": result.get("total_tokens", 0),
            "completed": result.get("completed", False),
            "memory_tool_used": _has_tool(turn_tool_calls, "memory"),
            "skill_manage_used": _has_tool(turn_tool_calls, "skill_manage"),
            "session_search_used": _has_tool(turn_tool_calls, "session_search"),
        }
        results.append(turn_data)

        print(
            f"    Done: {duration:.1f}s | tools: {len(turn_tool_calls)} | "
            f"mem: {'Y' if turn_data['memory_tool_used'] else 'N'} | "
            f"skill: {'Y' if turn_data['skill_manage_used'] else 'N'} | "
            f"search: {'Y' if turn_data['session_search_used'] else 'N'}"
        )

        # 等待后台 review 线程
        if i < len(turns) - 1:
            time.sleep(BACKGROUND_REVIEW_WAIT)

    return results


# ── 环境准备 ──────────────────────────────────────────────────
def setup_environment() -> None:
    """创建结果目录结构并备份现有进化产物。"""
    print("\n=== 环境准备 ===")

    # 创建目录结构
    for d in [RAW_DIR, TRAINING_DIR, SNAPSHOTS_DIR, ANALYSIS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    for group in [GROUP_CONTROL, GROUP_FRESH, GROUP_EVOLVED]:
        for task_id in EVAL_TASKS:
            (RAW_DIR / group / task_id).mkdir(parents=True, exist_ok=True)

    # 创建工作目录
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    print("  [ok] 目录结构已创建")


def reset_evolution_state() -> None:
    """清空进化产物（MEMORY.md, USER.md, 用户 skills）。"""
    print("\n=== 重置进化状态 ===")

    # 备份
    backup_dir = Path("/tmp/hermes-memories-backup-v2")
    if HERMES_HOME.exists():
        if (HERMES_HOME / "memories").exists():
            shutil.copytree(
                HERMES_HOME / "memories",
                backup_dir / "memories",
                dirs_exist_ok=True,
            )
        if SKILLS_DIR.exists():
            shutil.copytree(
                SKILLS_DIR,
                backup_dir / "skills",
                dirs_exist_ok=True,
            )
        print(f"  [backup] -> {backup_dir}")

    # 清空 MEMORY.md 和 USER.md
    MEMORY_MD.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_MD.write_text("", encoding="utf-8")
    USER_MD.write_text("", encoding="utf-8")
    print("  [reset] MEMORY.md and USER.md cleared")

    # 删除用户创建的 skills（保留 bundled）
    if SKILLS_DIR.exists():
        bundled_names: set[str] = set()
        manifest = SKILLS_DIR / ".bundled_manifest"
        if manifest.exists():
            for line in _read_file_safe(manifest).splitlines():
                line = line.strip()
                if ":" in line:
                    bundled_names.add(line.split(":")[0])

        for skill_md in list(SKILLS_DIR.rglob("SKILL.md")):
            skill_name = skill_md.parent.name
            if skill_name not in bundled_names:
                skill_dir = skill_md.parent
                shutil.rmtree(skill_dir, ignore_errors=True)
                print(f"  [removed] skill: {skill_name}")

    print("  [ok] 进化状态已重置")


# ── Phase 执行 ────────────────────────────────────────────────
def run_group_evaluation(group: str) -> list[RunResult]:
    """执行某个实验组的全部评估任务 (4 tasks × N runs)。"""
    print(f"\n{'#' * 60}")
    print(f"# 实验组: {group} ({len(EVAL_TASKS)} tasks x {N_RUNS} runs)")
    print(f"{'#' * 60}")

    all_results: list[RunResult] = []

    for task_id in EVAL_TASKS:
        for run_num in range(1, N_RUNS + 1):
            session_id = f"v2-{group}-{task_id}-run{run_num}"

            if group == GROUP_CONTROL:
                agent = create_control_agent(session_id=session_id)
            else:
                agent = create_normal_agent(session_id=session_id)

            run_result = run_eval_task(
                group=group,
                task_id=task_id,
                run_num=run_num,
                agent=agent,
            )
            all_results.append(run_result)
            save_run_result(run_result)

            # 清理工作目录中该任务的输出（保证下一次 run 是干净的）
            task_work_dir = WORK_DIR / task_id.lower()
            if task_work_dir.exists():
                shutil.rmtree(task_work_dir, ignore_errors=True)

    # 保存该组的汇总
    summary_path = RAW_DIR / group / "summary.json"
    summary_data = [asdict(r) for r in all_results]
    # 截断 generated_files
    for d in summary_data:
        trimmed: dict[str, str] = {}
        for fp, c in d.get("generated_files", {}).items():
            trimmed[fp] = c[:2000] if len(c) > 2000 else c
        d["generated_files"] = trimmed

    summary_path.write_text(
        _json_dumps(summary_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  [saved] {summary_path}")
    return all_results


def run_phase_b_training() -> dict[str, list[dict]]:
    """Phase B：进化训练。"""
    print(f"\n{'#' * 60}")
    print("# Phase B: 进化训练")
    print(f"{'#' * 60}")

    # 训练前快照
    snapshot_evolution_state("pre-training")

    all_training: dict[str, list[dict]] = {}

    for sid, session_def in TRAINING_SESSIONS.items():
        label = session_def["label"]
        turns = session_def["turns"]

        results = run_training_session(
            session_id=f"v2-train-{sid}",
            turns=turns,
            session_label=f"{sid}: {label}",
        )
        all_training[sid] = results

        # 保存训练结果
        out_path = TRAINING_DIR / f"{sid}-{label.split()[0]}.json"
        out_path.write_text(
            _json_dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  [saved] {out_path}")

        # 训练后快照
        snapshot_evolution_state(f"after-{sid}")

        # 等待后台 review
        time.sleep(BACKGROUND_REVIEW_WAIT)

    return all_training


def verify_training() -> dict[str, bool]:
    """验证训练成果：USER.md 是否包含全部 8 条偏好。"""
    print("\n=== 训练验证 ===")
    user_content = _read_file_safe(USER_MD)
    memory_content = _read_file_safe(MEMORY_MD)
    all_content = user_content + "\n" + memory_content

    checks = {
        "httpx": "httpx" in all_content.lower(),
        "loguru": "loguru" in all_content.lower(),
        "toml": "toml" in all_content.lower(),
        "msgspec": "msgspec" in all_content.lower(),
        "result_pattern": "result" in all_content.lower() and ("ok" in all_content.lower() or "err" in all_content.lower()),
        "click": "click" in all_content.lower(),
        "constants": "constants" in all_content.lower() or "constant" in all_content.lower(),
        "parametrize": "parametrize" in all_content.lower(),
    }

    user_skills = _list_user_skills()
    checks["skills_created"] = len(user_skills) > 0

    for key, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {key}")

    print(f"\n  USER.md ({len(user_content)} chars):")
    for line in user_content.splitlines()[:20]:
        print(f"    {line}")

    print(f"\n  MEMORY.md ({len(memory_content)} chars):")
    for line in memory_content.splitlines()[:10]:
        print(f"    {line}")

    print(f"\n  User skills: {len(user_skills)}")
    for s in user_skills:
        print(f"    - {s['category']}/{s['name']} ({s['chars']} chars)")

    # 保存验证结果
    verify_path = TRAINING_DIR / "verification.json"
    verify_path.write_text(
        _json_dumps({
            "checks": checks,
            "user_md_chars": len(user_content),
            "memory_md_chars": len(memory_content),
            "user_skills": [{"name": s["name"], "chars": s["chars"]} for s in user_skills],
            "all_passed": all(checks.values()),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return checks


# ── 统计分析 ──────────────────────────────────────────────────
def compute_compliance_scores(
    results: list[RunResult],
) -> dict[str, list[float]]:
    """按任务计算每次执行的偏好合规率。

    返回: {task_id: [score_run1, score_run2, ...]}
    score = 满足的适用偏好数 / 适用偏好总数
    """
    scores: dict[str, list[float]] = {}
    for r in results:
        task = r.task
        applicable = EVAL_TASKS[task].get("applicable_preferences", [])
        if not applicable:
            continue
        n_match = sum(1 for p in applicable if r.preference_compliance.get(p, False))
        score = n_match / len(applicable)
        scores.setdefault(task, []).append(score)
    return scores


def cliffs_delta(x: list[float], y: list[float]) -> float:
    """计算 Cliff's delta 效果大小。"""
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return 0.0
    count = 0
    for xi in x:
        for yj in y:
            if xi > yj:
                count += 1
            elif xi < yj:
                count -= 1
    return count / (n_x * n_y)


def interpret_cliffs_delta(d: float) -> str:
    """解读 Cliff's delta 大小。"""
    d_abs = abs(d)
    if d_abs < 0.147:
        return "negligible"
    if d_abs < 0.33:
        return "small"
    if d_abs < 0.474:
        return "medium"
    return "large"


def run_statistical_analysis(
    g1_results: list[RunResult],
    g2_results: list[RunResult],
    g3_results: list[RunResult],
) -> dict:
    """执行完整的统计分析。"""
    print("\n=== 统计分析 ===")

    # 尝试导入 scipy，降级处理
    try:
        from scipy.stats import mannwhitneyu, wilcoxon
        has_scipy = True
    except ImportError:
        print("  [WARN] scipy 未安装，跳过统计检验，仅计算描述性统计")
        has_scipy = False

    g1_scores = compute_compliance_scores(g1_results)
    g2_scores = compute_compliance_scores(g2_results)
    g3_scores = compute_compliance_scores(g3_results)

    analysis: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_runs": N_RUNS,
        "per_task": {},
        "overall": {},
    }

    # 每个任务的分析
    for task_id in EVAL_TASKS:
        s1 = g1_scores.get(task_id, [])
        s2 = g2_scores.get(task_id, [])
        s3 = g3_scores.get(task_id, [])

        task_analysis: dict = {
            "G1_control": {
                "scores": s1,
                "mean": sum(s1) / len(s1) if s1 else 0,
                "n": len(s1),
            },
            "G2_fresh": {
                "scores": s2,
                "mean": sum(s2) / len(s2) if s2 else 0,
                "n": len(s2),
            },
            "G3_evolved": {
                "scores": s3,
                "mean": sum(s3) / len(s3) if s3 else 0,
                "n": len(s3),
            },
        }

        # G1 vs G3: Mann-Whitney U（独立样本）
        if has_scipy and len(s1) >= 2 and len(s3) >= 2:
            try:
                stat, p_val = mannwhitneyu(s3, s1, alternative="greater")
                task_analysis["G1_vs_G3_mann_whitney"] = {
                    "U_statistic": float(stat),
                    "p_value": float(p_val),
                    "significant": p_val < 0.05,
                }
            except ValueError:
                task_analysis["G1_vs_G3_mann_whitney"] = {"error": "insufficient variation"}

        # G2 vs G3: Wilcoxon 符号秩检验（配对样本）
        if has_scipy and len(s2) == len(s3) and len(s2) >= 2:
            try:
                # 检查是否有差异（全相同则无法检验）
                diffs = [a - b for a, b in zip(s3, s2)]
                if any(d != 0 for d in diffs):
                    stat, p_val = wilcoxon(s3, s2, alternative="greater")
                    task_analysis["G2_vs_G3_wilcoxon"] = {
                        "W_statistic": float(stat),
                        "p_value": float(p_val),
                        "significant": p_val < 0.05,
                    }
                else:
                    task_analysis["G2_vs_G3_wilcoxon"] = {"error": "no differences between pairs"}
            except ValueError as e:
                task_analysis["G2_vs_G3_wilcoxon"] = {"error": str(e)}

        # Cliff's delta
        if s1 and s3:
            d_val = cliffs_delta(s3, s1)
            task_analysis["G1_vs_G3_cliffs_delta"] = {
                "delta": round(d_val, 4),
                "interpretation": interpret_cliffs_delta(d_val),
            }
        if s2 and s3:
            d_val = cliffs_delta(s3, s2)
            task_analysis["G2_vs_G3_cliffs_delta"] = {
                "delta": round(d_val, 4),
                "interpretation": interpret_cliffs_delta(d_val),
            }

        analysis["per_task"][task_id] = task_analysis

    # 总体分析（合并所有任务的得分）
    all_s1 = [s for scores in g1_scores.values() for s in scores]
    all_s2 = [s for scores in g2_scores.values() for s in scores]
    all_s3 = [s for scores in g3_scores.values() for s in scores]

    analysis["overall"] = {
        "G1_control": {"mean": sum(all_s1) / len(all_s1) if all_s1 else 0, "n": len(all_s1)},
        "G2_fresh": {"mean": sum(all_s2) / len(all_s2) if all_s2 else 0, "n": len(all_s2)},
        "G3_evolved": {"mean": sum(all_s3) / len(all_s3) if all_s3 else 0, "n": len(all_s3)},
    }

    if has_scipy and len(all_s1) >= 2 and len(all_s3) >= 2:
        try:
            stat, p_val = mannwhitneyu(all_s3, all_s1, alternative="greater")
            analysis["overall"]["G1_vs_G3_mann_whitney"] = {
                "U_statistic": float(stat),
                "p_value": float(p_val),
                "significant": p_val < 0.05,
            }
        except ValueError:
            pass

    if all_s1 and all_s3:
        d_val = cliffs_delta(all_s3, all_s1)
        analysis["overall"]["G1_vs_G3_cliffs_delta"] = {
            "delta": round(d_val, 4),
            "interpretation": interpret_cliffs_delta(d_val),
        }

    # 偏好合规矩阵 (8 preferences × 3 groups)
    # 只统计该偏好适用的任务对应的 run
    preference_matrix: dict[str, dict[str, dict[str, float | int]]] = {}
    all_preferences = [
        "httpx_not_requests", "loguru_not_logging", "toml_not_json_yaml",
        "msgspec_not_pydantic", "result_not_try_except", "click_not_argparse",
        "constants_py", "parametrize",
    ]

    # 构建每个偏好适用的任务集
    pref_applicable_tasks: dict[str, set[str]] = {}
    for task_id, task_def in EVAL_TASKS.items():
        for p in task_def.get("applicable_preferences", []):
            pref_applicable_tasks.setdefault(p, set()).add(task_id)

    for pref in all_preferences:
        applicable_tasks = pref_applicable_tasks.get(pref, set())

        def _filter(results: list[RunResult]) -> list[RunResult]:
            if not applicable_tasks:
                return results
            return [r for r in results if r.task in applicable_tasks]

        g1_applicable = _filter(g1_results)
        g2_applicable = _filter(g2_results)
        g3_applicable = _filter(g3_results)

        g1_count = sum(1 for r in g1_applicable if r.preference_compliance.get(pref, False))
        g2_count = sum(1 for r in g2_applicable if r.preference_compliance.get(pref, False))
        g3_count = sum(1 for r in g3_applicable if r.preference_compliance.get(pref, False))
        n1, n2, n3 = len(g1_applicable), len(g2_applicable), len(g3_applicable)

        preference_matrix[pref] = {
            "G1_control": {"count": g1_count, "total": n1, "rate": g1_count / n1 if n1 else 0},
            "G2_fresh": {"count": g2_count, "total": n2, "rate": g2_count / n2 if n2 else 0},
            "G3_evolved": {"count": g3_count, "total": n3, "rate": g3_count / n3 if n3 else 0},
            "applicable_tasks": sorted(applicable_tasks),
        }

    analysis["preference_matrix"] = preference_matrix

    # 保存
    stat_path = ANALYSIS_DIR / "statistical-tests.json"
    stat_path.write_text(
        _json_dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [saved] {stat_path}")

    compliance_path = ANALYSIS_DIR / "preference-compliance.json"
    compliance_path.write_text(
        _json_dumps(preference_matrix, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  [saved] {compliance_path}")

    # 打印摘要
    print("\n  === 偏好合规率总览 ===")
    print(f"  {'偏好':<25} {'G1(Control)':<15} {'G2(Fresh)':<15} {'G3(Evolved)':<15}")
    print(f"  {'-'*70}")
    for pref in all_preferences:
        pm = preference_matrix[pref]
        g1r = f"{pm['G1_control']['rate']:.0%}"
        g2r = f"{pm['G2_fresh']['rate']:.0%}"
        g3r = f"{pm['G3_evolved']['rate']:.0%}"
        print(f"  {pref:<25} {g1r:<15} {g2r:<15} {g3r:<15}")

    print(f"\n  总体合规率: G1={analysis['overall']['G1_control']['mean']:.2%}  "
          f"G2={analysis['overall']['G2_fresh']['mean']:.2%}  "
          f"G3={analysis['overall']['G3_evolved']['mean']:.2%}")

    return analysis


# ── 报告生成 ──────────────────────────────────────────────────
def generate_report(analysis: dict) -> None:
    """生成 Markdown 报告。"""
    print("\n=== 生成报告 ===")

    report_path = RESULTS_DIR / "report.md"
    lines: list[str] = []

    lines.append("# Hermes 自进化评估 V2 — 反默认偏好控制变量实验\n")
    lines.append(f"生成时间: {datetime.now(timezone.utc).isoformat()}\n")
    lines.append(f"模型: {DEFAULT_MODEL}\n")
    lines.append(f"重复次数: N={N_RUNS}\n")

    # 实验设计
    lines.append("\n## 1. 实验设计\n")
    lines.append("### 核心思路\n")
    lines.append(
        "选择 **模型默认不会选择** 的技术偏好（如 httpx 代替 requests、loguru 代替 logging），"
        "训练进 USER.md，然后测量进化后的 agent 是否在 **未被提示** 时主动采用这些偏好。\n"
    )
    lines.append("### 三个实验组\n")
    lines.append("| 组 | 名称 | 配置 |")
    lines.append("|---|------|------|")
    lines.append("| G1 | 控制组 (Control) | `skip_memory=True`，无记忆/画像/技能 |")
    lines.append("| G2 | 进化前基线 (Fresh) | 正常启动，空白 MEMORY/USER |")
    lines.append("| G3 | 进化后 (Evolved) | 正常启动，Phase B 训练后 |\n")

    lines.append("### 8 条反默认偏好\n")
    lines.append("| # | 偏好 | 默认行为 | 反默认要求 |")
    lines.append("|---|------|---------|-----------|")
    lines.append("| 1 | HTTP 客户端 | requests | httpx |")
    lines.append("| 2 | 日志库 | logging | loguru |")
    lines.append("| 3 | 配置格式 | JSON/YAML | TOML |")
    lines.append("| 4 | 数据验证 | pydantic | msgspec |")
    lines.append("| 5 | 错误处理 | try/except | Result 模式 |")
    lines.append("| 6 | CLI 框架 | argparse | click |")
    lines.append("| 7 | 常量管理 | 魔法数字 | constants.py |")
    lines.append("| 8 | 测试参数化 | 独立函数 | @pytest.mark.parametrize |\n")

    # 训练成果
    lines.append("\n## 2. 训练成果\n")
    verify_path = TRAINING_DIR / "verification.json"
    if verify_path.exists():
        verify_data = json.loads(verify_path.read_text(encoding="utf-8"))
        lines.append(f"- USER.md: {verify_data.get('user_md_chars', 0)} chars")
        lines.append(f"- MEMORY.md: {verify_data.get('memory_md_chars', 0)} chars")
        lines.append(f"- Skills: {len(verify_data.get('user_skills', []))} 个")
        lines.append("")
        lines.append("偏好检测:")
        for check, passed in verify_data.get("checks", {}).items():
            status = "PASS" if passed else "FAIL"
            lines.append(f"- [{status}] {check}")
        lines.append("")

    # 偏好合规率对比
    lines.append("\n## 3. 偏好合规率对比\n")
    pm = analysis.get("preference_matrix", {})
    if pm:
        lines.append("| 偏好 | G1 (Control) | G2 (Fresh) | G3 (Evolved) | G3-G1 Delta |")
        lines.append("|------|:---:|:---:|:---:|:---:|")
        for pref in [
            "httpx_not_requests", "loguru_not_logging", "toml_not_json_yaml",
            "msgspec_not_pydantic", "result_not_try_except", "click_not_argparse",
            "constants_py", "parametrize",
        ]:
            if pref in pm:
                g1r = pm[pref]["G1_control"]["rate"]
                g2r = pm[pref]["G2_fresh"]["rate"]
                g3r = pm[pref]["G3_evolved"]["rate"]
                delta = g3r - g1r
                delta_str = f"+{delta:.0%}" if delta > 0 else f"{delta:.0%}"
                lines.append(
                    f"| {pref} | {g1r:.0%} | {g2r:.0%} | {g3r:.0%} | {delta_str} |"
                )
        lines.append("")

    # 统计检验结果
    lines.append("\n## 4. 统计检验结果\n")

    lines.append("### 4.1 分任务结果\n")
    for task_id in EVAL_TASKS:
        task_data = analysis.get("per_task", {}).get(task_id, {})
        if not task_data:
            continue
        lines.append(f"#### {task_id}: {EVAL_TASKS[task_id]['description']}\n")

        g1_mean = task_data.get("G1_control", {}).get("mean", 0)
        g2_mean = task_data.get("G2_fresh", {}).get("mean", 0)
        g3_mean = task_data.get("G3_evolved", {}).get("mean", 0)
        lines.append(f"- 合规率: G1={g1_mean:.2%}, G2={g2_mean:.2%}, G3={g3_mean:.2%}")

        mw = task_data.get("G1_vs_G3_mann_whitney", {})
        if "p_value" in mw:
            sig = "YES" if mw["significant"] else "no"
            lines.append(f"- G1 vs G3 Mann-Whitney: p={mw['p_value']:.4f} (significant: {sig})")

        wt = task_data.get("G2_vs_G3_wilcoxon", {})
        if "p_value" in wt:
            sig = "YES" if wt["significant"] else "no"
            lines.append(f"- G2 vs G3 Wilcoxon: p={wt['p_value']:.4f} (significant: {sig})")

        cd1 = task_data.get("G1_vs_G3_cliffs_delta", {})
        if "delta" in cd1:
            lines.append(f"- G1 vs G3 Cliff's delta: {cd1['delta']:.4f} ({cd1['interpretation']})")

        cd2 = task_data.get("G2_vs_G3_cliffs_delta", {})
        if "delta" in cd2:
            lines.append(f"- G2 vs G3 Cliff's delta: {cd2['delta']:.4f} ({cd2['interpretation']})")
        lines.append("")

    lines.append("### 4.2 总体结果\n")
    overall = analysis.get("overall", {})
    g1_overall = overall.get("G1_control", {}).get("mean", 0)
    g2_overall = overall.get("G2_fresh", {}).get("mean", 0)
    g3_overall = overall.get("G3_evolved", {}).get("mean", 0)
    lines.append(f"- 总体合规率: G1={g1_overall:.2%}, G2={g2_overall:.2%}, G3={g3_overall:.2%}")

    mw_overall = overall.get("G1_vs_G3_mann_whitney", {})
    if "p_value" in mw_overall:
        sig = "YES" if mw_overall["significant"] else "no"
        lines.append(f"- G1 vs G3 Mann-Whitney: p={mw_overall['p_value']:.4f} (significant: {sig})")

    cd_overall = overall.get("G1_vs_G3_cliffs_delta", {})
    if "delta" in cd_overall:
        lines.append(f"- G1 vs G3 Cliff's delta: {cd_overall['delta']:.4f} ({cd_overall['interpretation']})")
    lines.append("")

    # 结论
    lines.append("\n## 5. 结论\n")

    # 根据数据自动判断
    if g3_overall > g1_overall + 0.2:
        p_val_str = ""
        if "p_value" in mw_overall:
            p_val_str = f"(p={mw_overall['p_value']:.4f})"
        lines.append(
            f"G3 (Evolved) 的总体偏好合规率 ({g3_overall:.0%}) 显著高于 "
            f"G1 (Control, {g1_overall:.0%}) {p_val_str}，"
            "表明 Hermes 自进化机制成功将用户偏好内化并在后续任务中主动采用。"
        )
    elif g3_overall > g1_overall:
        lines.append(
            f"G3 (Evolved, {g3_overall:.0%}) 略高于 G1 (Control, {g1_overall:.0%})，"
            "进化效果有限，可能需要更强的训练信号或更多的训练轮次。"
        )
    else:
        lines.append(
            f"G3 (Evolved, {g3_overall:.0%}) 未优于 G1 (Control, {g1_overall:.0%})，"
            "当前进化训练未产生预期效果。需要检查训练流程和偏好存储机制。"
        )
    lines.append("")

    # 写入文件
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [saved] {report_path}")


# ── 从已有 JSON 加载结果 ──────────────────────────────────────
def load_group_results(group: str) -> list[RunResult]:
    """从磁盘加载某组的全部 RunResult。"""
    results: list[RunResult] = []
    group_dir = RAW_DIR / group

    for task_id in EVAL_TASKS:
        for run_num in range(1, N_RUNS + 1):
            json_path = group_dir / task_id / f"run-{run_num}.json"
            if not json_path.exists():
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                results.append(RunResult(
                    group=data["group"],
                    task=data["task"],
                    run=data["run"],
                    tool_calls=data.get("tool_calls", []),
                    tool_call_count=data.get("tool_call_count", 0),
                    duration_s=data.get("duration_s", 0),
                    input_tokens=data.get("input_tokens", 0),
                    output_tokens=data.get("output_tokens", 0),
                    total_tokens=data.get("total_tokens", 0),
                    estimated_cost_usd=data.get("estimated_cost_usd", 0),
                    final_response=data.get("final_response"),
                    generated_files=data.get("generated_files", {}),
                    preference_compliance=data.get("preference_compliance", {}),
                    completed=data.get("completed", False),
                    memory_tool_used=data.get("memory_tool_used", False),
                    skill_manage_used=data.get("skill_manage_used", False),
                    session_search_used=data.get("session_search_used", False),
                ))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  [WARN] Failed to load {json_path}: {e}")
    return results


# ── 主入口 ────────────────────────────────────────────────────
def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="Hermes Self-Evolution Evaluation V2",
    )
    parser.add_argument(
        "--phase",
        choices=["setup", "G2", "train", "G3", "G1", "analysis", "all"],
        default="all",
        help="执行哪个阶段 (default: all)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="仅从已有数据生成报告",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=N_RUNS,
        help=f"每组每任务的重复次数 (default: {N_RUNS})",
    )
    args = parser.parse_args()

    _set_n_runs(args.runs)

    print(f"\nHermes Self-Evolution Evaluation V2")
    print(f"Model: {DEFAULT_MODEL}")
    print(f"Runs per group per task: {N_RUNS}")
    print(f"Total executions: {3 * len(EVAL_TASKS) * N_RUNS}")

    if args.report:
        g1 = load_group_results(GROUP_CONTROL)
        g2 = load_group_results(GROUP_FRESH)
        g3 = load_group_results(GROUP_EVOLVED)
        analysis = run_statistical_analysis(g1, g2, g3)
        generate_report(analysis)
        return

    g1_results: list[RunResult] = []
    g2_results: list[RunResult] = []
    g3_results: list[RunResult] = []

    if args.phase in ("setup", "all"):
        setup_environment()
        reset_evolution_state()

    if args.phase in ("G2", "all"):
        if args.phase == "G2":
            setup_environment()
        print("\n\n>>> Phase: G2-fresh 评估（训练前基线）")
        g2_results = run_group_evaluation(GROUP_FRESH)

    if args.phase in ("train", "all"):
        if args.phase == "train":
            setup_environment()
        print("\n\n>>> Phase: B 训练")
        run_phase_b_training()
        verify_training()

    if args.phase in ("G3", "all"):
        if args.phase == "G3":
            setup_environment()
        print("\n\n>>> Phase: G3-evolved 评估（训练后）")
        g3_results = run_group_evaluation(GROUP_EVOLVED)

    if args.phase in ("G1", "all"):
        if args.phase == "G1":
            setup_environment()
        print("\n\n>>> Phase: G1-control 评估（控制组）")
        g1_results = run_group_evaluation(GROUP_CONTROL)

    if args.phase in ("analysis", "all"):
        # 如果不是 all 模式，从磁盘加载
        if not g1_results:
            g1_results = load_group_results(GROUP_CONTROL)
        if not g2_results:
            g2_results = load_group_results(GROUP_FRESH)
        if not g3_results:
            g3_results = load_group_results(GROUP_EVOLVED)

        analysis = run_statistical_analysis(g1_results, g2_results, g3_results)
        generate_report(analysis)

    print("\n\n=== V2 评估完成 ===")
    print(f"结果目录: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
