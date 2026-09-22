"""复杂 MCP 工具的封装层（§7 规则：只给 LLM 暴露 2-3 个简单入参）。"""

from .ads_library import gads_ads_by_brand, meta_ads_by_brand
from .gaql_wrapper import (
    gaql_campaign_performance,
    gaql_list_customers,
    gaql_search_terms,
)

SIMPLE_TOOLS = [
    gaql_list_customers,
    gaql_campaign_performance,
    gaql_search_terms,
    meta_ads_by_brand,
    gads_ads_by_brand,
]

__all__ = [
    "gaql_list_customers",
    "gaql_campaign_performance",
    "gaql_search_terms",
    "meta_ads_by_brand",
    "gads_ads_by_brand",
    "SIMPLE_TOOLS",
]
