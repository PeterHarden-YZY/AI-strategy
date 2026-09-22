"""JSONC 解析 + Agent 构造 + LLM 声明（§3.1 / §7）。

- 旧 `agents/*.jsonc` 的 `role` / `goal` / `backstory` 原样读取，不做任何改写；
- LLM 一律用 env `MODEL`（强模型，§7 规则）。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from crewai import Agent

from . import mcp_config, paths

# §7 要求强模型（gemini-3.1-pro / gpt-5.2 / claude-4.5）。
# 当前走 §13.3 的「中转端点 base_url + api key」路线（.env 的 MODEL/OPENAI_API_*），
# 强模型为 gpt-5.6-sol；Gemini 官方 key 对 pro 档配额为 0，仅作备用。
DEFAULT_MODEL = "gemini/gemini-2.5-flash"


def get_model_name() -> str:
    mcp_config.load_env()
    return (os.getenv("MODEL") or os.getenv("OPENAI_MODEL_NAME") or DEFAULT_MODEL).strip()


def strip_jsonc(text: str) -> str:
    """去掉 // 与 /* */ 注释（**跳过字符串内部的 //**，如 https://）。"""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    esc = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    cleaned = "".join(out)
    # 容忍尾逗号
    cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
    return cleaned


def load_jsonc(path: str | Path) -> dict[str, Any]:
    return json.loads(strip_jsonc(Path(path).read_text(encoding="utf-8")))


_AGENT_CACHE: dict[str, dict[str, Any]] = {}


def load_agent_def(name: str) -> dict[str, Any]:
    if name not in _AGENT_CACHE:
        _AGENT_CACHE[name] = load_jsonc(paths.AGENTS_DIR / f"{name}.jsonc")
    return _AGENT_CACHE[name]


def build_agent(
    name: str,
    tools: list[Any] | None = None,
    **overrides: Any,
) -> Agent:
    """按 `agents/<name>.jsonc` 构造 Agent（人格原文不动）。"""
    d = load_agent_def(name)
    settings = dict(d.get("settings") or {})
    model = d.get("llm") or get_model_name()
    llm: Any = model
    if not isinstance(model, Agent):  # model 是字符串 → 允许附加采样参数
        from crewai import LLM

        llm_kwargs: dict[str, Any] = {"temperature": settings.get("temperature", 0.2)}
        # gpt-5.x / o 系推理模型：REASONING_EFFORT ∈ {low, medium, high}（代理端挂起时降到 medium/low）
        effort = (os.getenv("REASONING_EFFORT") or "").strip()
        if effort:
            llm_kwargs["reasoning_effort"] = effort
        llm = LLM(model=model, **llm_kwargs)
    kwargs: dict[str, Any] = {
        "role": d["role"],
        "goal": d["goal"],
        "backstory": d["backstory"],
        "llm": llm,
        "tools": list(tools or []),
        "verbose": settings.get("verbose", True),
        "allow_delegation": settings.get("allow_delegation", False),
    }
    for key in ("max_iter", "max_rpm", "max_execution_time", "respect_context_window", "cache"):
        if key in settings:
            kwargs[key] = settings[key]
    kwargs.update(overrides)
    return Agent(**kwargs)
