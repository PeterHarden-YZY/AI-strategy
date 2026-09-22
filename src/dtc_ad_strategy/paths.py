"""全局路径（§3 项目结构）。"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCRATCH = Path(os.getenv("DTC_SCRATCH_DIR") or (ROOT / "scratch")).resolve()
OUTPUT = Path(os.getenv("DTC_OUTPUT_DIR") or (ROOT / "output")).resolve()
KNOWLEDGE = ROOT / "knowledge"
FIXTURES = ROOT / "fixtures"
AGENTS_DIR = Path(__file__).parent / "agents"
TASKS_DIR = Path(__file__).parent / "tasks"

# 项目级 MCP 配置：优先 .codebuddy/mcp.json（§3），根目录 mcp.json 作为等价备选
PROJECT_MCP = ROOT / ".codebuddy" / "mcp.json"
ROOT_MCP = ROOT / "mcp.json"
USER_MCP = Path.home() / ".codebuddy" / "mcp.json"


def ensure_dirs() -> None:
    """保证数据契约层与交付层目录存在。"""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
