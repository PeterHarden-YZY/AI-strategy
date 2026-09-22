"""google-ads 封装（§7 规则）：只给 LLM 暴露 2-3 个简单入参。

背景：`search_search` 需要手写 GAQL，字段名几十个且类 SQL；写错的表现是**静默返回空**，
是本项目最危险的失败模式（§12.2）。因此这里预置已实测通过的 GAQL 模板，
LLM 只需给 `customer_id` + 时间范围（+ 可选关键词过滤）。
"""

from __future__ import annotations

from typing import Any

from crewai.tools import tool

from .mcp_call import call_mcp_tool

# 已实测通过（2026-09-22，customer 8890624174）的字段组合，勿随意增删字段名
GAQL_TEMPLATES: dict[str, dict[str, Any]] = {
    "campaign_performance": {
        "resource": "campaign",
        "fields": [
            "campaign.name",
            "metrics.cost_micros",
            "metrics.conversions",
            "metrics.conversions_value",
            "metrics.average_cpc",
            "metrics.clicks",
            "metrics.impressions",
        ],
        "orderings": ["metrics.cost_micros DESC"],
    },
    "search_terms": {
        "resource": "search_term_view",
        "fields": [
            "search_term_view.search_term",
            "campaign.name",
            "metrics.clicks",
            "metrics.cost_micros",
            "metrics.conversions",
            "metrics.conversions_value",
        ],
        "orderings": ["metrics.clicks DESC"],
    },
    "keyword_performance": {
        "resource": "keyword_view",
        "fields": [
            "ad_group_criterion.criterion_id",
            "ad_group_criterion.keyword.text",
            "ad_group_criterion.keyword.match_type",
            "campaign.name",
            "metrics.clicks",
            "metrics.cost_micros",
            "metrics.conversions",
            "metrics.conversions_value",
        ],
        "orderings": ["metrics.clicks DESC"],
    },
}

_DATE_MACROS = {
    "last_7d": "segments.date DURING LAST_7_DAYS",
    "last_30d": "segments.date DURING LAST_30_DAYS",
    "last_90d": "segments.date DURING LAST_90_DAYS",
    "this_month": "segments.date DURING THIS_MONTH",
    "last_month": "segments.date DURING LAST_MONTH",
}


def build_gaql(
    template: str,
    customer_id: str,
    date_range: str = "last_30d",
    extra_conditions: list[str] | None = None,
    name_filter: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """拼出 `search_search` 的完整入参。"""
    tpl = GAQL_TEMPLATES.get(template)
    if tpl is None:
        raise ValueError(
            f"未知 GAQL 模板：{template}，可用：{sorted(GAQL_TEMPLATES)}"
        )
    conditions = [_DATE_MACROS.get(date_range, _DATE_MACROS["last_30d"])]
    if name_filter:
        conditions.append(f"campaign.name LIKE '%{name_filter}%'")
    conditions.extend(extra_conditions or [])
    return {
        "customer_id": customer_id,
        "resource": tpl["resource"],
        "fields": list(tpl["fields"]),
        "conditions": conditions,
        "orderings": list(tpl["orderings"]),
        "limit": limit,
    }


@tool("GAQL 账户/系列表现查询")
def gaql_campaign_performance(
    customer_id: str,
    date_range: str = "last_30d",
    name_filter: str = "",
) -> str:
    """拉取 Google Ads 各 campaign 的花费/转化/收入/CPC/点击/曝光。

    date_range 可选：last_7d / last_30d / last_90d / this_month / last_month。
    name_filter 为 campaign 名模糊匹配（找历史同期活动 campaign 时用它，例：'202509'）。
    """
    args = build_gaql("campaign_performance", customer_id, date_range, name_filter=name_filter)
    return call_mcp_tool("google-ads", "search_search", args)


@tool("GAQL 搜索词报告查询")
def gaql_search_terms(
    customer_id: str,
    date_range: str = "last_30d",
    name_filter: str = "",
) -> str:
    """拉取搜索词报告：搜索词 + 所属 campaign + 点击/花费/转化/收入，按点击降序。"""
    args = build_gaql("search_terms", customer_id, date_range, name_filter=name_filter)
    return call_mcp_tool("google-ads", "search_search", args)


@tool("列出可访问的 Google Ads 客户 ID")
def gaql_list_customers() -> str:
    """列出当前凭证可访问的 Google Ads customer_id。取数前先调它。"""
    return call_mcp_tool("google-ads", "customers_list_accessible_customers", {})
