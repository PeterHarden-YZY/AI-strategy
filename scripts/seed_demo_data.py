"""初始化测试演示数据脚本。
将 fixtures 载入 scratch/，并生成符合 schema 的示例策略和素材 Brief 契约与报告。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dtc_ad_strategy import paths, router
from dtc_ad_strategy.schemas import RouterInput
import shutil

def main():
    paths.ensure_dirs()
    for src in sorted(paths.FIXTURES.glob("*.json")):
        name = src.name.replace("task5_historical_performance", "task5_performance")
        dst = paths.SCRATCH / name
        shutil.copyfile(src, dst)
        payload = router.read_json(dst)
        for key in ("status", "sources", "facts", "inferences", "gaps"):
            payload.setdefault(key, [] if key != "status" else "ok")
        router.write_json(dst, payload)

    # 生成 router.json & objective.json
    inp = RouterInput(
        product_url="https://www.huanuo.com/products/huanuo-63-inch-electric-standing-desk-topaz",
        product_text="HUANUO 63\" Premium Topaz L-Shaped Electric Standing Desk, dual motors, 176 lbs capacity, anti-collision sensor, memory presets, solid alloy steel frame, retail $1099.99.",
        market="US",
        goal_text="提升高客单转化，对齐居家办公与健康办公人群",
    )
    r_out = router.pre_route(inp)
    router.write_json(paths.SCRATCH / "router.json", r_out)

    obj_out = router.default_objective("conversions_purchase", "对齐用户输入「提升高客单转化」口语意图，映射至 conversions_purchase")
    router.write_json(paths.SCRATCH / "objective.json", obj_out)

    # 填充 task6_strategy.json
    task6_data = {
        "status": "ok",
        "sources": [{"tool": "strategy_synthesizer", "server": "crew-b", "query": "S0 synthesis", "retrieved_at": "2026-09-22T23:50:00Z"}],
        "facts": [
            "C5 历史数据显示支架品类 ROAS 达 4.01x，但仅分配 1.8% 预算",
            "Google Trends 显示 4 月为全行业兴趣峰值 (100)，当前 9 月为谷底 (4)"
        ],
        "inferences": [
            "以双电机高承重与静音为切入点，通过痛点对齐打消摇晃顾虑",
            "秋促应主打门槛击穿 (A 路径)，为次年 3-4 月旺季蓄水素材"
        ],
        "gaps": ["Meta 侧历史投放素材颗粒度数据缺失，需开通 Meta Ads API 补齐"],
        "recommendations": [
            "主力预算建议按 60% PMAX + 25% 搜索精准词 + 15% 支架/配件 cross-sell 组合配置",
            "针对大桌板摇晃痛点，前 3 秒钩子强化「放满 3 台显示器升降水杯不晃」物理实验视觉",
            "设置 CPA 止损红线为 $320，若连续 7 天超过且转化数 < 5 即触发限流或换素材"
        ],
        "kano_map": {
            "must_be": ["双电机升降平稳", "防夹回退遇阻自停", "合规电源与电磁认证"],
            "performance": ["63寸大桌面空间容量", "4档高度记忆预设", "静音分贝 < 45dB"],
            "attractive": ["整桌实木纹理质感", "理线槽隐形收纳系统", "10 年超长整机质保"]
        },
        "fogg_decision": {
            "dominant_path": "A",
            "motivation": {
                "dimension": "痛苦消除 (腰颈椎慢性疼痛)",
                "description": "久坐腰酸背痛与大桌面晃动导致的烦躁焦虑",
                "evidence_ref": "task1_painpoints.json pp_01"
            },
            "ability": {
                "cost_cut": "价格门槛降低",
                "description": "秋促直降 + 0 首付 4 期免息分期，打消千元级大件决策阻力",
                "expression": "$1099 -> $899 限时立省 $200"
            },
            "prompt": {
                "type": "限时紧迫感触发",
                "expression": "首发前 100 名赠定制理线魔术贴与双臂显示器支架券",
                "position": "首屏 Hero Banner + 视频最后 3 秒倒计时"
            }
        },
        "selling_point_map": [
            {"selling_point": "双电机重载合金钢架 (承重 176 lbs)", "pain_point_ref": "pp_01", "pain_point_text": "升降到最高点打字桌面严重晃动", "evidence": "Reddit r/StandingDesk 127条抱怨", "verdict": "主推"},
            {"selling_point": "63 英寸宽幅弧形大桌面", "pain_point_ref": "pp_02", "pain_point_text": "多屏与主机放置后空间逼仄无处下脚", "evidence": "Amazon 差评采样 18%", "verdict": "主推"},
            {"selling_point": "遇阻自停防夹传感器", "pain_point_ref": "pp_04", "pain_point_text": "担心宠物或小孩误触升降被挤压", "evidence": "家庭办公场景高频提及", "verdict": "需小预算测试"},
            {"selling_point": "FSA/HSA 医疗免税抵扣支持", "pain_point_ref": "pp_06", "pain_point_text": "健康办公设备费用报销流程繁琐", "evidence": "美国健康保险政策关注点", "verdict": "缺口机会"}
        ],
        "budget": {
            "total_monthly_usd": 35000,
            "allocation": {"PMAX": "55%", "Search_NonBrand": "25%", "Shopping_Accessories": "15%", "Retargeting": "5%"},
            "cpc_ceiling_non_brand": 4.50,
            "target_roas": 3.20
        },
        "stop_loss": {
            "cpa_circuit_breaker": 320.0,
            "min_conversions_window_days": 7,
            "low_cvr_threshold": "0.8%",
            "action_on_trigger": "暂停表现倒数 20% 素材组，将预算倾斜至支架与中下层漏斗词"
        }
    }
    router.write_json(paths.SCRATCH / "task6_strategy.json", task6_data)

    # 填充 task7_creative.json
    task7_data = {
        "status": "ok",
        "sources": [{"tool": "creative_director", "server": "crew-b", "query": "S1 briefs", "retrieved_at": "2026-09-22T23:50:00Z"}],
        "facts": ["生成 6 套完整素材 Brief", "覆盖 9:16 / 1:1 / 16:9 版位"],
        "inferences": ["以高动态实拍开场配合水杯不倒实验可极大提升前 3 秒留存"],
        "gaps": [],
        "asset_matrix": [
            {"asset_id": "V1-9x16-A-purchase", "placement": "TikTok/Reels", "format": "9:16 Video (15s)", "selling_point": "双电机升降极稳", "fogg_path": "A", "objective": "conversions_purchase"},
            {"asset_id": "V2-9x16-M-cart", "placement": "Meta Stories", "format": "9:16 Video (15s)", "selling_point": "腰颈减压健康生活", "fogg_path": "M", "objective": "add_to_cart"},
            {"asset_id": "I1-1x1-A-purchase", "placement": "Instagram Feed", "format": "1:1 Image Carousel", "selling_point": "63寸桌面大容量", "fogg_path": "A", "objective": "conversions_purchase"}
        ],
        "briefs": [
            {
                "asset_id": "V1-9x16-A-purchase",
                "placement": "TikTok / Instagram Reels 9:16 沉浸流",
                "format": "短视频 (15s MP4)",
                "objective": "conversions_purchase",
                "ad_type": "product",
                "strategy": {"selling_point": "双电机重载合金钢架 · 升降不晃", "pain_point_ref": "pp_01", "kano_class": "Must-be 必备型"},
                "copy": {
                    "hook_0_3s": "你买的升降桌，一打字咖啡就波浪翻滚？来看这个「满杯水升降」极限测试！",
                    "primary_text": "HUANUO 63\" Topaz 双电机旗舰升降桌，双电机强劲驱动，176 lbs 狂暴载重，升降过程水滴不洒！秋促直降 $200，全美包邮。",
                    "headlines": ["摆满 3 台显示器照样稳如磐石", "久坐拯救者：1 秒切换站立办公"],
                    "cta": "Shop Now · 限时立省 $200"
                },
                "visual_direction": {
                    "shot_list": [
                        {"time": "00:00 - 00:03", "visual": "特写：桌角放一杯装满 99% 的黑咖啡，升降桌从最低 28\" 极速升至 46\"，水面波澜不惊", "audio": "急促音效，突然静止，清脆打字机械键盘声", "overlay": "升降水杯挑战：一滴都不洒？！"},
                        {"time": "00:03 - 00:09", "visual": "全景切换：程序员双手用力下压桌板，稳固不晃；镜头掠过双电机与一体式理线槽", "audio": "旁白：双电机驱动才是真平稳，告别晃荡打字噩梦", "overlay": "176 lbs 航天级承重 · 德国双电机"},
                        {"time": "00:09 - 00:15", "visual": "一键 4 档高度记忆触控，女主人优雅站立办公，屏幕弹出秋促直降立省 $200 优惠码", "audio": "上扬节拍，清脆按键提示音：限时特惠，手慢无", "overlay": "秋促直降 $200 · Code: TOPAZ200"}
                    ]
                },
                "reference_prompts": [
                    "Commercial photography of a sleek modern home office at dusk, HUANUO 63 inch L-shaped dark walnut standing desk, three 4K monitors glowing with code and analytics, warm ambient LED lighting, ergonomic chair, minimalist aesthetic, 8k resolution, photorealistic, cinematic lighting --ar 9:16",
                    "Macro close-up shot of a transparent glass coffee cup filled with black espresso sitting on a textured dark wood standing desk surface, perfectly still liquid without ripples, warm dramatic side lighting, shallow depth of field --ar 9:16"
                ],
                "acceptance_checklist": [
                    "前 3 秒画面必须清晰展示满水杯特写，严禁 logo 开场",
                    "必须出现 4 档记忆高度按键的真实触控动作",
                    "结尾必须包含清晰的折扣价格锚点与优惠码提示"
                ]
            }
        ]
    }
    router.write_json(paths.SCRATCH / "task7_creative.json", task7_data)

    # 填充 output/ 示例交付物
    report_md = """# DTC 广告战略指导书：HUANUO 63\" Premium Topaz 升降桌

## 1. 战略执行摘要 (Executive Summary)
本报告基于 2026 年 Q3 真实历史投放表现（累计消耗 $239,380，综合 ROAS 3.28x）、Google Trends 需求信号及竞品广告库综合制定。核心目标为守住 3.2+ ROAS 底线，同时为次年 3-4 月旺季构建素材护城河。

## 2. 需求信号与季节性战役规划
- **搜索兴趣低谷应对**：9 月处于 Google Trends 搜索谷底（指数 4），相比 4 月峰值（100）需求相对疲软。
- **战役节奏**：秋促期间严格以「门槛击穿 (A 路径)」驱动换新，不盲目泛推 PMAX，预算向高转化中下层精准词倾斜。

## 3. KANO 卖点与痛点校验结论
- **主推卖点 1**：双电机高承重钢架（对应 Reddit 高频痛点：升降打字桌面剧烈晃动）
- **主推卖点 2**：63 寸宽幅弧形桌面（对应多屏办公场景空间紧凑痛点）
- **小预算测试**：遇阻自停防夹传感器（家有宠物或孩童的安全保障）

## 4. 账户投放架构与预算分配
- **PMAX 智能投放**：55% 预算份额，承担品牌与产品破圈
- **Search 下层意图词**：25% 预算份额，承接强购买心智用户
- **支架及配件 Cross-Sell**：15% 预算份额，高 ROAS (4.01x) 放大器
- **动态再营销**：5% 预算份额，挽回放弃加购人群
"""
    (paths.OUTPUT / "strategy_report.md").write_text(report_md, encoding="utf-8")

    brief_md = """# DTC 素材制作 Brief 派工单 (Asset Briefs)

## 脚本编号：V1-9x16-A-purchase
- **版位格式**：TikTok / Instagram Reels (9:16 Video, 15秒)
- **主打卖点**：双电机重载合金钢架 · 升降不晃
- **对应痛点**：pp_01 打字摇晃与咖啡泼洒
- **福格路径**：A 门槛击穿 (直降 $200 优惠码)

### 前 3 秒黄金钩子
> 「你买的升降桌，一打字咖啡就波浪翻滚？来看这个『满杯水升降』极限测试！」

### 分镜制作明细表
| 时间段 | 画面视觉动作 | 旁白与音频音效 | 贴片字幕规范 |
| :--- | :--- | :--- | :--- |
| **00:00 - 00:03** | 满杯黑咖啡放桌角，升降桌极速上升，水滴不洒 | 急促音效骤停，清脆机械键盘声 | 升降水杯挑战：一滴都不洒？！ |
| **00:03 - 00:09** | 程序员双手重压桌沿稳如泰山，镜头带过双电机与收纳槽 | 旁白：德国双电机强劲驱动，告别摇晃 | 176 lbs 狂暴承重 · 稳如磐石 |
| **00:09 - 00:15** | 一键触控升至站立办公位，定格秋促优惠立减 $200 | 欢快上扬音效，点击清脆声 | 秋促直降 $200 · Code: TOPAZ200 |

### AI 绘图 / 分镜参考 Prompt
```text
Commercial photography of a sleek modern home office at dusk, HUANUO 63 inch L-shaped dark walnut standing desk, three 4K monitors glowing with code, warm ambient LED lighting, ergonomic chair, cinematic lighting --ar 9:16
```
"""
    (paths.OUTPUT / "creative_brief.md").write_text(brief_md, encoding="utf-8")
    print("All demo contracts and reports generated successfully.")

if __name__ == "__main__":
    main()
