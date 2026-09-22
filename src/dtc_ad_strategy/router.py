"""R0 确定性预处理层（§4.7：**零 LLM**）。

职责边界（§4）：
- 只做 URL/文本判定、槽位完整性检查、`status` 判定、澄清问题生成；
- 不产出任何策略建议、卖点判断、预算数字（违反即串层）；
- 对 `promo` / `hybrid` 的活动数字执行**零容错占位**（§4.1 / A10）。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import paths
from .schemas import (
    AD_TYPES,
    OBJECTIVES,
    Clarification,
    ObjectivePayload,
    RouterInput,
    RouterOutput,
    Slot,
)

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

URL_RE = re.compile(r"https?://[^\s<>\"'）)]+", re.IGNORECASE)

# 折扣 / 限时 / 节日节点信号（§4.1 路由判定优先级第 2 条）
PROMO_SIGNAL_RE = re.compile(
    r"(\b\d{1,3}\s*%\s*(off|discount)\b)"
    r"|(\boff\b)"
    r"|(\bdiscount\b)"
    r"|(\bsale\b)"
    r"|(\bpromo(tion)?\b)"
    r"|(\bcoupon\b)"
    r"|(\bpromo\s*code\b)"
    r"|(\bcode\b)"
    r"|(\blimited[- ]time\b)"
    r"|(\bblack\s*friday\b)"
    r"|(\bcyber\s*(monday|week)\b)"
    r"|(\bthanksgiving\b)"
    r"|(\bchristmas\b|\bxmas\b)"
    r"|(\bholiday\b)"
    r"|(\bends\s+(soon|on|\d))"
    r"|(\bflash\s*sale\b)"
    r"|(\bclearance\b)"
    r"|(\bdoorbuster\b)"
    r"|(\bbogo\b)"
    r"|(折扣)"
    r"|(满减)"
    r"|(限时)"
    r"|(优惠码)"
    r"|(大促)"
    r"|(双\s*11)"
    r"|(黑五)"
    r"|(圣诞)"
    r"|(感恩节)",
    re.IGNORECASE,
)

# 活动槽必填字段（§4.1）与零容错占位符（A10）
PROMO_REQUIRED_FIELDS = [
    "promo_name",
    "mechanic",
    "discount_value",
    "start_date",
    "end_date",
]
PROMO_PLACEHOLDERS = {
    "promo_name": "{活动名称待确认}",
    "mechanic": "{活动机制待确认}",
    "discount_value": "{折扣力度待确认}",
    "threshold": "{满减门槛待确认}",
    "code": "{优惠码待确认}",
    "start_date": "{活动开始日期待确认}",
    "end_date": "{活动截止日期待确认}",
    "eligible_scope": "{参与范围待确认}",
}

PRODUCT_REQUIRED_FIELDS = ["product_name", "category"]

# §4.4 objective → 投放参数矩阵（下游硬约束，不得自选）
OBJECTIVE_MATRIX: dict[str, dict[str, Any]] = {
    "leads": {
        "bid": "最低成本 / CPL 上限",
        "attribution_window": "7d_click",
        "daily_budget_rule": "CPL 目标 × 20–30",
        "creative_focus": "钩子＝利益交换（指南/报价/试用）；CTA＝Get / Claim",
        "landing_requirement": "表单页，字段 ≤3",
        "stop_loss": "CPL > 目标 2× 连续 3 天",
        "primary_kpi": "CPL",
        "secondary_kpi": ["留资率", "有效线索率"],
    },
    "reach": {
        "bid": "Reach 出价 + 频次上限",
        "attribution_window": "1d_view",
        "daily_budget_rule": "CPM × 目标覆盖人数",
        "creative_focus": "钩子＝记忆点；弱 CTA",
        "landing_requirement": "品牌页 / 品类页",
        "stop_loss": "频次 >3 且 CTR 持续下滑",
        "primary_kpi": "CPM / 覆盖人数",
        "secondary_kpi": ["频次", "CTR"],
    },
    "outbound_clicks": {
        "bid": "Link Clicks / 手动 CPC 封顶",
        "attribution_window": "1d_click",
        "daily_budget_rule": "CPC 目标 × 50",
        "creative_focus": "钩子＝好奇心缺口；CTA＝Learn more",
        "landing_requirement": "内容页 / 集合页",
        "stop_loss": "CPC > 非品牌封顶 2×",
        "primary_kpi": "CPC",
        "secondary_kpi": ["CTR", "落地页浏览率"],
    },
    "conversions_purchase": {
        "bid": "tROAS / tCPA",
        "attribution_window": "7d_click_1d_view",
        "daily_budget_rule": "CPA 目标 × 10–15",
        "creative_focus": "钩子＝结果证明 + 价格锚；CTA＝Shop now",
        "landing_requirement": "PDP / 购物车",
        "stop_loss": "CPA > 目标 1.5× 连续 5 天，或 ROAS < 盈亏线",
        "primary_kpi": "ROAS",
        "secondary_kpi": ["CPA", "CVR"],
    },
    "add_to_cart": {
        "bid": "AddToCart 优化",
        "attribution_window": "7d_click",
        "daily_budget_rule": "加购成本 × 15",
        "creative_focus": "钩子＝场景代入 + 低门槛；CTA＝Add to cart",
        "landing_requirement": "PDP",
        "stop_loss": "加购→购买率 < 历史均值 60%",
        "primary_kpi": "加购成本",
        "secondary_kpi": ["加购→购买率", "CPA"],
    },
}

# §4.5 ad_type × objective 交叉校验：True=✅，False=⚠️
CROSS_CHECK: dict[tuple[str, str], bool] = {
    ("product", "leads"): True,
    ("product", "reach"): True,
    ("product", "outbound_clicks"): True,
    ("product", "conversions_purchase"): True,
    ("product", "add_to_cart"): True,
    ("promo", "leads"): False,
    ("promo", "reach"): True,
    ("promo", "outbound_clicks"): True,
    ("promo", "conversions_purchase"): True,
    ("promo", "add_to_cart"): True,
    ("hybrid", "leads"): False,
    ("hybrid", "reach"): False,
    ("hybrid", "outbound_clicks"): True,
    ("hybrid", "conversions_purchase"): True,
    ("hybrid", "add_to_cart"): True,
}

CROSS_CHECK_ALTERNATIVE: dict[tuple[str, str], str] = {
    ("promo", "leads"): "拆成 promo/reach 造势层 + 一个独立 lead 表单广告（活动仅为留资/抽奖时保留本组合）",
    ("hybrid", "leads"): "拆成 promo/leads 收线索 + product/conversions_purchase 收割",
    ("hybrid", "reach"): "拆成 promo/reach 造势层 + product/conversions_purchase 收割层",
}


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------


def extract_urls(text: str) -> list[str]:
    """从任意文本中抽取 URL（去重保序）。"""
    if not text:
        return []
    seen: list[str] = []
    for u in URL_RE.findall(text):
        u = u.rstrip(".,;)】]")
        if u not in seen:
            seen.append(u)
    return seen


def has_promo_signal(text: str) -> bool:
    return bool(text and PROMO_SIGNAL_RE.search(text))


def _question(slot: str, field: str) -> str:
    q = {
        "promo_name": "活动名称是什么？（须与活动页标题逐字一致）",
        "mechanic": "活动机制是什么？（例：满 $500 减 $20 / 全场 8 折 / 买一送一）",
        "discount_value": "折扣力度的精确数值是多少？（例：$20 OFF / 20% OFF，不接受估算）",
        "threshold": "满减门槛是多少？（例：Spend $500，无门槛请写「无门槛」）",
        "code": "优惠码是什么？（无码请写「无优惠码」）",
        "start_date": "活动开始日期（YYYY-MM-DD）？",
        "end_date": "活动截止日期（YYYY-MM-DD）？",
        "eligible_scope": "参与范围是什么？（全站 / 指定 SKU / 指定品类）",
        "product_name": "产品名 / 型号是什么？",
        "category": "细分品类是什么？（例：L 型电动升降桌）",
        "price": "售价是多少？",
        "selling_points": "计划主打卖点有哪些？（最多 5 条，按重要性排序）",
    }
    return q.get(field, f"{slot}.{field} 缺失，请补充")


def build_slot(mode: str, urls: list[str], raw_text: str) -> Slot:
    return Slot(mode=mode, urls=urls, raw_text=raw_text, resolved={}, pending_confirm=[])


# --------------------------------------------------------------------------
# 主流程：确定性路由
# --------------------------------------------------------------------------


def pre_route(inp: RouterInput) -> dict[str, Any]:
    """零 LLM 的槽位解析 + ad_type 判定 + 澄清清单。

    返回 dict，可直接喂给 R0 agent，也可作为 `router.json` 的骨架。
    """
    slots: dict[str, Slot] = {}

    # --- product 槽 ---
    p_urls = extract_urls(inp.product_url or "")
    p_text = (inp.product_text or "").strip()
    if not p_urls and p_text:
        p_urls = extract_urls(p_text)
    if p_urls:
        slots["product"] = build_slot("url", p_urls, p_text)
    elif p_text:
        slots["product"] = build_slot("manual", [], p_text)
    else:
        slots["product"] = build_slot("none", [], "")

    # --- promo 槽 ---
    m_urls = extract_urls(inp.promo_url or "")
    m_text = (inp.promo_text or "").strip()
    if not m_urls and m_text:
        m_urls = extract_urls(m_text)
    if m_urls:
        slots["promo"] = build_slot("url", m_urls, m_text)
    elif m_text:
        slots["promo"] = build_slot("manual", [], m_text)
    else:
        slots["promo"] = build_slot("none", [], "")

    has_product = slots["product"].mode != "none"
    has_promo = slots["promo"].mode != "none"

    # --- §4.1 路由判定优先级（自上而下，命中即停）---
    clarifications: list[Clarification] = []
    if has_product and has_promo:
        ad_type = "hybrid"
        note = "命中判定优先级第 1 条：同时提供产品信息与活动信息 → hybrid"
    elif has_product and not has_promo:
        signal = has_promo_signal(p_text) or has_promo_signal(inp.goal_text or "")
        if signal:
            ad_type = "hybrid"
            note = (
                "命中判定优先级第 2 条：仅提供产品信息，但内容出现明确折扣/限时/节日节点"
                " → hybrid 候选，须向用户确认一次（无活动则降为 product）"
            )
            clarifications.append(
                Clarification(
                    slot="promo",
                    field="confirm_ad_type",
                    question="产品信息里出现了折扣/限时信号，是否确实有在跑的活动？"
                    "（有 → 保持 hybrid 并补齐活动字段；没有 → 降级为 product）",
                )
            )
        else:
            ad_type = "product"
            note = "命中判定优先级第 4 条：仅提供产品信息且无折扣/限时信号 → product"
    elif has_promo and not has_product:
        ad_type = "promo"
        note = (
            "命中判定优先级第 3 条：仅提供活动信息 → 默认 promo；"
            "提示可补齐产品卖点升级为 hybrid，是否升级由用户决定"
        )
        clarifications.append(
            Clarification(
                slot="product",
                field="upgrade_to_hybrid",
                question="是否补齐产品卖点，把本轮升级为 hybrid（先讲卖点再收折扣）？",
            )
        )
    else:
        ad_type = "product"
        note = "命中判定优先级第 4 条（兜底）：未提供任何产品/活动信息 → product（随后判定为 failed）"

    # --- 槽位完整性 ---
    missing_slots: list[str] = []
    if ad_type in ("product", "hybrid") and not has_product:
        missing_slots.append("product")
    if ad_type in ("promo", "hybrid") and not has_promo:
        missing_slots.append("promo")

    # --- 必填字段澄清（单批次，§4.2 禁止挤牙膏）---
    for field in PRODUCT_REQUIRED_FIELDS:
        if ad_type in ("product", "hybrid"):
            clarifications.append(
                Clarification(slot="product", field=field, question=_question("product", field))
            )
    if ad_type in ("promo", "hybrid"):
        for field in PROMO_REQUIRED_FIELDS:
            clarifications.append(
                Clarification(slot="promo", field=field, question=_question("promo", field))
            )
        clarifications.append(
            Clarification(
                slot="promo",
                field="exclusions",
                question="活动排除项有哪些？（不参与的商品/品类/地区；无请写「无排除项」）",
            )
        )

    # --- status ---
    if ad_type == "product" and slots["product"].mode == "none":
        status = "failed"
    elif missing_slots:
        status = "partial"
    else:
        status = "partial" if clarifications else "ok"

    return {
        "status": status,
        "ad_type": ad_type,
        "task_profile": ad_type,
        "decision_note": note,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "slots": {k: v.model_dump() for k, v in slots.items()},
        "missing_slots": missing_slots,
        "clarifications": [c.model_dump() for c in clarifications],
        "sources": [],
        "facts": [],
        "inferences": [],
        "gaps": [],
    }


# --------------------------------------------------------------------------
# 校验 / 零容错
# --------------------------------------------------------------------------


def _is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def apply_zero_tolerance(payload: dict[str, Any]) -> dict[str, Any]:
    """活动数字零容错（§4.1 / A10）：拿不到就占位，绝不估算。"""
    ad_type = payload.get("ad_type", "product")
    if ad_type not in ("promo", "hybrid"):
        return payload

    slots = payload.setdefault("slots", {})
    promo = slots.setdefault("promo", {}) or {}
    resolved = promo.setdefault("resolved", {}) or {}
    pending = promo.setdefault("pending_confirm", []) or []

    for field, placeholder in PROMO_PLACEHOLDERS.items():
        if _is_empty(resolved.get(field)):
            # threshold / code / eligible_scope 非必填，但仍需显式占位或显式"无"
            resolved[field] = placeholder
            if field not in pending:
                pending.append(field)
    promo["resolved"] = resolved
    promo["pending_confirm"] = pending

    # 未拿到活动信息时，整段记为 GAP（§9.2：空数据 ≠ 好数据）
    gaps = payload.setdefault("gaps", [])
    if promo.get("mode") == "none":
        gaps.append("promo 槽位未提供任何活动信息，活动规则/折扣/起止日期全部记为 GAP")
    return payload


def validate_router(payload: dict[str, Any]) -> list[str]:
    """返回错误列表；空列表代表合法（A8）。"""
    errors: list[str] = []
    if payload.get("ad_type") not in AD_TYPES:
        errors.append(f"ad_type 非法：{payload.get('ad_type')!r}，必须 ∈ {AD_TYPES}")
    if payload.get("task_profile") not in AD_TYPES:
        errors.append(f"task_profile 非法：{payload.get('task_profile')!r}")
    if payload.get("status") not in ("ok", "partial", "failed"):
        errors.append(f"status 非法：{payload.get('status')!r}")
    slots = payload.get("slots") or {}
    for name in ("product", "promo"):
        if name not in slots:
            errors.append(f"缺少 slots.{name}")
            continue
        if slots[name].get("mode") not in ("url", "manual", "none"):
            errors.append(f"slots.{name}.mode 非法：{slots[name].get('mode')!r}")
    return errors


def validate_objective(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("objective") not in OBJECTIVES:
        errors.append(f"objective 非法：{payload.get('objective')!r}，必须 ∈ {OBJECTIVES}")
    if not payload.get("mapping_note"):
        errors.append("缺少 mapping_note（§4.3：必须写明映射理由供用户当场否认）")
    return errors


def default_objective(objective: str, mapping_note: str) -> dict[str, Any]:
    """按 §4.4 矩阵生成 objective 骨架；guardrails 留空等 C5 回填。"""
    m = OBJECTIVE_MATRIX.get(objective, OBJECTIVE_MATRIX["conversions_purchase"])
    return {
        "objective": objective,
        "mapping_note": mapping_note,
        "optimization_event": {
            "leads": "Lead",
            "reach": "Impression / Reach",
            "outbound_clicks": "Link Click",
            "conversions_purchase": "Purchase",
            "add_to_cart": "AddToCart",
        }[objective],
        "attribution_window": m["attribution_window"],
        "bid_strategy": m["bid"],
        "primary_kpi": {"name": m["primary_kpi"], "baseline_from": "task5_performance.json"},
        "secondary_kpi": [{"name": k} for k in m["secondary_kpi"]],
        "guardrails": {"cpa_ceiling": None, "non_brand_cpc_cap": None, "frequency_cap": None},
        "status": "partial",
        "sources": [],
        "facts": [],
        "inferences": [],
        "gaps": [],
    }


def cross_check_note(ad_type: str, objective: str) -> str:
    """§4.5：落 ⚠️ 时给出替代方案。"""
    if CROSS_CHECK.get((ad_type, objective), True):
        return ""
    return (
        f"⚠️ ad_type={ad_type} × objective={objective} 为不推荐组合。"
        f"替代方案：{CROSS_CHECK_ALTERNATIVE.get((ad_type, objective), '拆分投放层级')}"
    )


# --------------------------------------------------------------------------
# 落盘 / 读取
# --------------------------------------------------------------------------


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def finalize_router(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """R0 输出落盘前的最后一道闸：零容错 + 枚举校验。"""
    payload = apply_zero_tolerance(payload)
    payload.setdefault("task_profile", payload.get("ad_type", "product"))
    errors = validate_router(payload)
    if errors:
        payload["status"] = "failed"
    return payload, errors


def load_router(scratch: Path | None = None) -> dict[str, Any]:
    return read_json((scratch or paths.SCRATCH) / "router.json")


def load_objective(scratch: Path | None = None) -> dict[str, Any]:
    return read_json((scratch or paths.SCRATCH) / "objective.json")


def router_model(payload: dict[str, Any]) -> RouterOutput:
    return RouterOutput.model_validate(payload)


def objective_model(payload: dict[str, Any]) -> ObjectivePayload:
    return ObjectivePayload.model_validate(payload)
