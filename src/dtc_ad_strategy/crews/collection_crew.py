"""Crew A —— 采集层（§6，工具密集）。

C0 → C1 / C2 → C3 / C4 / C5。
**C1 与 C2 物理隔离**：各自独立成 Crew，且只注入 C0 的 JSON（§6 规则）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crewai import Crew, Process

from .. import paths, router
from ..config import build_agent
from ..mcp import MCPSession
from ..schemas import (
    Task0Product,
    Task1PainPoints,
    Task2CompetitorAds,
    Task3LandingPages,
    Task4DemandSignals,
    Task5Performance,
)
from ..tools import SIMPLE_TOOLS
from .base import build_context_text, build_task, dump

logger = logging.getLogger(__name__)

JSON_CONTRACT = "【契约】status ∈ {ok, partial, failed}；facts / inferences / gaps 三层分离；sources[] 每项含 tool / server / query / retrieved_at；工具返回 0 条必须记 GAP 并写明原因。"

# 每个采集 task 的：agent / MCP server / 上游依赖文件 / 输出模型
STEP_AGENT: dict[str, str] = {
    "product_analysis_task": "agent_1",
    "pain_points_task": "agent_1",
    "competitor_ads_task": "agent_2",
    "landing_pages_task": "agent_2",
    "demand_signals_task": "agent_3",
    "performance_task": "agent_3",
}

STEP_SERVERS: dict[str, list[str]] = {
    "product_analysis_task": ["playwright"],
    "pain_points_task": ["playwright"],
    "competitor_ads_task": ["facebook-ads-library", "gads-transparency"],
    "landing_pages_task": ["playwright"],
    "demand_signals_task": ["google-trends", "similarweb", "google-ads"],
    "performance_task": ["google-ads", "meta-ads"],
}

# §6 隔离：C1 / C2 只依赖 C0，互不可见
STEP_CONTEXT: dict[str, list[str]] = {
    "product_analysis_task": [],
    "pain_points_task": ["task0_product.json"],
    "competitor_ads_task": ["task0_product.json"],
    "landing_pages_task": ["task0_product.json", "task2_competitor_ads.json"],
    "demand_signals_task": ["task0_product.json"],
    "performance_task": ["task0_product.json"],
}

STEP_MODEL: dict[str, Any] = {
    "product_analysis_task": Task0Product,
    "pain_points_task": Task1PainPoints,
    "competitor_ads_task": Task2CompetitorAds,
    "landing_pages_task": Task3LandingPages,
    "demand_signals_task": Task4DemandSignals,
    "performance_task": Task5Performance,
}

STEP_ORDER = [
    "product_analysis_task",
    "pain_points_task",
    "competitor_ads_task",
    "landing_pages_task",
    "demand_signals_task",
    "performance_task",
]


def _run_step(
    task_name: str,
    scratch: Path,
    router_payload: dict[str, Any],
    objective_payload: dict[str, Any],
    inputs: dict[str, Any],
) -> None:
    """跑单个采集 task（独立 Crew + 独立 MCP 会话）。"""
    agent_name = STEP_AGENT[task_name]
    servers = STEP_SERVERS[task_name]
    model = STEP_MODEL[task_name]

    with MCPSession(servers) as mcp_tools:
        tools = list(mcp_tools)
        if agent_name == "agent_3":
            # §7：复杂工具包一层，只给 LLM 简单入参
            tools = tools + list(SIMPLE_TOOLS)
        agent = build_agent(agent_name, tools=tools)

        task = build_task(
            task_name,
            agent,
            output_json=model,
            output_file=scratch / _out_name(task_name),
            extra_expected_output=JSON_CONTRACT,
            context_text=build_context_text(scratch, STEP_CONTEXT[task_name]),
        )
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
        crew.kickoff(inputs=inputs)

    # 兜底：确保文件存在且带 status（A3）
    out_path = scratch / _out_name(task_name)
    payload = router.read_json(out_path)
    if not payload:
        logger.warning("[%s] 未产出 JSON，写 failed 占位", task_name)
        payload = {
            "status": "failed",
            "sources": [],
            "facts": [],
            "inferences": [],
            "gaps": [f"{task_name} 未产出任何结果（LLM 未落盘或工具全部失败）"],
        }
        router.write_json(out_path, payload)
    payload.setdefault("status", "partial")
    for key in ("sources", "facts", "inferences", "gaps"):
        payload.setdefault(key, [])
    router.write_json(out_path, payload)


def _out_name(task_name: str) -> str:
    return {
        "product_analysis_task": "task0_product.json",
        "pain_points_task": "task1_painpoints.json",
        "competitor_ads_task": "task2_competitor_ads.json",
        "landing_pages_task": "task3_landing_pages.json",
        "demand_signals_task": "task4_demand_signals.json",
        "performance_task": "task5_performance.json",
    }[task_name]


def run_collection(
    scratch: Path | None = None,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    """跑 Crew A（全部或指定步骤）。"""
    scratch = scratch or paths.SCRATCH
    scratch.mkdir(parents=True, exist_ok=True)

    router_payload = router.load_router(scratch)
    objective_payload = router.load_objective(scratch)
    if not router_payload or not objective_payload:
        raise RuntimeError("【§4 规则】缺少 router.json / objective.json，Crew A 不得启动")

    prod_slot = (router_payload.get("slots") or {}).get("product") or {}
    promo_slot = (router_payload.get("slots") or {}).get("promo") or {}

    inputs = {
        "ad_type": router_payload.get("ad_type", "product"),
        "task_profile": router_payload.get("task_profile", "product"),
        "objective": objective_payload.get("objective", "conversions_purchase"),
        "primary_kpi": (objective_payload.get("primary_kpi") or {}).get("name", ""),
        "product_name": (prod_slot.get("resolved") or {}).get("product_name")
        or (promo_slot.get("resolved") or {}).get("eligible_scope")
        or "（待确认）",
        "product_url": (prod_slot.get("urls") or [""])[0] if prod_slot.get("urls") else "",
        "product_brief": prod_slot.get("raw_text", ""),
    }

    for step in steps or STEP_ORDER:
        logger.info("[Crew A] 运行 %s（servers=%s）", step, STEP_SERVERS[step])
        _run_step(step, scratch, router_payload, objective_payload, inputs)

    return {
        "router": router_payload,
        "objective": objective_payload,
        "files": [str(scratch / _out_name(s)) for s in (steps or STEP_ORDER)],
    }


def load_fixtures(scratch: Path | None = None, fixtures: Path | None = None) -> list[str]:
    """离线模式：把旧项目真实数据复制进 scratch/（§3.1 fixtures 用途）。"""
    import shutil

    scratch = scratch or paths.SCRATCH
    fixtures = fixtures or paths.FIXTURES
    scratch.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for src in sorted(fixtures.glob("*.json")):
        name = src.name.replace("task5_historical_performance", "task5_performance")
        dst = scratch / name
        shutil.copyfile(src, dst)
        payload = router.read_json(dst)
        for key in ("status", "sources", "facts", "inferences", "gaps"):
            payload.setdefault(key, [] if key != "status" else "ok")
        router.write_json(dst, payload)
        copied.append(str(dst))
    return copied
