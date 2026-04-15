"""评分计算器 — 从原始分数生成加权最终分数和对比报告"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

# 评分维度权重
DIMENSION_WEIGHTS = {
    "correctness": 0.30,
    "completeness": 0.25,
    "quality": 0.20,
    "efficiency": 0.15,
    "autonomy": 0.10,
}

# 类别权重
CATEGORY_WEIGHTS = {
    "cat1": 0.25,
    "cat2": 0.25,
    "cat3": 0.25,
    "cat4": 0.25,
}

AGENTS = ["cc", "openclaw", "hermes"]

TASKS = {
    "cat1": ["task-1"],
    "cat2": ["task-2a", "task-2b", "task-2c", "task-2d"],
    "cat3": ["task-3a", "task-3b", "task-3c"],
    "cat4": ["task-4a", "task-4b", "task-4c"],
}


@dataclass
class TaskScore:
    correctness: float = 0.0
    completeness: float = 0.0
    quality: float = 0.0
    efficiency: float = 0.0
    autonomy: float = 0.0

    @property
    def weighted(self) -> float:
        return sum(
            getattr(self, dim) * w for dim, w in DIMENSION_WEIGHTS.items()
        )


def load_scores(scores_file: Path) -> dict[str, dict[str, TaskScore]]:
    """从 CSV 加载原始分数"""
    scores: dict[str, dict[str, TaskScore]] = {a: {} for a in AGENTS}
    if not scores_file.exists():
        return scores

    with open(scores_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            agent = row["agent"]
            task = row["task"]
            scores[agent][task] = TaskScore(
                correctness=float(row.get("correctness", 0)),
                completeness=float(row.get("completeness", 0)),
                quality=float(row.get("quality", 0)),
                efficiency=float(row.get("efficiency", 0)),
                autonomy=float(row.get("autonomy", 0)),
            )
    return scores


def compute_category_score(
    agent_scores: dict[str, TaskScore], tasks: list[str]
) -> float:
    """计算某个类别的加权平均分"""
    task_scores = [
        agent_scores[t].weighted for t in tasks if t in agent_scores
    ]
    return sum(task_scores) / len(task_scores) if task_scores else 0.0


def compute_final_score(agent_scores: dict[str, TaskScore]) -> float:
    """计算最终总分"""
    total = 0.0
    for cat, weight in CATEGORY_WEIGHTS.items():
        cat_score = compute_category_score(agent_scores, TASKS[cat])
        total += cat_score * weight
    return total


def generate_report(
    scores: dict[str, dict[str, TaskScore]], arena_dir: Path
) -> str:
    """生成 Markdown 对比报告"""
    lines = ["# AI Coding Agent 评估结果\n"]
    lines.append(f"生成时间: {__import__('datetime').datetime.now().isoformat()}\n")

    # 总分表
    lines.append("## 总分\n")
    lines.append("| Agent | Cat1 代码 | Cat2 浏览器 | Cat3 监控 | Cat4 交互 | **总分** |")
    lines.append("|-------|----------|-----------|---------|---------|---------|")

    for agent in AGENTS:
        cat_scores = []
        for cat in ["cat1", "cat2", "cat3", "cat4"]:
            cs = compute_category_score(scores[agent], TASKS[cat])
            cat_scores.append(cs)
        final = compute_final_score(scores[agent])
        lines.append(
            f"| {agent} | {cat_scores[0]:.1f} | {cat_scores[1]:.1f} | "
            f"{cat_scores[2]:.1f} | {cat_scores[3]:.1f} | **{final:.1f}** |"
        )

    # 详细分数
    lines.append("\n## 详细任务分数\n")
    for cat, tasks in TASKS.items():
        lines.append(f"### {cat}\n")
        lines.append("| Task | Agent | 正确性 | 完整性 | 质量 | 效率 | 自主性 | 加权分 |")
        lines.append("|------|-------|--------|--------|------|------|--------|--------|")
        for task in tasks:
            for agent in AGENTS:
                if task in scores[agent]:
                    s = scores[agent][task]
                    lines.append(
                        f"| {task} | {agent} | {s.correctness:.1f} | "
                        f"{s.completeness:.1f} | {s.quality:.1f} | "
                        f"{s.efficiency:.1f} | {s.autonomy:.1f} | "
                        f"{s.weighted:.1f} |"
                    )
        lines.append("")

    # 加载指标
    lines.append("## 效率指标\n")
    lines.append("| Agent | Task | 耗时(s) | 退出码 |")
    lines.append("|-------|------|---------|--------|")
    for agent in AGENTS:
        metrics_file = arena_dir / "results" / agent / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics = json.load(f)
            for task, m in sorted(metrics.items()):
                lines.append(
                    f"| {agent} | {task} | "
                    f"{m.get('duration_seconds', '-')} | "
                    f"{m.get('exit_code', '-')} |"
                )

    return "\n".join(lines)


def main() -> None:
    arena_dir = Path(__file__).parent.parent
    scores_file = arena_dir / "scoring" / "scores.csv"

    # 如果 CSV 不存在，创建模板
    if not scores_file.exists():
        print(f"创建评分模板: {scores_file}")
        with open(scores_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["agent", "task", "correctness", "completeness",
                 "quality", "efficiency", "autonomy", "notes"]
            )
            for agent in AGENTS:
                for tasks in TASKS.values():
                    for task in tasks:
                        writer.writerow([agent, task, 0, 0, 0, 0, 0, ""])
        print("请填写分数后重新运行")
        return

    scores = load_scores(scores_file)
    report = generate_report(scores, arena_dir)

    # 输出报告
    report_file = arena_dir / "reports" / "comparison-report.md"
    report_file.write_text(report)
    print(f"报告已生成: {report_file}")

    # 同时输出到终端
    print("\n" + report)


if __name__ == "__main__":
    main()
