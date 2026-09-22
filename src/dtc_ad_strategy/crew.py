"""主入口（§3）：@CrewBase class-based。

`【事实】` 纯 JSONC 声明式路线接不了 MCP —— `mcp_server_params` / `get_mcp_tools()`
只存在于 class-based `CrewBase`，因此本文件必须是 class-based。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from crewai.project import CrewBase

from . import paths
from .crews.collection_crew import STEP_ORDER as COLLECTION_STEPS, load_fixtures, run_collection
from .crews.router_crew import run_router
from .crews.strategy_crew import STEP_ORDER as STRATEGY_STEPS, run_strategy
from .schemas import RouterInput

logger = logging.getLogger(__name__)


@CrewBase
class DtcAdStrategyCrew:
    """路由 → 采集 → 策略 三段式流水线，JSON 为唯一契约。"""

    def __init__(
        self,
        router_input: RouterInput | None = None,
        scratch: Path | None = None,
        output: Path | None = None,
    ) -> None:
        self.router_input = router_input or RouterInput()
        self.scratch = Path(scratch or paths.SCRATCH)
        self.output = Path(output or paths.OUTPUT)
        paths.ensure_dirs()
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 三段
    # ------------------------------------------------------------------
    def route(self) -> dict[str, Any]:
        logger.info("=== Crew R 路由层 ===")
        return run_router(self.router_input, self.scratch)

    def collect(self, offline: bool = False, steps: list[str] | None = None) -> dict[str, Any]:
        logger.info("=== Crew A 采集层 ===")
        if offline:
            return {"files": load_fixtures(self.scratch), "offline": True}
        return run_collection(self.scratch, steps or COLLECTION_STEPS)

    def strategize(self, steps: list[str] | None = None) -> dict[str, Any]:
        logger.info("=== Crew B 策略层 ===")
        return run_strategy(self.scratch, self.output, steps or STRATEGY_STEPS)

    # ------------------------------------------------------------------
    def run(self, offline: bool = False, skip_collection: bool = False) -> dict[str, Any]:
        """全链路：R → A → B。任一环节 failed 即终止（§6）。"""
        result: dict[str, Any] = {"status": "ok", "stages": {}}

        r = self.route()
        result["stages"]["router"] = r
        if r.get("status") == "failed":
            result["status"] = "failed"
            result["message"] = "R0 判定失败：未终止前不进入采集层"
            return result

        if not skip_collection:
            result["stages"]["collection"] = self.collect(offline=offline)

        result["stages"]["strategy"] = self.strategize()
        result["outputs"] = {
            "strategy_report": str(self.output / "strategy_report.md"),
            "creative_brief": str(self.output / "creative_brief.md"),
        }
        return result
