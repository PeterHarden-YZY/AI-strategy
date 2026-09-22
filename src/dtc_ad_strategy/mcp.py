"""MCP 会话助手：把 MCPServerAdapter 的生命周期收敛成 context manager。"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

from crewai_tools.adapters.mcp_adapter import MCPServerAdapter

from . import mcp_config

logger = logging.getLogger(__name__)


class MCPSession:
    """单 Crew 同时连多个 MCP server（A2）。

    用法：
        with MCPSession(["playwright", "google-trends"]) as tools:
            crew = Crew(agents=[...], tasks=[...])
            crew.kickoff()
    """

    def __init__(self, servers: list[str], connect_timeout: int = 90) -> None:
        self.servers = servers
        self.connect_timeout = connect_timeout
        self._adapter: MCPServerAdapter | None = None

    def __enter__(self) -> list[Any]:
        params = mcp_config.serverparams_list(self.servers)
        if not params:
            logger.warning("[mcp] 无可用 server：%s", self.servers)
            return []
        logger.info("[mcp] 连接 %d 个 server：%s", len(params), self.servers)
        self._adapter = MCPServerAdapter(params, connect_timeout=self.connect_timeout)
        tools = list(self._adapter.tools)
        logger.info("[mcp] 拿到 %d 个工具", len(tools))
        return tools

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._adapter is not None:
            try:
                self._adapter.stop()
            except Exception as stop_exc:  # noqa: BLE001
                logger.warning("[mcp] 关闭 adapter 失败：%s", stop_exc)
            self._adapter = None


def filter_tools(tools: list[Any], names: list[str]) -> list[Any]:
    """按 MCP 原生工具名过滤（宿主侧前缀 mcp__<server>__ 在 CrewAI 侧不存在）。"""
    wanted = {n.lower() for n in names}
    return [t for t in tools if t.name.lower() in wanted]
