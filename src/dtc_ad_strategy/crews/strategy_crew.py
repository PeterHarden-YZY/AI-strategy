"""Crew B —— 策略层（§6，纯推理，不调工具）。

S0 策略合成 → S1 素材 Brief → S1b 渲染 creative_brief.md → S2 报告汇总。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crewai import Crew, Process

from .. import paths, router
from ..config import build_agent
from ..schemas import Task6Strategy, Task7Creative
from .base import build_context_text, build_task

logger = logging.getLogger(__name__)

JSON_CONTRACT = "【契约】status ∈ {ok, partial, failed}；facts / inferences / gaps 三层分离；sources[] 沿用上游证据标签（§9.3 证据链不可断）。"

STEP_AGENT = {
    "strategy_task": "agent_4",
    "creative_task": "agent_5",
    "creative_brief_md_task": "agent_5",
    "report_task": "agent_6",
}

STEP_CONTEXT = {
    "strategy_task": [
        "router.json",
        "objective.json",
        "task0_product.json",
        "task1_painpoints.json",
        "task2_competitor_ads.json",
        "task3_landing_pages.json",
        "task4_demand_signals.json",
        "task5_performance.json",
    ],
    "creative_task": [
        "router.json",
        "objective.json",
        "task0_product.json",
        "task1_painpoints.json",
        "task6_strategy.json",
    ],
    "creative_brief_md_task": ["task7_creative.json", "router.json", "objective.json"],
    "report_task": [
        "router.json",
        "objective.json",
        "task0_product.json",
        "task1_painpoints.json",
        "task2_competitor_ads.json",
        "task3_landing_pages.json",
        "task4_demand_signals.json",
        "task5_performance.json",
        "task6_strategy.json",
        "task7_creative.json",
    ],
}

STEP_ORDER = ["strategy_task", "creative_task", "creative_brief_md_task", "report_task"]


def _clean_markdown(path: Path) -> None:
    """去掉 crewai 落盘 .md 时自动加的 `# <文件路径>` 头与 ```markdown 围栏。"""
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    while lines and (lines[0].startswith(f"# {path.as_posix()}") or lines[0].startswith(f"# {path}")):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    if lines and lines[0].strip().startswith("```markdown"):
        lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        # 围栏内部整体缩进了一级的话，取消缩进
        lines = [l[2:] if l.startswith("  ") else l for l in lines]
    path.write_text("\n".join(lines).lstrip() + "\n", encoding="utf-8")


def _run_step(task_name: str, scratch: Path, output: Path, inputs: dict[str, Any]) -> None:
    agent = build_agent(STEP_AGENT[task_name], tools=[])

    if task_name == "strategy_task":
        out_file: Path = scratch / "task6_strategy.json"
        model: Any = Task6Strategy
    elif task_name == "creative_task":
        out_file = scratch / "task7_creative.json"
        model = Task7Creative
    elif task_name == "creative_brief_md_task":
        out_file = output / "creative_brief.md"
        model = None
    else:
        out_file = output / "strategy_report.md"
        model = None

    task = build_task(
        task_name,
        agent,
        output_json=model,
        output_file=out_file,
        extra_expected_output=JSON_CONTRACT if model else "",
        context_text=build_context_text(scratch, STEP_CONTEXT[task_name]),
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    crew.kickoff(inputs=inputs)

    if model is None:
        _clean_markdown(out_file)

    if model is not None:
        payload = router.read_json(out_file)
        if not payload:
            logger.warning("[%s] 未产出 JSON，写 failed 占位", task_name)
            payload = {
                "status": "failed",
                "sources": [],
                "facts": [],
                "inferences": [],
                "gaps": [f"{task_name} 未产出任何结果"],
            }
        for key in ("status", "sources", "facts", "inferences", "gaps"):
            payload.setdefault(key, [] if key != "status" else "partial")
        router.write_json(out_file, payload)


def run_strategy(
    scratch: Path | None = None,
    output: Path | None = None,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    scratch = scratch or paths.SCRATCH
    output = output or paths.OUTPUT
    output.mkdir(parents=True, exist_ok=True)

    router_payload = router.load_router(scratch)
    objective_payload = router.load_objective(scratch)
    if not router_payload or not objective_payload:
        raise RuntimeError("【§4 规则】缺少 router.json / objective.json，Crew B 不得启动")

    inputs = {
        "ad_type": router_payload.get("ad_type", "product"),
        "objective": objective_payload.get("objective", "conversions_purchase"),
        "primary_kpi": (objective_payload.get("primary_kpi") or {}).get("name", ""),
        "product_name": ((router_payload.get("slots") or {}).get("product") or {})
        .get("resolved", {})
        .get("product_name", "（待确认）"),
    }

    for step in steps or STEP_ORDER:
        logger.info("[Crew B] 运行 %s", step)
        _run_step(step, scratch, output, inputs)

    return {
        "strategy": str(scratch / "task6_strategy.json"),
        "creative": str(scratch / "task7_creative.json"),
        "creative_brief": str(output / "creative_brief.md"),
        "report": str(output / "strategy_report.md"),
    }
