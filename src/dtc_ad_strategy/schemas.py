"""scratch/*.json 的数据契约模型（§4.2 / §4.3 / §5）。

设计原则：
- **关键枚举强校验**（`ad_type` / `objective` / `status`）—— 这是 §9.0 与 A8 的硬要求；
- 其余字段宽松（`extra="allow"`），避免 LLM 多写字段就整包失败；
- 三层分离 `facts` / `inferences` / `gaps`（§9.1）。
"""

from __future__ import annotations

import warnings
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# §10.4 的业务字段名就叫 `copy`（与 pydantic BaseModel.copy 同名），压掉覆盖告警
warnings.filterwarnings("ignore", message=r'Field name "copy".*shadows an attribute')

AD_TYPES = ("product", "promo", "hybrid")
OBJECTIVES = ("leads", "reach", "outbound_clicks", "conversions_purchase", "add_to_cart")
STATUSES = ("ok", "partial", "failed")

AdType = Literal["product", "promo", "hybrid"]
Objective = Literal["leads", "reach", "outbound_clicks", "conversions_purchase", "add_to_cart"]
Status = Literal["ok", "partial", "failed"]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SourceRef(_Loose):
    """§5：sources[] 每一项。"""

    tool: str = ""
    server: str = ""
    query: str = ""
    retrieved_at: str = ""


class ContractPayload(_Loose):
    """所有 scratch/*.json 的公共底座（§5）。"""

    status: Status = "partial"
    sources: list[SourceRef] = Field(default_factory=list)
    facts: list[Any] = Field(default_factory=list)
    inferences: list[Any] = Field(default_factory=list)
    gaps: list[Any] = Field(default_factory=list)


# --------------------------------------------------------------------------
# 路由层契约（§4.2 / §4.3）
# --------------------------------------------------------------------------


class ProductResolved(_Loose):
    brand: str = ""
    product_name: str = ""
    category: str = ""
    price: Any | None = None
    selling_points: list[str] = Field(default_factory=list)


class PromoResolved(_Loose):
    promo_name: str = ""
    mechanic: str = ""
    discount_value: Any | None = None
    threshold: Any | None = None
    code: str = ""
    start_date: str = ""
    end_date: str = ""
    eligible_scope: str = ""
    exclusions: list[str] = Field(default_factory=list)


class Slot(_Loose):
    """`product` / `promo` 两个槽位（§4.1 二取一）。"""

    mode: Literal["url", "manual", "none"] = "none"
    urls: list[str] = Field(default_factory=list)
    raw_text: str = ""
    resolved: dict[str, Any] = Field(default_factory=dict)
    pending_confirm: list[str] = Field(default_factory=list)


class Clarification(_Loose):
    slot: str = ""
    field: str = ""
    question: str = ""


class RouterInput(_Loose):
    """R0 的原始输入（人工填写 / URL），确定性预处理的对象。"""

    product_url: str | None = None
    product_text: str = ""
    promo_url: str | None = None
    promo_text: str = ""
    goal_text: str = ""
    market: str = "US"


class RouterOutput(ContractPayload):
    """`scratch/router.json`（§4.2）。"""

    ad_type: AdType = "product"
    task_profile: AdType = "product"
    decision_note: str = ""
    created_at: str = ""
    slots: dict[str, Slot] = Field(default_factory=dict)
    missing_slots: list[str] = Field(default_factory=list)
    clarifications: list[Clarification] = Field(default_factory=list)


class KPI(_Loose):
    name: str = ""
    baseline_from: str = ""


class Guardrails(_Loose):
    """§4.3：空值必须由 C5 真实数据回填，拿不到记 GAP。"""

    cpa_ceiling: Any | None = None
    non_brand_cpc_cap: Any | None = None
    frequency_cap: Any | None = None


class ObjectiveSpec(_Loose):
    """`scratch/objective.json`（§4.3）。"""

    objective: Objective = "conversions_purchase"
    mapping_note: str = ""
    optimization_event: str = ""
    attribution_window: str = ""
    bid_strategy: str = ""
    primary_kpi: KPI = Field(default_factory=KPI)
    secondary_kpi: list[KPI] = Field(default_factory=list)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    cross_check_note: str = ""


class ObjectivePayload(ObjectiveSpec, ContractPayload):
    """带 status/sources 的落地形态。"""


# --------------------------------------------------------------------------
# 采集层契约（§5）
# --------------------------------------------------------------------------


class Task0Product(ContractPayload):
    input_mode: Literal["url", "brief", "url+brief", "none"] = "none"
    category: str = ""
    selling_points: list[str] = Field(default_factory=list)
    specs: dict[str, Any] = Field(default_factory=dict)
    pending_confirm: list[str] = Field(default_factory=list)
    suggested_supplements: list[str] = Field(default_factory=list)


class PainPoint(_Loose):
    id: str = ""
    text: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    severity: str = ""
    quote: str = ""


class Task1PainPoints(ContractPayload):
    pain_points: list[PainPoint] = Field(default_factory=list)


class CompetitorAd(_Loose):
    brand: str = ""
    platform: str = ""
    creative_type: str = ""
    headline: str = ""
    body: str = ""
    cta: str = ""
    start_date: str = ""
    format: str = ""


class Task2CompetitorAds(ContractPayload):
    ads: list[CompetitorAd] = Field(default_factory=list)
    promo_creative: list[CompetitorAd] = Field(default_factory=list)


class LandingPage(_Loose):
    brand: str = ""
    url: str = ""
    hero_headline: str = ""
    promo_rules: list[str] = Field(default_factory=list)
    cta_text: list[str] = Field(default_factory=list)
    price_anchoring: str = ""


class Task3LandingPages(ContractPayload):
    pages: list[LandingPage] = Field(default_factory=list)


class Trend(_Loose):
    term: str = ""
    values: list[Any] = Field(default_factory=list)
    peak_week: str = ""
    trough_week: str = ""
    seasonality_note: str = ""


class Task4DemandSignals(ContractPayload):
    trends: list[Trend] = Field(default_factory=list)
    keywords: list[dict[str, Any]] = Field(default_factory=list)


class Campaign(_Loose):
    name: str = ""
    spend: Any | None = None
    cpa: Any | None = None
    roas: Any | None = None
    cpc: Any | None = None
    cvr: Any | None = None
    conversions: Any | None = None


class Task5Performance(ContractPayload):
    campaigns: list[Campaign] = Field(default_factory=list)
    account_totals: dict[str, Any] = Field(default_factory=dict)
    promo_baseline: list[dict[str, Any]] = Field(default_factory=list)


# --------------------------------------------------------------------------
# 推理层契约（§5 / §10.4）
# --------------------------------------------------------------------------


class SellingPointMap(_Loose):
    """§9.4 模式B 卖点↔痛点映射校验，判定三选一。"""

    selling_point: str = ""
    pain_point_ref: str = ""
    pain_point_text: str = ""
    evidence: str = ""
    verdict: Literal["主推", "需小预算测试", "缺口机会"] = "需小预算测试"


class Task6Strategy(ContractPayload):
    kano_map: dict[str, Any] = Field(default_factory=dict)
    fogg_decision: dict[str, Any] = Field(default_factory=dict)
    selling_point_map: list[SellingPointMap] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    stop_loss: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class CreativeBrief(_Loose):
    """§10.4 单条素材 Brief（`copy` 是业务字段名，放开 pydantic 保护命名空间）。"""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    asset_id: str = ""
    placement: str = ""
    format: str = ""
    objective: str = ""
    ad_type: str = ""
    target_audience: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    fogg: dict[str, Any] = Field(default_factory=dict)
    copy: dict[str, Any] = Field(default_factory=dict)
    visual_direction: dict[str, Any] = Field(default_factory=dict)
    delivery_spec: dict[str, Any] = Field(default_factory=dict)
    reference_prompts: list[str] = Field(default_factory=list)
    acceptance_checklist: list[str] = Field(default_factory=list)


class Task7Creative(ContractPayload):
    asset_matrix: list[dict[str, Any]] = Field(default_factory=list)
    briefs: list[CreativeBrief] = Field(default_factory=list)
