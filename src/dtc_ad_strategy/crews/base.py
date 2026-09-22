"""Task 构造公共逻辑（§3.1：迁移的提示词原文 + v2 适配前后缀）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crewai import Task

from .. import paths
from ..config import load_jsonc

_TASK_CACHE: dict[str, dict[str, Any]] = {}


def load_task_def(name: str) -> dict[str, Any]:
    if name not in _TASK_CACHE:
        _TASK_CACHE[name] = load_jsonc(paths.TASKS_DIR / f"{name}.json")
    return _TASK_CACHE[name]


def compose_description(d: dict[str, Any]) -> str:
    """v2_prefix + 迁移原文 + v2_suffix（原文一字不改地居中）。"""
    return f"{d.get('v2_prefix', '')}{d['description']}{d.get('v2_suffix', '')}"


def build_task(
    name: str,
    agent: Any,
    context: list[Task] | None = None,
    output_json: Any | None = None,
    output_file: str | Path | None = None,
    extra_expected_output: str = "",
    context_text: str = "",
) -> Task:
    d = load_task_def(name)
    description = compose_description(d)
    if context_text:
        description = f"{description}\n\n【上游已落盘的数据（事实源，不得改写）】\n{context_text}"

    expected = d["expected_output"]
    if extra_expected_output:
        expected = f"{expected}\n{extra_expected_output}"
    if output_json is not None:
        expected = (
            f"{expected}\n【输出格式】必须输出可直接解析的 JSON，"
            f"字段严格对齐 {output_json.__name__} 模型，不要包在 ```json 代码块里。"
        )

    return Task(
        name=d.get("name", name),
        description=description,
        expected_output=expected,
        agent=agent,
        context=list(context or []),
        output_json=output_json,
        output_file=str(output_file) if output_file else None,
    )


def build_context_text(scratch: Path, filenames: list[str], limit: int = 7000) -> str:
    """把上游 JSON 读进来当上下文（跨 Crew 传数据的唯一方式）。"""
    chunks: list[str] = []
    for fn in filenames:
        p = scratch / fn
        if not p.exists():
            chunks.append(f"### {fn}\n（缺失，未落盘）")
            continue
        text = p.read_text(encoding="utf-8")
        if len(text) > limit:
            text = text[:limit] + f"\n…（截断，共 {len(text)} 字符）"
        chunks.append(f"### {fn}\n{text}")
    return "\n\n".join(chunks)


def dump(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(obj)
