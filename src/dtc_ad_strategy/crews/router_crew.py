"""Crew R —— 路由层（§4 / §6）。

R0（输入路由官）+ R1（投放目标策略官），串行且必须先完成。
任一 `status="failed"` 即终止整条链路，不进 Crew A（§6 规则）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crewai import Crew, Process

from .. import paths, router
from ..config import build_agent
from ..mcp import MCPSession
from ..schemas import ObjectivePayload, RouterInput, RouterOutput
from .base import build_task, dump

logger = logging.getLogger(__name__)

JSON_CONTRACT = "【契约】status ∈ {ok, partial, failed}；sources[] 每项含 tool / server / query / retrieved_at。"


def run_router(
    inp: RouterInput,
    scratch: Path | None = None,
    servers: list[str] | None = None,
) -> dict[str, Any]:
    """跑 Crew R，产出 scratch/router.json + scratch/objective.json。"""
    scratch = scratch or paths.SCRATCH
    scratch.mkdir(parents=True, exist_ok=True)

    # ---------- 第 0 步：零 LLM 的确定性预处理 ----------
    skeleton = router.pre_route(inp)
    router_path = scratch / "router.json"
    objective_path = scratch / "objective.json"

    if skeleton["status"] == "failed":
        router.write_json(router_path, skeleton)
        logger.error("[R0] status=failed，终止链路，不进 Crew A：%s", skeleton["decision_note"])
        return {"status": "failed", "router": skeleton, "objective": None, "errors": []}

    # ---------- 第 1 步：R0 / R1（LLM 只做抽取与枚举映射）----------
    servers = servers or ["playwright"]
    with MCPSession(servers) as mcp_tools:
        r0 = build_agent("agent_r0", tools=mcp_tools)
        r1 = build_agent("agent_r1", tools=[])

        router_task = build_task(
            "router_task",
            r0,
            context=[],
            output_json=RouterOutput,
            output_file=router_path,
            extra_expected_output=JSON_CONTRACT,
        )
        objective_task = build_task(
            "objective_task",
            r1,
            context=[router_task],
            output_json=ObjectivePayload,
            output_file=objective_path,
            extra_expected_output=JSON_CONTRACT,
        )

        crew = Crew(
            agents=[r0, r1],
            tasks=[router_task, objective_task],
            process=Process.sequential,
            verbose=True,
        )
        crew.kickoff(
            inputs={
                "route_skeleton": dump(skeleton),
                "router_json": dump(skeleton),
                "goal_text": inp.goal_text or "（用户未填写投放目的，请按 ad_type 给出默认建议）",
            }
        )

    # ---------- 第 2 步：落盘前的最后一道闸（零容错 + 枚举校验）----------
    payload = router.read_json(router_path) or skeleton
    payload.setdefault("slots", skeleton.get("slots", {}))
    payload.setdefault("ad_type", skeleton["ad_type"])
    payload.setdefault("task_profile", skeleton["ad_type"])
    payload.setdefault("decision_note", skeleton["decision_note"])
    payload.setdefault("created_at", skeleton["created_at"])
    payload.setdefault("missing_slots", skeleton["missing_slots"])
    payload.setdefault("clarifications", skeleton["clarifications"])
    payload.setdefault("sources", [])
    payload.setdefault("facts", [])
    payload.setdefault("inferences", [])
    payload.setdefault("gaps", [])
    payload, errors = router.finalize_router(payload)
    router.write_json(router_path, payload)

    obj = router.read_json(objective_path) or {}
    obj_errors = router.validate_objective(obj)
    ad_type = payload.get("ad_type", "product")
    if obj_errors:
        logger.error("[R1] objective 非法，按默认枚举落地并标注需人工复核：%s", obj_errors)
        obj = router.default_objective(
            "conversions_purchase",
            "R1 未产出合法枚举值，按默认 conversions_purchase 落地，**需人工复核**",
        )
        obj["status"] = "partial"
        obj["gaps"] = [f"objective 自动兜底，原因：{'; '.join(obj_errors)}"]
    else:
        if not obj.get("cross_check_note"):
            obj["cross_check_note"] = router.cross_check_note(ad_type, obj["objective"])
        obj.setdefault("status", "partial")
        obj.setdefault("sources", [])
        obj.setdefault("facts", [])
        obj.setdefault("inferences", [])
        obj.setdefault("gaps", [])
    router.write_json(objective_path, obj)

    return {
        "status": payload.get("status"),
        "router": payload,
        "objective": obj,
        "errors": errors + obj_errors,
        "paths": {"router": str(router_path), "objective": str(objective_path)},
    }
