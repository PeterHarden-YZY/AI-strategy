# agent.md — DTC 广告策略引擎 · MVP 规格

> **本文件是施工图纸，不是原则声明。**
> 任何 coding agent（CodeBuddy / WorkBuddy / Codex）拿到本文件，应能独立构建出可运行的系统。
> 粒度对齐 `skills/dtc-ad-strategy/SKILL.md`（Step / Input Context / 动作 / Persist Output），内容升级为 MCP 驱动版。
>
> 标记：`【事实】` 已实测 ｜ `【规则】` 约束条款 ｜ `【待定】` 待 Arthur 拍板

---

## 0. 一句话定义

一个**由真实数据驱动的** DTC 广告策略生成系统：用户输入先经**广告类型路由器**（产品 / 活动 / 混合）与**广告目的选择器**（leads / 覆盖面 / 出站点击 / 转化购买 / 加购）翻译成结构化契约，再接入 7 个 MCP 采集竞品广告 / 落地页 / 用户评论 / 需求信号 / 自有投放数据，经多 agent 推理，产出一份能直接进广告后台执行的策略全案。

判准只有一条：**报告里每条建议，能否当天变成广告后台的一次操作。**

---

## 1. MVP 范围（钉死，不得蔓延）

### 做
1. **路由层**：广告类型三选一（产品 / 活动 / 混合）+ 广告目的五选一（leads / 覆盖面 / 出站点击 / 转化购买 / 加购），见 §4
2. 双模式输入：产品槽与活动槽各自支持（已发布 URL / 未发布人工填写）
3. 六路数据采集，全部走真实 MCP，落 `scratch/*.json`（按 `task_profile` 调整开关）
4. 路由层与采集层、采集层与推理层解耦（三个 Crew，JSON 为契约）
5. KANO + 福格策略合成，含模式B 卖点↔痛点映射校验
6. 创意输出（**素材 Brief：福格三要素 + 镜头/文案/交付规格**），AI 图 Prompt 降级为参考图
7. 汇总产出 `output/strategy_report.md` + `output/creative_brief.md`，必答五问 + 回显 `ad_type` / `objective`

### 不做（MVP 之后再说）
- 多市场 / 多语言（MVP 只做 US 站英文）
- 自动化调度 / 定时跑
- Web UI / Dashboard
- 客服工单数据（`【事实】` 在内部系统，任何 MCP 够不着，只能人工导 CSV）
- 素材自动生成（**只出参考图 Prompt，且必须挂在 Brief 的 `reference_prompts` 字段下**，不调图像模型）

---

## 2. 验收标准（Definition of Done）

系统算建成，必须同时满足：

| # | 标准 | 验证方式 |
|---|---|---|
| A1 | `crewai-tools[mcp]` 装好，`MCP_AVAILABLE == True` | `python -c "from crewai_tools.adapters.mcp_adapter import MCP_AVAILABLE; print(MCP_AVAILABLE)"` |
| A2 | **单 Crew 能同时连 ≥2 个 MCP server** | 起一个 adapter 挂 2 个 server，列出工具数 > 单 server 工具数 |
| A3 | 采集 Crew 跑通 6 个 task，产出 6 个非空 JSON | `scratch/` 下 6 个文件均含 `status` 与数据字段 |
| A4 | 每个采集 task 的工具调用有真实返回 | JSON 中 FACT 条目均带 `source` 字段 |
| A5 | 策略 Crew 读 JSON 跑通，产出报告 | `output/strategy_report.md` 存在且非空 |
| A6 | **报告必答五问**（投什么/怎么写/落哪里/花多少/何时停） | 人工过一遍，任一问无答案即不通过 |
| A7 | 工具返回空时记为 GAP 而非脑补 | 断网/错参测试：报告中应出现 GAP 标注 |
| A8 | 路由层产出合法契约，objective 命中枚举 | `scratch/router.json` + `scratch/objective.json` 存在，`ad_type∈{product,promo,hybrid}`、`objective∈{leads,reach,outbound_clicks,conversions_purchase,add_to_cart}` |
| A9 | 三种 `ad_type` 跑出的报告有明显差异 | `promo`/`hybrid` 报告必含：活动规则、折扣口径、截止日期、历史同期活动基线；`product` 报告必含：卖点↔痛点映射表 |
| A10 | 活动数字零容错 | 输入故意留空折扣值时，报告对应位置出现 `{…待确认}` 占位，而非估算数字 |
| A11 | 创意层交付的是 Brief 而非 Prompt | `output/creative_brief.md` 存在且 ≥6 条 Brief，每条含完整福格三要素、镜号、CTA、交付规格；AI 图 Prompt 只出现在 `reference_prompts` 字段内 |

**A2 是最高优先级风险，必须先验证。`【事实】`** `MCPServerAdapter(serverparams)` 签名是单个 `StdioServerParameters | dict`，非 list。若实测多 server 不可行，则改为「每个采集 Crew 只连一个 server」并按数据源拆 Crew，或自写多 server adapter。**此项未验证前不要写下游代码。**

---

## 3. 项目结构（新项目骨架）

```
dtc_ad_strategy_v2/
├── .codebuddy/
│   ├── rules/agent.md          # 本文件，项目宪法
│   └── mcp.json                # 项目级 MCP 配置（凭证走 env）
├── src/dtc_ad_strategy/
│   ├── crew.py                 # @CrewBase 主入口（class-based，必须）
│   ├── router.py               # 确定性预处理：URL/文本判定、槽位完整性、单次澄清（零 LLM）
│   ├── crews/
│   │   ├── router_crew.py      # R0 输入路由 Crew + R1 目的选择 Crew
│   │   ├── collection_crew.py  # 采集 Crew（工具密集）
│   │   └── strategy_crew.py    # 策略 Crew（纯推理）
│   ├── agents/                 # agent_1..5.jsonc + agent_r0/r1.jsonc
│   ├── tasks/                  # task 定义（含 router task）
│   ├── tools/
│   │   ├── gaql_wrapper.py     # google-ads 封装：只暴露简单入参
│   │   └── ads_library.py      # facebook/gads 封装
│   └── schemas.py              # scratch/*.json 的 Pydantic 模型（含 RouterInput / ObjectiveSpec）
├── scratch/                    # 数据契约层（路由→采集→推理）
│   ├── router.json             # R0 产出：ad_type + 输入槽解析
│   └── objective.json          # R1 产出：objective + KPI + 出价 + 护栏
├── fixtures/                   # 旧项目真实数据，做离线测试用
├── knowledge/
│   ├── product_brief_template.md
│   └── creative_brief_template.md   # 单条素材 Brief 模板（§10.3 结构的空模板）
├── output/
│   ├── strategy_report.md
│   └── creative_brief.md            # 创意主交付物（给设计师/剪辑师）
├── .env.example                # 变量名清单，不含真值
└── pyproject.toml              # 含 crewai-tools[mcp]
```

### 3.1 迁移清单（CodeBuddy 必读，不得跳过）

旧项目路径：**`D:\agents_project\dtc_ad_strategy`**

以下资产是三轮迭代的成果，**必须原样提取，不得重写、不得"优化"**：

| 资产 | 旧路径 | 提取要求 |
|---|---|---|
| Agent 人格 | `agents/agent_1.jsonc` ~ `agent_4.jsonc` | `role` / `goal` / `backstory` 原文，一字不改 |
| Task 提示词 | `crew.jsonc` → `tasks[]` | `description` / `expected_output` 原文 |
| 双模式输入 | `crew.jsonc` task[0] | 模式A/B 定义 + 模式B 铁律（严禁编造、标【待确认】、附建议补充清单） |
| 卖点↔痛点映射校验 | `crew.jsonc` task[3] | 三段判定原文（主推 / 需小预算测试 / 缺口机会）+ 主推必须可追溯铁律 |
| 简报模板 | `knowledge/product_brief_template.md` | 整文件复制到新项目 `knowledge/` |
| **素材 Brief 模板** | 新写（按 §10.4 YAML 结构） | 新建 `knowledge/creative_brief_template.md`，空模板随项目提交，S1 按此填充 |
| Fixtures | `scratch/*.json` | 复制到 `fixtures/`，作离线测试用（真实 MCP 数据，非推测） |
| 业务基线 | 本文件 §14 | 6 条已验证结论，供策略层参照 |

**⚠️ 唯一允许改写的地方**：旧 `crew.jsonc` 中 task 的 `name` 字段是 UI 自动生成的垃圾名（`_kano__task`、`_1__15_task`、`_product_name_trustpilotamazonyoutubereddit_task`、`_product_name__task`），会原样变成报告章节标题。**只取 `description` / `expected_output`，`name` 必须按 §6 重新语义化命名**（如 `user_pain_points_task`）。

**`【规则】` 旧项目的"双模式输入"（模式A URL / 模式B 简报）不废弃，但上移一层**：它现在是 §4 中 `product` 槽的取值方式；新增的 `promo` 槽沿用同一套双模式规则（活动链接 / 手填活动内容）。旧 task[0] 的铁律原文照搬到 R0 的 `product` 槽。

**`【事实】` 为什么必须 class-based**：`crewai/project/crew_loader.py` 中 `mcp` 关键字零命中。`mcp_server_params` / `get_mcp_tools()` 只存在于 class-based `CrewBase`。纯 JSONC 声明式路线接不了 MCP。
**`【规则】`** 旧 `agents/*.jsonc` 与 `crew.jsonc` **不迁移格式**，由 `crew.py` 手动读取构造 Agent/Task，提示词一个字不动。

---

## 4. 最上层：广告类型路由器 + 广告目的选择器【规则】

R0 / R1 是**确定性决策层**，位于 Crew A 之上，先于任何采集发生。
唯一职责：**把用户输入翻译成结构化契约**，不产出任何策略建议。

```
用户输入
  │
  ├─ R0 广告类型路由（ad_type 三选一 + 输入槽解析）  → scratch/router.json
  │
  └─ R1 广告目的选择（objective 五选一）             → scratch/objective.json
        │
        └── Crew A 采集（按 task_profile 调整各 task 开关与权重）
              └── Crew B 策略（按 objective 的主 KPI / 出价 / 止损矩阵产出）
```

**`【规则】`** 没有 `router.json` 与 `objective.json`，Crew A / Crew B 不得启动。

### 4.1 广告类型：三选一

| `ad_type` | 定义 | 创意主轴 | 必需输入槽 |
|---|---|---|---|
| `product` **产品广告** | 主卖点宣传，常年在线（Evergreen），不与活动绑定 | 卖点↔痛点映射，产品力叙事 | `product` |
| `promo` **活动广告** | 宣传活动内容与折扣，有明确起止时间与参与门槛 | 折扣机制、紧迫感、活动规则 | `promo` |
| `hybrid` **混合广告** | 产品卖点 + 活动内容同屏，先讲卖点再收折扣 | 卖点承接 + 活动收口 | `product` **且** `promo` |

每个槽位**二取一**填写：

| 槽 | URL 模式 | 人工模式 |
|---|---|---|
| `product` | 输入产品链接 → `playwright` 抓页解析 | 用户按 `knowledge/product_brief_template.md` 手填产品简报 |
| `promo` | 输入活动链接（活动页 / 落地页 / EDM）→ `playwright` 抓活动标题、规则、折扣、起止、门槛、排除项 | 用户手填活动内容 |

**`【规则】`** 两个槽的取值模式互相独立：`product=url + promo=manual` 合法，`hybrid` 下允许混搭。
**`【规则】`** 任一模式的缺失字段一律进 `pending_confirm`，**严禁模型补全**（继承 §9.1 数据纪律）。
**`【规则】` 活动数字零容错**：折扣力度、满减门槛、优惠码、起止日期不得估算、不得取整、不得写成"约 X 折"；拿不到即以 `{折扣力度待确认}` 占位进入下游文案。

#### 路由判定优先级（自上而下，命中即停）

1. 用户同时提供 **产品信息 + 活动信息** → `hybrid`
2. 只提供产品信息，但内容中出现明确折扣 / 限时 / 节日节点 → 判为 `hybrid` **候选**，须向用户确认一次（可降为 `product`）
3. 只提供活动信息，且活动只覆盖单一 SKU → 默认 `promo`，同时提示可补齐产品卖点升级为 `hybrid`，是否升级由用户决定
4. 其余 → `product`

### 4.2 `scratch/router.json` 契约

```json
{
  "status": "ok | partial | failed",
  "ad_type": "product | promo | hybrid",
  "task_profile": "product | promo | hybrid",
  "decision_note": "命中判定优先级第 N 条 + 理由",
  "created_at": "ISO8601",
  "slots": {
    "product": {
      "mode": "url | manual | none",
      "urls": [],
      "raw_text": "",
      "resolved": {"brand":"","product_name":"","category":"","price":null,"selling_points":[]},
      "pending_confirm": []
    },
    "promo": {
      "mode": "url | manual | none",
      "urls": [],
      "raw_text": "",
      "resolved": {"promo_name":"","mechanic":"","discount_value":null,"threshold":null,"code":"","start_date":"","end_date":"","eligible_scope":"","exclusions":[]},
      "pending_confirm": []
    }
  },
  "missing_slots": [],
  "clarifications": [{"slot":"","field":"","question":""}],
  "sources": [{"tool":"","server":"","query":"","retrieved_at":""}]
}
```

**`【规则】` 澄清只允许单批次**：R0 把所有缺失字段一次性列成 `clarifications[]` 问完，禁止挤牙膏式多轮追问。
**`【规则】`** `ad_type=product` 且 `slots.product.mode == "none"` → R0 直接 `status="failed"` 终止，且不调用任何采集工具。

### 4.3 广告目的：五选一（R1）

| `objective` | 定义 | Meta 原生目标 | Google 原生目标 | 主优化事件 |
|---|---|---|---|---|
| `leads` | 留资 / 线索获取 | `OUTCOME_LEADS` | Search / Demand Gen（表单提交） | Lead |
| `reach` | 覆盖面 / 曝光 | `OUTCOME_AWARENESS`（Reach + 频次控制） | YouTube / Demand Gen（曝光出价） | Impression / Reach |
| `outbound_clicks` | 出站点击 / 引流 | `OUTCOME_TRAFFIC`（Link Clicks） | Search / PMax（最大化点击） | Link Click |
| `conversions_purchase` | 转化（购买） | `OUTCOME_SALES` → Purchase | PMax / Search tROAS | Purchase |
| `add_to_cart` | 加购 | `OUTCOME_SALES` → Add to Cart | Search / PMax（加购优化） | AddToCart |

**`【规则】`** objective 只能取上表 5 个枚举值，**禁止自由文本**。用户口语描述（"想多卖点货"）由 LLM 映射到枚举，必须同时输出 `mapping_note` 写明映射理由，供用户当场否认。
**`【规则】`** `add_to_cart` 与 `conversions_purchase` 不得同时作为主优化事件；两个都要 → 主 `add_to_cart`，purchase 降级为观察指标，写进报告"何时停"。

`scratch/objective.json`：

```json
{
  "objective": "conversions_purchase",
  "mapping_note": "用户原话『想多卖货』→ purchase 为最终变现事件",
  "optimization_event": "Purchase",
  "attribution_window": "7d_click_1d_view",
  "bid_strategy": "tROAS",
  "primary_kpi": {"name":"ROAS","baseline_from":"task5_performance.json"},
  "secondary_kpi": [{"name":"CPA"},{"name":"CVR"}],
  "guardrails": {"cpa_ceiling": null, "non_brand_cpc_cap": null, "frequency_cap": 3}
}
```

`guardrails` 的空值**必须由 C5 真实数据回填**，拿不到记 GAP，不得臆造。

### 4.4 objective → 投放参数矩阵（S0 / S1 / S2 的硬约束）

| objective | 出价方式 | 归因窗口 | 测试期日预算粒度 | S1 创意重心 | 落地页要求 | 止损信号 |
|---|---|---|---|---|---|---|
| `leads` | 最低成本 / CPL 上限 | 7d click | CPL 目标 × 20–30 | 钩子＝利益交换（指南/报价/试用）；CTA＝Get / Claim | 表单页，字段 ≤3 | CPL > 目标 2× 连续 3 天 |
| `reach` | Reach 出价 + 频次上限 | 1d view | CPM × 目标覆盖人数 | 钩子＝记忆点；弱 CTA | 品牌页 / 品类页 | 频次 >3 且 CTR 持续下滑 |
| `outbound_clicks` | Link Clicks / 手动 CPC 封顶 | 1d click | CPC 目标 × 50 | 钩子＝好奇心缺口；CTA＝Learn more | 内容页 / 集合页 | CPC > 非品牌封顶 2× |
| `conversions_purchase` | tROAS / tCPA | 7d click + 1d view | CPA 目标 × 10–15 | 钩子＝结果证明 + 价格锚；CTA＝Shop now | PDP / 购物车 | CPA > 目标 1.5× 连续 5 天，或 ROAS < 盈亏线 |
| `add_to_cart` | AddToCart 优化 | 7d click | 加购成本 × 15 | 钩子＝场景代入 + 低门槛；CTA＝Add to cart | PDP | 加购→购买率 < 历史均值 60% |

### 4.5 ad_type × objective 交叉校验

| ↓ad_type ＼ objective→ | leads | reach | outbound_clicks | conversions_purchase | add_to_cart |
|---|---|---|---|---|---|
| `product` | ✅ | ✅ | ✅ | ✅ 主力 | ✅ |
| `promo` | ⚠️ 仅当活动本身为留资 / 抽奖 | ✅ 大促造势 | ✅ | ✅ 主力 | ✅ |
| `hybrid` | ⚠️ | ⚠️ 信息过载，不建议 | ✅ | ✅ 主力 | ✅ 主力 |

**`【规则】`** 落 ⚠️ 时 R1 必须复核一次并给出替代方案（例：`hybrid + reach` → 拆成 `promo/reach` 造势层 + `product/conversions_purchase` 收割层）。

### 4.6 路由结果如何改写 Crew A

`task_profile` 改变各采集 task 的开关与必答项，**不得三种 ad_type 跑同一套提示词**。

| Task | `product` | `promo` | `hybrid` |
|---|---|---|---|
| C0 | 全量剖析 | 降级：只解最小集（名称/价格/品类），范围以 `promo.eligible_scope` 为准；无产品 URL 时从活动页抽取并标 source | 全量剖析 |
| C1 | 痛点挖掘（原样） | 改跑**折扣敏感度 / 购买动机**，同样必须带证据，**不得跳过** | 痛点 + 折扣动机都跑 |
| C2 | 常规素材采集 | **必加"竞品同节点促销广告"过滤**，额外输出 `promo_creative[]` | 两者都采集 |
| C3 | 竞品 PDP 为主 | **活动页 / 促销规则页为主**，必提 `promo_rules[]`、`end_date`、`threshold`、`exclusions[]` | 双侧采集，且**必须交叉校验 PDP 与活动页价格/口径一致** |
| C4 | 产品词 | 活动词（`brand+code/sale`、节日词）+ 季节性峰值必答 | 合并两类词 |
| C5 | 按 campaign 拉效率 | **必须拉历史同期活动 campaign 的 ROAS / CPA 作为基线** | 全量 + 同期活动基线 |

### 4.7 实现约定

- 路由用 **纯 Python + 一个轻量 Crew**：`router.py` 负责 URL/文本判定、槽位完整性检查、`status` 判定（**零 LLM**）；`crews/router_crew.py` 的 R0 agent 只做「字段抽取与结构化」，R1 agent 只做「自然语言 → objective 枚举映射」。
- **R0 / R1 禁止输出策略建议、卖点判断、预算数字**，违反即视为串层。
- ad_type 与 objective 一旦写入 JSON，下游 Crew **只读不改**；下游若认为更优组合（例：推断出应先做 reach 造势），只能写入 `recommendations[]` 作为建议，**不得回改 JSON**。

---

## 5. 数据契约：scratch/*.json【规则】

路由层、采集层与推理层之间**只通过 JSON 通信**，不靠对话记忆。每个 JSON 必须含：
- `status`: `"ok"` / `"partial"` / `"failed"`
- `sources`: 数组，每项 `{tool, server, query, retrieved_at}`
- `facts` / `inferences` / `gaps` 三层分离（见 §9 数据纪律）

| 文件 | 产出 task | 关键字段 |
|---|---|---|
| `router.json` | **R0** | `ad_type`、`slots.{product,promo}.{mode,resolved,pending_confirm}`、`missing_slots[]`、`clarifications[]` |
| `objective.json` | **R1** | `objective`、`optimization_event`、`bid_strategy`、`attribution_window`、`primary_kpi`、`secondary_kpi[]`、`guardrails{}` |
| `task0_product.json` | C0 | `input_mode`(`url`/`brief`/`url+brief`)、`category`、`selling_points[]`、`specs{}`、`pending_confirm[]` |
| `task1_painpoints.json` | C1 | `pain_points[{text, evidence:{platform, brand, date, url}, severity, quote}]` |
| `task2_competitor_ads.json` | C2 | `ads[{brand, platform, creative_type, headline, body, cta, start_date, format}]` |
| `task3_landing_pages.json` | C3 | `pages[{brand, url, hero_headline, promo_rules[], cta_text[], price_anchoring}]` |
| `task4_demand_signals.json` | C4 | `trends[{term, values[], peak_week, seasonality_note}]`、`keywords[]` |
| `task5_performance.json` | C5 | `campaigns[{name, spend, cpa, roas, cpc, cvr, conversions}]`、`account_totals{}` |
| `task6_strategy.json` | S0 | `kano_map{}`、`fogg_decision{}`（主导路径 M/A/P）、`selling_point_map[]`（卖点↔痛点判定）、`budget{}`、`stop_loss{}` |
| `task7_creative.json` | S1 | `asset_matrix[]`（卖点 × 福格路径 × 版位）、`briefs[]`（每条含 `fogg.{motivation,ability,prompt}`、`copy{}`、`shot_list[]`、`delivery_spec{}`、`reference_prompts[]`、`acceptance_checklist[]`） |

---

## 6. 任务拓扑：Router Crew 打头 + 两个 Crew

### Crew R — 路由（确定性预处理 + 轻量抽取）

```
R0 广告类型路由（ad_type + 输入槽解析） → scratch/router.json
R1 广告目的选择（objective + KPI 口径） → scratch/objective.json
```

**`【规则】` R0/R1 串行且必须先完成**，任一 `status="failed"` 即终止整条链路，不进 Crew A。规格见 §4。

### Crew A — 采集（工具密集）

```
C0 产品剖析 ──┬── C1 用户评论与痛点      → task1_painpoints.json
              ├── C2 竞品广告素材        → task2_competitor_ads.json
              ├── C3 竞品落地页与CTA     → task3_landing_pages.json
              ├── C4 需求信号与搜索词    → task4_demand_signals.json
              └── C5 自有历史投放复盘    → task5_performance.json
```

**`【规则】` C1 与 C2 物理隔离**：互不可见，各自只接收 C0。理由：防止竞品信息污染痛点挖掘，及反向污染。此约束在旧项目三层落实过，改造必须保留。

| Task | 工具（MCP server → 原生工具名） | 提示词要点 |
|---|---|---|
| C0 | `playwright` 抓页；模式B 无工具 | 输入来源改为 `router.json.slots.product`（URL 模式抓页 / 人工模式以简报为准）；`ad_type=promo` 时按 §4.6 降级。缺失标【待确认】+ 附建议补充清单 |
| C1 | `tavily`(待接) 发现入口 → `playwright` 抓 Reddit/Amazon/Trustpilot | 每条痛点标 平台+品牌+时间。品牌型号未发布时严禁虚构本产品评价 |
| C2 | `facebook-ads-library`: `get_meta_platform_id`, `get_meta_ads`；`gads-transparency`: `search_advertiser`, `get_advertiser_ads` | 提取创意类型/文案/CTA/在投时长，不做评价 |
| C3 | `playwright` 抓竞品落地页 | 提 hero 标题、活动规则、CTA 原文、价格锚点 |
| C4 | `google-trends`: `compare_terms`, `interest_over_time`；`similarweb`；`google-ads` 搜索词报告 | 必须输出季节性峰值与谷底周，及相对主词的量级倍数 |
| C5 | `google-ads`: `customers_list_accessible_customers`, `search_search`；`meta-ads` | 按 campaign 拉 spend/CPA/ROAS/CPC/CVR，标出效率最优与最差 |

> 宿主侧直调时工具名带 `mcp__<server>__` 前缀；CrewAI 经 `MCPServerAdapter` 接入时为 MCP 原生名。**同一 server，两种叫法。**

### Crew B — 策略（纯推理，不调工具）

```
S0 策略合成  ← 读 task0..task5 全部        → task6_strategy.json
S1 素材Brief  ← 读 task0 + task6 + router + objective
                                            → task7_creative.json + output/creative_brief.md
S2 报告汇总  ← 读全部                      → output/strategy_report.md（创意章节指向 creative_brief.md）
```

| Task | 职责 |
|---|---|
| S0 | KANO 分类 + **福格模型决策（判定本轮主导路径是 M/A/P 中的哪一条并写明理由）**；模式B 强制输出卖点↔痛点映射表；**必须引用 C5 数据给出预算与止损建议** |
| S1 | **产出素材 Brief**（≥6 条：福格三要素 + 前3秒钩子 + 镜号表 + CTA 原文 + 交付规格 + 验收清单）；AI 图 Prompt 仅作 `reference_prompts` 参考图，非交付主体 |
| S2 | 汇总校验一致性，产出最终报告；核对素材 Brief 与策略/落地页/活动口径一致 |

---

## 7. Agent 定义

| Agent | 角色 | 所属 Crew | 工具 |
|---|---|---|---|
| **Agent R0** | 输入路由官 | R / R0 | playwright（抓产品/活动 URL） |
| **Agent R1** | 投放目标策略官 | R / R1 | 无 |
| Agent 1 | 资深用户洞察专家 | A / C1 | tavily, playwright |
| Agent 2 | 竞品情报分析师 | A / C2, C3 | facebook-ads-library, gads-transparency, playwright |
| Agent 3 | 增长数据分析师（**新增**） | A / C4, C5 | google-trends, similarweb, google-ads, meta-ads |
| Agent 4 | 首席广告策略官 | B / S0 | 无 |
| Agent 5 | 素材 Brief 主创（原"爆款内容创意总监"，人格原文不动） | B / S1 | 无（参考图只写在结论里，不调图像模型） |
| Agent 6 | 综合策略汇总官 | B / S2 | 无 |

**`【规则】` LLM 一律用 Arthur 提供的强模型。** `【事实】` `google-ads` 的 `search_search` 需手写 GAQL（字段名几十个、类 SQL）；`similarweb` 参数枚举多。弱模型写错概率高，且**写错表现为空结果不报错**（静默失败，最危险）。
**`【规则】`** 复杂工具在 `tools/` 下包一层，只给 LLM 暴露 2-3 个简单入参。

---

## 8. MCP 与凭证清单【事实】

| server | 凭证 env | 供的数据 | 状态 |
|---|---|---|---|
| `google-ads` | config path | 自有投放 / 搜索词 | ✅ 已验证 |
| `meta-ads` | token | 自有 Meta 投放 | ✅ 已验证 |
| `facebook-ads-library` | ScrapeCreators key | 竞品 FB 广告素材 | ✅ 已验证 |
| `gads-transparency` | 免凭证 | 竞品 Google 广告素材 | ✅ 已验证（FlexiSpot 0 条） |
| `google-trends` | 免凭证 | 需求信号 | ✅ 已验证 |
| `similarweb` | SSE URL | 竞品流量/渠道/搜索词 | ✅ 可用 |
| `playwright` | 免凭证 | 抓落地页/CTA/活动规则 | ✅ 可用 |
| `tavily` | `TAVILY_API_KEY` | **搜索入口发现** | ⚠️ 待接入 |

**`【事实】` 最大缺口：7 个已装 MCP 中无搜索类。** Reddit 长尾讨论、社媒帖子、FAQ 页面不是"抓"的问题，是**先要发现 URL 才能抓**。没有搜索 MCP，C1 是半瞎的。Tavily key 是补齐第一类数据的唯一阻塞项。

---

## 9. 硬约束（继承旧项目，不得丢弃）

### 9.0 路由层约束（新增，见 §4）
- ad_type / objective **只取枚举值**，`promo` / `hybrid` 的活动数字零容错，缺失即占位不估算。
- `router.json` / `objective.json` 下游只读，**不得回改**。

### 9.1 数据纪律：FACT / INFER / GAP 三层强制标注
- **FACT** — 工具返回 / 抓取原文 / 人工简报。必须附来源。
- **INFER** — 由事实推导。必须写推断依据链。
- **GAP** — 需要但拿不到。明确写"未获取"及原因。
- **严禁**用模型先验补全 FACT 层（价格、型号、认证、尺寸、竞品动态、用户评价）。

### 9.2 空数据 ≠ 好数据
工具返回 0 条时如实记为 GAP 并区分原因（"未投该渠道" vs "ID 用错"），**不得脑补填充**。

### 9.3 证据链不可断
下游引用上游结论时，证据标签一并传递，不得在传递中丢失。

### 9.4 双模式输入（已上移为路由层槽位取值方式）

两个槽（`product` / `promo`）各自独立二取一：**URL 模式**（工具抓取，入 FACT）／**人工模式**（用户输入为唯一事实源，入 FACT，缺失进 `pending_confirm`）。
两者的标注规则完全一致：前者附 URL 来源，后者附用户原始文本。
模式B 下 S0 强制输出映射表，判定三选一：
① 有需求证据 → 主推 ｜ ② 无对应痛点 → 需小预算测试 ｜ ③ 高发痛点无卖点 → 缺口/机会
**铁律：列为主推的卖点必须能追溯到一条带证据的痛点。**

### 9.5 业务闭环测试判准
无法映射到「投什么 / 怎么写 / 落哪里 / 花多少 / 何时停」的输出，视为无效，不得入报告。
反面案例：纯 KANO 表、纯 SWOT、纯 persona。

---

## 10. 输出规格（两个交付物）

| 交付物 | 读者 | 用途 |
|---|---|---|
| `output/strategy_report.md` | 投放负责人 / Arthur | 答五问：投什么 / 怎么写 / 落哪里 / 花多少 / 何时停 |
| **`output/creative_brief.md`** | **设计师 / 剪辑师** | **素材需求单，读完能直接开工；是创意层的主交付物** |

### 10.1 报告：五问判准

报告每章必须能回答五问，缺失即不通过。**报告开头必须先回显 `ad_type` 与 `objective`**（含 mapping_note），读者据此判断后续所有建议的语境。

| 问 | 必须包含 |
|---|---|
| 投什么 | 渠道 + 广告类型 + 受众/关键词层级 |
| 怎么写 | 钩子文案 / 卖点排序 / CTA 原文 + **指向 `output/creative_brief.md` 的具体 asset_id**（报告正文不再复述完整大段文案） |
| 落哪里 | 落地页 URL 或改造要求 |
| 花多少 | 预算分配比例 + 出价上限（非品牌 CPC 封顶） |
| 何时停 | **由 `objective` 决定的主 KPI**（CPL / CPM / CPC / ROAS / 加购成本）达标线与止损规则（含观察期天数），一律用 §4.4 矩阵，不得自选 |


**主 KPI 由 `objective.json` 决定**，不得自行挑选：

| objective | 报告主 KPI（第一行） | 辅助 KPI |
|---|---|---|
| `leads` | CPL | 留资率、有效线索率 |
| `reach` | CPM / 覆盖人数 | 频次、CTR |
| `outbound_clicks` | CPC | CTR、落地页浏览率 |
| `conversions_purchase` | ROAS | CPA、CVR |
| `add_to_cart` | 加购成本 | 加购→购买率、CPA |

**`【规则】` `promo` / `hybrid` 的报告必须额外包含**：活动名称、折扣口径、门槛、优惠码、起止日期、排除项、以及历史同期活动 campaign 的效率基线（取自 C5，缺失记 GAP）。

### 10.2 素材 Brief：创意层的主交付物

**`【规则】` 创意层产出的是「素材需求单」，不是 Prompt。** Brief 的读者是设计师 / 剪辑师，判准是：**读完不需要回头追问就能开工。**

- AI 图 Prompt **只允许出现在 Brief 的 `reference_prompts` 字段**，用途是给设计师看氛围感觉的参考图，**不是终稿、不可直接投放**。
- **禁止输出"只有 Prompt、没有 Brief"的结果**（视为 A11 不通过）。
- **禁止无解释的抽象词**：出现"高级感 / 有质感 / 有冲击力"必须紧跟可执行翻译（具体配色、材质、光位、镜头、剪辑节奏），否则该条不通过。
- 每条 Brief 独立成段、可单独派工，不得靠上下文才读得懂。

### 10.3 素材矩阵（先排产，再写 Brief）

矩阵先落 `task7_creative.json`，再展开成 Brief 文件：

| 排产维度 | 取值 |
|---|---|
| 卖点 | 主推卖点 ≥2 条（必须可追溯痛点）+ 待测试卖点 1 条（来自 S0 的 KANO 判定） |
| **福格主导路径** | **M 主导 / A 主导 / P 主导，各至少 1 条**（见 §10.5） |
| 版位格式 | 9:16（Reels / TikTok / Shorts）、1:1、4:5、1.91:1（PMax asset） |

最小交付量：**6 条 Brief**（3 条视频 + 3 套静态图）。`promo` / `hybrid` 必须至少 2 条带活动元素的素材。

### 10.4 单条素材 Brief 结构（模板见 `knowledge/creative_brief_template.md`）

每条逐项填齐，缺失写 `{待确认}`，**不得省略字段、不得合并字段**：

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

### 10.5 福格三要素填写口径（`B = MAP`）

| 要素 | 可选维度 | 填写要求 |
|---|---|---|
| **M 动机** | 愉悦/痛苦、希望/恐惧、认同/排斥 | 必须选一个维度，并引一条真实痛点原文作为 `evidence_ref`；不得凭空写"用户想要更好生活" |
| **A 能力** | 金钱、时间、体力、脑力、社会偏离、非常规 | 必须说明素材削减的是哪个成本，以及画面/文案如何体现（例：原价 vs 现价的价格对比 = 金钱；装机过程 3 秒快剪 = 体力） |
| **P 提示** | signal 信号（告知）/ facilitator 引导（降低门槛）/ spark 刺激（激发冲动） | 必须写明提示出现在素材的哪个时间点，并给出原文 |

**`【规则】` 主导路径决定素材结构**：S0 已在 `task6_strategy.json.fogg_decision` 判定本轮主导路径，S1 的素材矩阵必须**围绕主导路径倾斜排产**（主推路径占 ≥50% 素材量），其余两条作对照测试。

### 10.6 Brief 的三条硬判准

1. **可追溯** — `strategy.selling_point` 必须能追到 `task1_painpoints.json` 中一条带证据的痛点（继承 §9.4 铁律）；追不到的只能列为"测试素材"并显式标注，且不计入主推预算。
2. **可执行** — `visual_direction` 里每个形容词都能翻译成画面动作；抽象无解释即判不通过。
3. **可验收** — `acceptance_checklist` 全勾才算交付；`reference_prompts` 缺失仅记 GAP，不影响验收。

**`【规则】` 口径一致性**：`promo` / `hybrid` 素材中的活动名称、折扣数字、门槛、优惠码、截止日期，必须与 `router.json.slots.promo.resolved` **逐字一致**（活动数字零容错，§4.1）。

**规格化**：静态图对齐 PMax asset（1:1 / 1.91:1 / 4:5 + 字符上限），视频对齐 Reels / TikTok 9:16 + 前 3 秒钩子 + 静音可懂；交付文件需满足 `delivery_spec.files`。

---

## 11. 构建阶段（每阶段可验证后再进下一步）

| 阶段 | 内容 | 出口条件 |
|---|---|---|
| **P0** | 建项目骨架 + git init + `.env.example` + 迁移 agent/task 配置与 fixtures | 目录就位，`git log` 有基线 |
| **P1** | 装 `crewai-tools[mcp]`，**验证多 server 连接（A2）** | A2 明确通过或明确失败并定替代方案 |
| **P1.5** | **路由层**：`router.py` + `router_crew.py` + `agent_r0/r1.jsonc` + `schemas.py` 新增 `RouterInput` / `ObjectiveSpec` | 三种 ad_type 各跑一次，产出合法 `router.json`；五个 objective 各跑一次算出合法 `objective.json`（A8 通过） |
| **P2** | 写 `schemas.py` 剩余模型 + 采集 Crew 骨架 + 单 task（C0）跑通，C0 改读 `router.json` | C0 产出合法 JSON |
| **P3** | 补齐 C1–C5，逐个实跑验证真实返回 | 6 个 JSON 均含真实数据 |
| **P4** | 策略 Crew S0–S2，用 fixtures 离线跑通 | 报告产出且五问可答；**`creative_brief.md` ≥6 条 Brief，福格三要素与验收清单齐全（A11 通过）** |
| **P5** | 全链路真跑（HUANUO 63" Premium Topaz）+ 人工验收，须覆盖两种 ad_type × 两种 objective | A1–A10 全通过 |

---

## 12. 已知风险

1. **多 server 适配（A2）** — 未验证，可能导致 Crew 结构返工。**先做 P1。**
2. **静默失败** — GAQL / similarweb 参数写错返回空而不报错，下游基于空数据产出看似完整的报告。**靠 §9.2 与 A7 双重拦截。**
3. **反爬** — Trustpilot / Amazon 用 playwright 直抓易被拦，需评估是否值得。
4. **objective 误映射** — 用户口语（"多卖货"）可能被映射到错的优化事件，导致整个下游 KPI 与止损线全错。**靠 `mapping_note` 回显 + 用户当场否认机制拦截（A8）。**
5. **活动数字被模型脑补** — 折扣/截止日期一旦臆造，报告直接不可执行。**靠活动数字零容错 + `{…待确认}` 占位 + A10 拦截。**
6. **上下文膨胀** — S0 同时吃 6 个 JSON，需控制字段粒度，必要时先摘要。
7. **ad_type 一刀切** — 三种类型共用一套采集提示词会导致 `promo` 缺规则、`hybrid` 数据不全。**靠 §4.6 的 task_profile 开关表强制区分。**

---

## 13. 待 Arthur 拍板【待定】

0. **`promo` / `hybrid` 的默认 objective** — 是默认 `conversions_purchase`，还是必须逐次向用户确认？ 逐次确认
1. `TAVILY_API_KEY` — 补齐用户评论数据的唯一阻塞项
2. **HUANUO 主账号 Meta 广告库返回 0 条在投**（`100168622048562`）— 主动放弃 Meta 还是 ID 用错？另有 `Huanuoav` / `Huanuo-IN` 子账号待查 
3. 强模型接入方式（endpoint / key / CrewAI 中如何声明） 通过base url加上api key的方式接入
4. 是否保留旧项目 `run_direct_agent.py`（无工具，全靠先验）— 建议废弃 
不保留

---

## 14. 已验证的业务基线（供策略层参照）【事实】

2026-09-22 真实 MCP 采集，非模型推测：

1. **支架线严重低配** — CPC $0.82（全场最低）、CPA $45.4、ROAS 4.01（最高），预算仅占 1.8%
2. **新 feed 在崩** — `pmax-PD-深色&浅色-20260915新feed` ROAS 1.37、CPA $1,161、CVR 0.33%（同系列 1.27–1.39%）
3. **FSA/HSA 是现成空位** — UPLIFT 在投「Put your FSA or HSA funds to work… before your benefits reset」，FlexiSpot 与 HUANUO 均未用
4. **参数正面比必输** — FlexiSpot 355 lbs / UPLIFT 15 年质保 vs HUANUO 176 lbs / 5 年 → 改用稳定性叙事 + 美国本地发货售后
5. **季节性决定节奏** — `electric standing desk` 峰值 4/12–4/18（值 100），9 月仅 4（全年谷底）
6. **细分词不值得单独建 campaign** — `l-shaped` / `with drawers` / `with storage` 均值 2，主词 17，差 8 倍

---

_版本：MVP v1.2 · 2026-09-22 · v1.1 新增 §4 路由层，原 §4–§13 顺延为 §5–§14；v1.2 创意层主交付物改为素材 Brief（§10.2–10.6），AI 图 Prompt 降级为参考图 · 待 Arthur 审核_
