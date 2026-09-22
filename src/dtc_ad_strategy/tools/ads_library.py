"""facebook-ads-library / gads-transparency 封装（§7 规则）：只暴露品牌名 + 国家。

LLM 不需要知道 `get_meta_platform_id` → `get_meta_ads` 的两步链路，
也不需要理解 gads-transparency 的 advertiser 查找流程。
"""

from __future__ import annotations

import json

from crewai.tools import tool

from .mcp_call import call_mcp_tool


@tool("按品牌名拉取 Meta 在投广告")
def meta_ads_by_brand(brand_names: str, country: str = "US", limit: int = 20) -> str:
    """一次拿到品牌在 Meta Ad Library 的在投广告。

    brand_names 支持逗号分隔多个品牌名。内部自动先解析 platform_id 再拉广告。
    返回 0 条时要区分「未投该渠道」与「ID 用错」，如实记 GAP。
    """
    brands = [b.strip() for b in brand_names.split(",") if b.strip()]
    id_raw = call_mcp_tool("facebook-ads-library", "get_meta_platform_id", {"brand_names": brands})
    if id_raw.startswith("ERROR:"):
        return id_raw

    ids: list[str] = []
    try:
        parsed = json.loads(id_raw)
        items = parsed if isinstance(parsed, list) else [parsed]
        for it in items:
            if isinstance(it, dict):
                for key in ("platform_id", "id", "page_id"):
                    if it.get(key):
                        ids.append(str(it[key]))
                        break
                else:
                    ids.extend(str(v) for v in it.values() if isinstance(v, (int, str)) and str(v).isdigit())
            elif isinstance(it, (int, str)) and str(it).isdigit():
                ids.append(str(it))
    except json.JSONDecodeError:
        # 非 JSON 文本：粗暴抽数字
        import re

        ids = re.findall(r"\b\d{8,}\b", id_raw)

    if not ids:
        return f"GAP: 未解析到 {brands} 的 Meta platform_id。原始返回：{id_raw[:800]}"

    ads = call_mcp_tool(
        "facebook-ads-library",
        "get_meta_ads",
        {"platform_ids": ids, "country": country, "limit": limit},
    )
    return json.dumps({"platform_ids": ids, "ads_raw": ads}, ensure_ascii=False)


@tool("按品牌名拉取 Google Ads Transparency 在投广告")
def gads_ads_by_brand(brand_name: str, country: str = "US") -> str:
    """查竞品在 Google Ads Transparency Center 的在投广告（免凭证）。"""
    found = call_mcp_tool("gads-transparency", "search_advertiser", {"query": brand_name})
    if found.startswith("ERROR:"):
        return found
    return json.dumps({"advertiser_search_raw": found}, ensure_ascii=False)
