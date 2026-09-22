# 素材 Brief 模板（S1 填充 · 交付给设计师 / 剪辑师）

> 用途：创意层主交付物 `output/creative_brief.md` 的单条结构（§10.4）。
> 规则：每条逐项填齐，缺失写 `{待确认}`，**不得省略字段、不得合并字段**。
> 判准：读完不需要回头追问就能开工。AI 图 Prompt 只允许出现在 `reference_prompts`。

---

```yaml
asset_id:        V1-9x16-M-leads              # 全局唯一，报告里按此引用
placement:       Meta Reels / TikTok In-feed
format:          9:16, 15s, 烧字幕, 静音可懂
objective:       leads                        # 来自 objective.json
ad_type:         hybrid                       # 来自 router.json
target_audience: { persona, trigger_scene }

strategy:
  selling_point:    "<一句话主推卖点>"
  pain_point_ref:   "task1_painpoints.json#pp_03"   # 必须可追溯，见 §9.3
  kano_class:       "期望型 / 必备型 / 魅力型 / 无差异"
  competitor_diff:  "vs FlexiSpot 355lbs：改讲稳定性 + 美国本地发货"   # 引 task2 / task3

fogg:
  motivation:                                 # B=MAP 里的 M
    dimension:     "愉悦/痛苦 ｜ 希望/恐惧 ｜ 认同/排斥"    # 三选一
    expression:    "画面 / 文案如何兑现这个动机"
    evidence_ref:  "task1_painpoints.json#pp_03 原文 quote"
  ability:                                    # B=MAP 里的 A
    cost_cut:      "金钱 / 时间 / 体力 / 脑力 / 社会偏离 / 非常规"   # 六选一
    expression:    "素材里怎么把这件事说成很容易（免安装 / 30 秒看懂 / 0 风险退换…）"
  prompt:                                     # B=MAP 里的 P
    type:          "signal 信号 / facilitator 引导 / spark 刺激"
    position:      "前 3 秒钩子 / 中段 / 结尾 CTA / 角标"
    expression:    "<提示语原文>"

copy:
  hook_0_3s:      "<前 3 秒口播 + 字幕，原文>"
  body_lines:     ["<字幕行 1>", "<字幕行 2>"]
  overlay_text:   ["<画面贴字，注意字符上限>"]
  cta:            "<CTA 原文，须与落地页 CTA 逐字一致>"    # 引 task3

visual_direction:
  shot_list:      [{"t":"0-3s","画面":"","镜头":"","字幕":"","音效":""}]
  composition:    "主体 / 场景 / 构图 / 光位"
  color_material: "主色 / 材质 / 对比手法"
  must_avoid:     ["禁词", "合规雷区", "与竞品雷同的元素"]   # 引 task2 避免撞车

delivery_spec:
  size_duration:  "1080x1920, 15s"
  safe_area:      "上下 14%，右 20%"
  audio:          "口播 / BGM / 静音可懂"
  files:          "MP4 H.264 + 无字幕版 + 900x1600 安全版"

reference_prompts:              # 仅作氛围参考图，非终稿，缺失记 GAP 不影响验收
  - "<AI 图 Prompt A>"
  - "<AI 图 Prompt B>"

acceptance_checklist:
  - 前 3 秒钩子在静音状态下是否成立？
  - CTA 是否与落地页原文一致？
  - 折扣 / 截止日期是否与 router.json.slots.promo.resolved 逐字一致？
  - 主推卖点能否追溯到一条带证据的痛点？
```
