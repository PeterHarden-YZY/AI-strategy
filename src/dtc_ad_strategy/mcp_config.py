"""MCP 配置加载（§8）。

职责：
1. 读取项目级 `.codebuddy/mcp.json`，把 `${VAR}` 占位符用 `.env` / 进程环境回填；
2. 占位符解析不出来时，回退到用户级 `~/.codebuddy/mcp.json` 的同名条目；
3. 输出 `MCPServerAdapter` 可直接吃的 serverparams（**支持 list，用于 A2 多 server 连接**）。
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

from . import paths

logger = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# http 型 server 在 mcp.json 里写 "type": "http"，mcpadapt 只认这些 transport
_TRANSPORT_ALIAS = {
    "http": "streamable-http",
    "https": "streamable-http",
    "streamable_http": "streamable-http",
    "streamable-http": "streamable-http",
    "sse": "sse",
    "ws": "ws",
    "websocket": "ws",
}


def load_env() -> None:
    """加载项目根 .env（不覆盖已有进程环境变量）。"""
    load_dotenv(paths.ROOT / ".env", override=False)


def _expand(value: Any) -> Any:
    """递归展开 ${VAR}；解析不到则原样保留（供上层判失败）。"""
    if isinstance(value, str):
        return _PLACEHOLDER.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def _has_unresolved(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_PLACEHOLDER.search(value))
    if isinstance(value, dict):
        return any(_has_unresolved(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_unresolved(v) for v in value)
    return False


def _read_json(path: Any) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _servers_from(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: cfg
        for name, cfg in (raw.get("mcpServers") or {}).items()
        if isinstance(cfg, dict) and not cfg.get("disabled", False)
    }


def _to_serverparams(name: str, cfg: dict[str, Any]) -> Any:
    """把 mcp.json 的一条 server 配置转成 StdioServerParameters 或 dict。"""
    cfg = _expand(cfg)
    stype = cfg.get("type", "stdio")

    if stype == "stdio":
        from mcp import StdioServerParameters

        env = cfg.get("env") or {}
        # 与进程环境合并，避免只传白名单变量导致子进程找不到 PATH / HOME
        merged_env = {**os.environ, **{k: v for k, v in env.items() if isinstance(v, str)}}
        return StdioServerParameters(
            command=cfg["command"],
            args=list(cfg.get("args") or []),
            env=merged_env,
        )

    transport = _TRANSPORT_ALIAS.get(stype)
    if transport is None:
        raise ValueError(f"[{name}] 不支持的 MCP server type: {stype}")
    params: dict[str, Any] = {"transport": transport}
    if cfg.get("url"):
        params["url"] = cfg["url"]
    if cfg.get("headers"):
        params["headers"] = cfg["headers"]
    return params


def load_server_specs(names: list[str] | None = None) -> dict[str, Any]:
    """返回 {server_name: serverparams}。names 为空时返回全部可用 server。"""
    load_env()
    project = _servers_from(_read_json(paths.PROJECT_MCP)) or _servers_from(
        _read_json(paths.ROOT_MCP)
    )
    user = _servers_from(_read_json(paths.USER_MCP))

    specs: dict[str, Any] = {}
    for name, cfg in project.items():
        if names and name not in names:
            continue
        if _has_unresolved(cfg):
            # 占位符没配上真值 —— 回退用户级配置（那里是明文凭证）
            if name in user:
                logger.warning("[mcp] %s：项目级凭证未解析，回退用户级配置", name)
                cfg = user[name]
            else:
                logger.warning("[mcp] %s：凭证缺失且无回退，跳过", name)
                continue
        try:
            specs[name] = _to_serverparams(name, cfg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[mcp] %s 配置解析失败：%s", name, exc)

    missing = (set(names) - set(specs)) if names else set()
    if missing:
        logger.warning("[mcp] 以下 server 不可用：%s", ", ".join(sorted(missing)))
    return specs


def serverparams_list(names: list[str]) -> list[Any]:
    """给 `MCPServerAdapter` 的 list 入参（A2：单 Crew 连多个 server）。"""
    specs = load_server_specs(names)
    return [specs[n] for n in names if n in specs]


def available_servers() -> list[str]:
    load_env()
    raw = _servers_from(_read_json(paths.PROJECT_MCP)) or _servers_from(
        _read_json(paths.ROOT_MCP)
    )
    return sorted(raw)
