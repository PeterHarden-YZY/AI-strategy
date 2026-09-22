"""CLI 入口。

示例：
    # 产品广告（已发布 URL）
    .venv/Scripts/python run.py --product-url "https://..." --goal "想多卖货"

    # 混合广告（产品 URL + 活动链接）
    .venv/Scripts/python run.py --product-url "https://..." --promo-url "https://..." --goal "加购"

    # 活动广告（手填活动内容）
    .venv/Scripts/python run.py --promo-text "黑五全场 20% OFF，code BF20，11/20-11/30"

    # 离线模式（用 fixtures 跑策略层，不调 MCP）
    .venv/Scripts/python run.py --product-text "HUANUO 63 Premium Topaz" --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dtc_ad_strategy import paths  # noqa: E402
from dtc_ad_strategy.crew import DtcAdStrategyCrew  # noqa: E402
from dtc_ad_strategy.schemas import RouterInput  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DTC 广告策略引擎 v2")
    p.add_argument("--product-url", default="", help="产品落地页 URL（product 槽 URL 模式）")
    p.add_argument("--product-text", default="", help="产品简报文本（product 槽人工模式）")
    p.add_argument("--promo-url", default="", help="活动页 / 落地页 / EDM URL")
    p.add_argument("--promo-text", default="", help="活动内容手填文本")
    p.add_argument("--goal", default="", help="投放目的口语描述（R1 映射到 objective 枚举）")
    p.add_argument("--scratch", default="", help="scratch 目录")
    p.add_argument("--output", default="", help="output 目录")
    p.add_argument("--offline", action="store_true", help="用 fixtures 跑，不调 MCP")
    p.add_argument(
        "--skip-collection",
        action="store_true",
        help="跳过采集层（用已有的 scratch/*.json 直接跑策略层）",
    )
    p.add_argument("--pre-route-only", action="store_true", help="只跑确定性路由，不调 LLM")
    p.add_argument(
        "--only",
        choices=["router", "collection", "strategy", "full"],
        default="full",
        help="只跑指定阶段（默认 full = R → A → B）",
    )
    p.add_argument(
        "--steps",
        default="",
        help="逗号分隔的 task 名，只跑这些步骤（配合 --only collection / strategy 使用）",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()

    inp = RouterInput(
        product_url=args.product_url or None,
        product_text=args.product_text,
        promo_url=args.promo_url or None,
        promo_text=args.promo_text,
        goal_text=args.goal,
    )

    if args.pre_route_only:
        from dtc_ad_strategy import router

        print(json.dumps(router.pre_route(inp), ensure_ascii=False, indent=2))
        return 0

    crew = DtcAdStrategyCrew(
        router_input=inp,
        scratch=Path(args.scratch) if args.scratch else None,
        output=Path(args.output) if args.output else None,
    )
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    if args.only == "router":
        result = crew.route()
    elif args.only == "collection":
        result = crew.collect(offline=args.offline, steps=steps or None)
    elif args.only == "strategy":
        result = crew.strategize(steps=steps or None)
    else:
        result = crew.run(offline=args.offline, skip_collection=args.skip_collection)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") != "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
