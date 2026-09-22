"""直连单个 MCP server 调一次工具（供 tools/ 下的封装层使用）。"""

from __future__ import annotations

import logging
from typing import Any

from crewai_tools.adapters.mcp_adapter import MCPServerAdapter

from .. import mcp_config

logger = logging.getLogger(__name__)


def call_mcp_tool(server: str, tool_name: str, args: dict[str, Any], timeout: int = 90) -> str:
    """连接 server → 按名找工具 → 调一次 → 关掉。

    返回工具原始文本；失败时返回以 `ERROR:` 开头的说明，交给上层记为 GAP（§9.2）。
    """
    params = mcp_config.serverparams_list([server])
    if not params:
        return f"ERROR: server `{server}` 不可用（凭证缺失或配置解析失败）"

    adapter = MCPServerAdapter(params[0], connect_timeout=timeout)
    try:
        for tool in adapter.tools:
            if tool.name.lower() == tool_name.lower():
                try:
                    return str(tool.run(**args))
                except Exception as exc:  # noqa: BLE001
                    return f"ERROR: 调用 {server}.{tool_name} 失败：{exc}"
        available = ", ".join(sorted(t.name for t in adapter.tools))
        return f"ERROR: server `{server}` 没有工具 `{tool_name}`；可用工具：{available}"
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: 连接 server `{server}` 失败：{exc}"
    finally:
        try:
            adapter.stop()
        except Exception:  # noqa: BLE001
            pass


def list_mcp_tools(server: str, timeout: int = 60) -> list[str]:
    params = mcp_config.serverparams_list([server])
    if not params:
        return []
    adapter = MCPServerAdapter(params[0], connect_timeout=timeout)
    try:
        return sorted(t.name for t in adapter.tools)
    finally:
        try:
            adapter.stop()
        except Exception:  # noqa: BLE001
            pass
