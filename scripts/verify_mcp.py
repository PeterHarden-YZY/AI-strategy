"""验收脚本：A1（MCP 可用）+ A2（单 Crew 同时连 ≥2 个 MCP server）。

用法：
    .venv/Scripts/python scripts/verify_mcp.py
    .venv/Scripts/python scripts/verify_mcp.py --servers google-trends,gads-transparency,playwright
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dtc_ad_strategy import mcp_config  # noqa: E402

from crewai_tools.adapters.mcp_adapter import MCP_AVAILABLE, MCPServerAdapter  # noqa: E402


def _tool_names(adapter: MCPServerAdapter) -> list[str]:
    # ToolCollection 本身就是 list[BaseTool]，没有 .tools 子属性
    return sorted(t.name for t in adapter.tools)


def check_a1() -> bool:
    ok = MCP_AVAILABLE is True
    print(f"[A1] MCP_AVAILABLE = {MCP_AVAILABLE} -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_a2(servers: list[str]) -> bool:
    print(f"[A2] 目标 server：{servers}")

    single_counts: dict[str, int] = {}
    for name in servers:
        params = mcp_config.serverparams_list([name])
        if not params:
            print(f"  - {name}: 配置缺失，跳过")
            continue
        try:
            adapter = MCPServerAdapter(params[0], connect_timeout=60)
            names = _tool_names(adapter)
            single_counts[name] = len(names)
            print(f"  - {name}: {len(names)} tools")
            adapter.stop()
        except Exception as exc:  # noqa: BLE001
            print(f"  - {name}: 连接失败 {type(exc).__name__}: {exc}")

    if not single_counts:
        print("[A2] FAIL：没有任何单 server 连上")
        return False

    params = mcp_config.serverparams_list(servers)
    print(f"[A2] 多 server 入参长度 = {len(params)}")
    adapter = MCPServerAdapter(params, connect_timeout=90)
    names = _tool_names(adapter)
    total = len(names)
    max_single = max(single_counts.values())
    print(f"[A2] 多 server 合并工具数 = {total}；单 server 最大 = {max_single}")
    for n in names:
        print(f"      · {n}")
    adapter.stop()

    ok = total > max_single and len(params) >= 2
    print(f"[A2] -> {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--servers", default="google-trends,gads-transparency")
    args = parser.parse_args()

    servers = [s.strip() for s in args.servers.split(",") if s.strip()]
    ok1 = check_a1()
    ok2 = False
    try:
        ok2 = check_a2(servers)
    except Exception as exc:  # noqa: BLE001
        print(f"[A2] 异常：{type(exc).__name__}: {exc}")
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
