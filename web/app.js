/* ============================================================
 * DTC 广告策略引擎 · 操作平台 — 前端 SPA（无构建链，原生实现）
 * ============================================================ */
"use strict";

/* ---------------- 基础工具 ---------------- */

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(c));
  }
  return el;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `请求失败 ${res.status}`);
  return data;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtBytes(n) {
  if (!n) return "0 B";
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  return (n / 1048576).toFixed(1) + " MB";
}

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function relTime(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return Math.floor(diff / 60) + " 分钟前";
  if (diff < 86400) return Math.floor(diff / 3600) + " 小时前";
  return Math.floor(diff / 86400) + " 天前";
}

function elapsed(startIso, endIso) {
  if (!startIso) return "—";
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : Date.now();
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return s + "s";
  if (s < 3600) return Math.floor(s / 60) + "m" + (s % 60) + "s";
  return Math.floor(s / 3600) + "h" + Math.floor((s % 3600) / 60) + "m";
}

function highlightJson(obj) {
  const json = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  return esc(json).replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false)\b|\bnull\b|(-?\d+\.?\d*(?:[eE][+-]?\d+)?)/g,
    (m, str, colon, bool, num) => {
      if (str) return colon ? `<span class="j-key">${str}</span>${colon}` : `<span class="j-str">${str}</span>`;
      if (bool) return `<span class="j-bool">${bool}</span>`;
      if (num) return `<span class="j-num">${num}</span>`;
      return `<span class="j-null">null</span>`;
    }
  );
}

function copyText(text, tip = "已复制到剪贴板") {
  navigator.clipboard.writeText(text).then(
    () => toast(tip, "ok"),
    () => toast("复制失败", "err")
  );
}

/* ---------------- Toast / Modal ---------------- */

function toast(msg, kind = "") {
  const el = h("div", { class: `toast ${kind}` }, msg);
  $("#toasts").append(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity .3s";
    setTimeout(() => el.remove(), 320);
  }, 3200);
}

function confirmModal(title, body, okText = "确认", danger = false) {
  return new Promise((resolve) => {
    const mask = h("div", { class: "modal-mask" });
    const close = (val) => {
      mask.remove();
      resolve(val);
    };
    const modal = h(
      "div",
      { class: "modal" },
      h("h3", {}, title),
      h("p", {}, body),
      h(
        "div",
        { class: "modal-actions" },
        h("button", { class: "btn", onclick: () => close(false) }, "取消"),
        h("button", { class: `btn ${danger ? "btn-danger" : "btn-primary"}`, onclick: () => close(true) }, okText)
      )
    );
    mask.append(modal);
    mask.addEventListener("click", (e) => {
      if (e.target === mask) close(false);
    });
    $("#modal-root").append(mask);
  });
}

/* ---------------- 图标 ---------------- */

const I = {
  dash: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>`,
  run: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>`,
  jobs: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3h10l6 6v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h5"/></svg>`,
  data: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`,
  report: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 12l6-6"/><path d="M16 2l4 4-4 2-2-2z"/></svg>`,
  env: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a5 5 0 0 0-7 7l-4.2 4.1a2 2 0 0 0 0 2.8l.3.3a2 2 0 0 0 2.8 0l4.1-4.2a5 5 0 0 0 7-7l-3 3-3-3 3-3z"/></svg>`,
  arrow: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>`,
  chev: `<svg class="chev" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>`,
  doc: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8M16 17H8M10 9H8"/></svg>`,
  play: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>`,
  stop: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`,
  copy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  download: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>`,
  trash: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
  refresh: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36L21 8"/><path d="M21 3v5h-5"/></svg>`,
  empty: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M8 11h6"/></svg>`,
};

/* ---------------- 全局状态 ---------------- */

const State = {
  route: "dashboard",
  meta: null,
  health: null,
  overview: null,
  form: loadForm(),
  runDraft: null,          // {stage} 从总览跳转预选
  jobs: [],
  selectedJobId: null,
  jobDetail: null,
  jobLogOffset: 0,
  dataFile: "router.json",
  dataTab: "overview",
  reportTab: "strategy_report.md",
  preRoute: null,
  polling: null,
};

function loadForm() {
  const def = {
    product_url: "", product_text: "", promo_url: "", promo_text: "", goal_text: "",
    stage: "full", offline: false, skip_collection: false,
    collection_steps: [], strategy_steps: [],
  };
  try {
    return { ...def, ...JSON.parse(localStorage.getItem("dtc_form_v1") || "{}") };
  } catch {
    return def;
  }
}
function saveForm() {
  localStorage.setItem("dtc_form_v1", JSON.stringify(State.form));
}

/* ---------------- 导航 ---------------- */

const PAGES = {
  dashboard: { title: "总览", sub: "流水线状态 · 快捷操作", icon: I.dash },
  run: { title: "新建运行", sub: "填写输入 → 实时预路由 → 提交执行", icon: I.run },
  jobs: { title: "运行监控", sub: "任务队列 · 阶段进度 · 实时日志", icon: I.jobs },
  data: { title: "数据契约", sub: "scratch/*.json · facts / inferences / gaps", icon: I.data },
  report: { title: "策略报告", sub: "strategy_report.md · creative_brief.md", icon: I.report },
  env: { title: "环境状态", sub: "LLM · MCP · fixtures · 目录", icon: I.env },
};

function renderNav() {
  const nav = $("#nav");
  nav.innerHTML = "";
  for (const [key, page] of Object.entries(PAGES)) {
    const item = h(
      "div",
      { class: `nav-item ${State.route === key ? "active" : ""}`, onclick: () => go(key) },
      h("span", { html: page.icon }),
      page.title,
      key === "jobs" && State.overview?.running ? h("span", { class: "nav-badge" }) : null
    );
    nav.append(item);
  }
}

function go(route, params = {}) {
  State.route = route;
  Object.assign(State, params);
  location.hash = route;
  stopPolling();
  renderNav();
  renderView();
  startPolling();
}

/* ---------------- 视图骨架 ---------------- */

function renderView() {
  const page = PAGES[State.route];
  $("#page-title").textContent = page.title;
  $("#page-sub").textContent = page.sub;
  const actions = $("#topbar-actions");
  actions.innerHTML = "";

  if (State.route === "dashboard") {
    actions.append(
      h("button", { class: "btn", onclick: () => refreshAll(true) }, h("span", { html: I.refresh }), "刷新"),
      h("button", { class: "btn btn-primary", onclick: () => go("run", { runDraft: { stage: "full" } }) }, h("span", { html: I.play }), "新建运行")
    );
    viewDashboard();
  } else if (State.route === "run") {
    viewRun();
  } else if (State.route === "jobs") {
    if (State.overview?.running && !State.selectedJobId) State.selectedJobId = State.overview.running.id;
    viewJobs();
  } else if (State.route === "data") {
    viewData();
  } else if (State.route === "report") {
    viewReport();
  } else if (State.route === "env") {
    viewEnv();
  }
}

/* ============================================================
 * 页面：总览
 * ============================================================ */

const STAGE_INFO = {
  R: { name: "路由层 R", desc: "R0 确定性槽位解析 + R1 目标映射" },
  A: { name: "采集层 A", desc: "MCP 驱动的 6 步数据采集（C0–C5）" },
  B: { name: "策略层 B", desc: "策略合成 + 素材 Brief + 报告" },
};

function viewDashboard() {
  const view = $("#view");
  view.innerHTML = "";
  if (!State.overview) {
    view.append(h("div", { class: "empty-state" }, h("div", { html: I.empty }), h("div", { class: "es-title" }, "加载中…")));
    return;
  }
  const ov = State.overview;

  // 运行中提示条
  if (ov.running) {
    view.append(
      h(
        "div",
        { class: "run-strip" },
        h("span", { class: "badge running" }, "RUNNING"),
        h("div", { style: "flex:1" },
          h("div", { style: "font-weight:700" }, `${ov.running.stage_label}`),
          h("div", { style: "font-size:12px;color:var(--text-3)" }, `任务 ${ov.running.id} · 已运行 ${elapsed(ov.running.started_at)}`)
        ),
        ov.queued > 0 ? h("span", { class: "tag" }, `队列中 ${ov.queued}`) : null,
        h("button", { class: "btn", onclick: () => go("jobs", { selectedJobId: ov.running.id }) }, "查看监控")
      )
    );
  } else if (ov.last_job) {
    const j = ov.last_job;
    view.append(
      h(
        "div",
        { class: "run-strip", style: j.status === "failed" ? "border-color:rgba(248,113,113,.3);background:rgba(248,113,113,.06)" : "" },
        h("span", { class: `badge ${j.status}` }, j.status.toUpperCase()),
        h("div", { style: "flex:1" },
          h("div", { style: "font-weight:700" }, `上次任务：${j.stage_label} · ${relTime(j.finished_at || j.created_at)}`),
          h("div", { style: "font-size:12px;color:var(--text-3)" }, j.error ? j.error : "点击右侧查看日志与结果")
        ),
        h("button", { class: "btn", onclick: () => go("jobs", { selectedJobId: j.id }) }, "查看")
      )
    );
  }

  // 流水线三段
  const flow = h("div", { class: "pipeline-flow" });
  const stages = ["R", "A", "B"];
  stages.forEach((sg, i) => {
    const info = STAGE_INFO[sg];
    const files = ov.files.filter((f) => f.stage === sg);
    const doneCount = files.filter((f) => f.exists).length;
    const stageCard = h(
      "div",
      { class: `stage-card ${sg.toLowerCase()}` },
      h(
        "div",
        { class: "stage-head" },
        h("div", { class: "stage-name" }, h("span", { class: `stage-letter ${sg.toLowerCase()}` }, sg), info.name),
        h("span", { class: "tag" }, `${doneCount}/${files.length}`)
      ),
      h("div", { style: "font-size:11.5px;color:var(--text-3);margin-bottom:10px" }, info.desc),
      ...files.map((f) =>
        h(
          "div",
          {
            class: `file-chip ${f.exists ? "" : "missing"}`,
            onclick: f.exists ? () => go("data", { dataFile: f.name }) : undefined,
            title: f.exists ? `${f.summary || ""} · 点击查看` : f.desc,
          },
          h("span", { class: `chip-status st-${f.status}` }),
          h("span", { class: "chip-name" }, f.name),
          h("span", { class: "chip-label" }, f.label)
        )
      )
    );
    flow.append(stageCard);
    if (i < 2) flow.append(h("div", { class: "stage-arrow", html: I.arrow }));
  });
  view.append(flow);

  // 快捷操作
  view.append(
    h(
      "div",
      { class: "grid grid-3", style: "margin-bottom:4px" },
      quickCard("跑全链路", "R → A → B 一键串行（需 MCP 与 LLM 就绪）", "run", { stage: "full" }),
      quickCard("离线全链路", "R + fixtures 采集 + B（不调 MCP，验证策略层）", "run", { stage: "full", offline: true }),
      quickCard("仅策略层 B", "用现有 scratch/*.json 重跑 S0–S2", "run", { stage: "strategy" })
    )
  );

  // 输出交付物
  const oc = h("div", { class: "grid grid-2 output-cards" });
  for (const out of ov.outputs) {
    oc.append(
      h(
        "div",
        { class: "card output-card" },
        h("div", { class: "doc-icon", html: I.doc }),
        h("div", { class: "oc-body" },
          h("div", { class: "oc-title" }, out.label + (out.exists ? "" : "（未生成）")),
          h("div", { class: "oc-sub" }, out.exists ? `${out.summary || "—"} · ${fmtTime(out.mtime)} · ${fmtBytes(out.size)}` : out.desc)
        ),
        out.exists
          ? h("button", { class: "btn btn-sm", onclick: () => go("report", { reportTab: out.name }) }, "查看")
          : h("span", { class: "tag" }, "待生成")
      )
    );
  }
  view.append(h("div", { class: "card-title", style: "margin-top:22px" }, "交付物"), oc);
}

function quickCard(title, sub, route, draft) {
  return h(
    "div",
    {
      class: "card",
      style: "cursor:pointer;transition:border-color .15s",
      onclick: () => go(route, { runDraft: draft }),
      onmouseenter: (e) => (e.currentTarget.style.borderColor = "rgba(99,102,241,.4)"),
      onmouseleave: (e) => (e.currentTarget.style.borderColor = ""),
    },
    h("div", { style: "font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px" }, h("span", { html: I.play, style: "color:var(--accent-2);display:inline-flex" }), title),
    h("div", { style: "font-size:12px;color:var(--text-3);margin-top:6px;line-height:1.6" }, sub)
  );
}

/* ============================================================
 * 页面：新建运行
 * ============================================================ */

function viewRun() {
  const view = $("#view");
  view.innerHTML = "";
  if (State.runDraft) {
    State.form.stage = State.runDraft.stage;
    if (State.runDraft.offline !== undefined) State.form.offline = State.runDraft.offline;
    State.runDraft = null;
  }
  const f = State.form;

  const left = h("div", { class: "card" }, h("div", { class: "card-title" }, "输入"));

  const mkField = (key, label, placeholder, hint, textarea, mono) => {
    const input = textarea
      ? h("textarea", { class: `textarea ${mono ? "mono" : ""}`, placeholder, oninput: (e) => { f[key] = e.target.value; saveForm(); schedulePreRoute(); } }, f[key] || "")
      : h("input", { class: `input ${mono ? "mono" : ""}`, placeholder: placeholder, value: f[key] || "", oninput: (e) => { f[key] = e.target.value; saveForm(); schedulePreRoute(); } });
    return h("div", { class: "field" }, h("label", {}, label), input, hint ? h("div", { class: "hint" }, hint) : null);
  };

  left.append(
    mkField("product_url", "产品落地页 URL", "https://www.example.com/products/xxx", "product 槽 URL 模式：交给 R0 + Playwright 解析", false, true),
    mkField("product_text", "产品简报（人工模式）", "例：HUANUO 63\u201d Premium Topaz L 型升降桌，双电机，售价 $1099.99", "没有 URL 时可手填；也可与 URL 同时提供（url+brief）", true),
    h("hr", { class: "divider" }),
    mkField("promo_url", "活动页 / EDM URL", "https://www.example.com/promo/black-friday", "promo 槽 URL 模式；与产品信息同时提供 → hybrid", false, true),
    mkField("promo_text", "活动内容（手填）", "例：黑五全场 20% OFF，code BF20，11/20–11/30", "包含折扣/限时/节日信号即被识别为 promo", true),
    h("hr", { class: "divider" }),
    mkField("goal_text", "投放目的（口语描述）", "例：想多卖货 / 加购 / 收线索 / 打声量", "R1 会把口语映射到 objective 枚举（leads/reach/outbound_clicks/conversions_purchase/add_to_cart）", true)
  );

  // 高级选项
  const advBody = h("div", { class: "collapsible-body" });
  const advHead = h("div", { class: "collapsible-head", onclick: () => { advHead.classList.toggle("open"); advBody.classList.toggle("open"); } }, "高级选项", h("span", { html: I.chev }));

  const stageSelect = h(
    "select",
    {
      class: "select",
      onchange: (e) => { f.stage = e.target.value; saveForm(); renderRunOptions(); },
    },
    ...State.meta.stages.map((s) => h("option", { value: s.key, selected: f.stage === s.key ? "" : null }, s.label))
  );

  const offlineSw = switchRow("offline", "离线模式（fixtures 跑策略层，不调 MCP）", f.offline, (v) => { f.offline = v; saveForm(); renderRunOptions(); });
  const skipSw = switchRow("skip_collection", "跳过采集层（直接用已有 scratch/*.json）", f.skip_collection, (v) => { f.skip_collection = v; saveForm(); renderRunOptions(); });

  const stepArea = h("div", { id: "step-area" });
  advBody.append(
    h("div", { class: "field" }, h("label", {}, "执行范围"), stageSelect),
    offlineSw,
    h("div", { style: "height:10px" }),
    skipSw,
    stepArea
  );
  left.append(advHead, advBody);

  const submitBtn = h(
    "button",
    {
      class: "btn btn-primary",
      style: "width:100%;justify-content:center;padding:12px;font-size:14px;margin-top:16px",
      onclick: submitJob,
    },
    h("span", { html: I.play }),
    "提交执行"
  );
  left.append(submitBtn);

  const right = h(
    "div",
    { class: "card preview-panel" },
    h("div", { class: "card-title" }, "实时预路由（R0 · 零 LLM · 输入即算）"),
    h("div", { id: "pre-route-body" })
  );

  view.append(h("div", { class: "run-layout" }, left, right));
  renderRunOptions();
  renderPreRoute();
}

function switchRow(key, label, val, onChange) {
  return h(
    "label",
    { class: "switch" },
    h("input", { type: "checkbox", checked: val ? "" : null, onchange: (e) => onChange(e.target.checked) }),
    h("span", { class: "track" }),
    h("span", { class: "switch-label" }, label)
  );
}

function renderRunOptions() {
  const f = State.form;
  const area = $("#step-area");
  if (!area) return;
  area.innerHTML = "";
  const showA = (f.stage === "collection" || f.stage === "full") && !f.offline && !f.skip_collection;
  const showB = f.stage === "strategy" || f.stage === "full";

  if (showA) {
    area.append(h("div", { class: "field", style: "margin-top:16px" },
      h("label", {}, "采集步骤（A 层 · 可多选）"),
      h("div", { class: "step-picker" },
        ...State.meta.collection_steps.map((s) => {
          const on = !f.collection_steps.length || f.collection_steps.includes(s.key);
          return h("div", {
            class: `step-chip ${on ? "on" : ""}`,
            onclick: () => {
              if (!f.collection_steps.length) f.collection_steps = State.meta.collection_steps.map((x) => x.key);
              const i = f.collection_steps.indexOf(s.key);
              if (i >= 0) f.collection_steps.splice(i, 1); else f.collection_steps.push(s.key);
              saveForm(); renderRunOptions();
            },
          }, h("span", { class: "dot" }), s.label);
        })
      ),
      h("div", { class: "hint" }, "默认全选；空选 = 全部执行")
    ));
  }
  if (showB) {
    area.append(h("div", { class: "field", style: "margin-top:16px" },
      h("label", {}, "策略步骤（B 层 · 可多选）"),
      h("div", { class: "step-picker" },
        ...State.meta.strategy_steps.map((s) => {
          const on = !f.strategy_steps.length || f.strategy_steps.includes(s.key);
          return h("div", {
            class: `step-chip ${on ? "on" : ""}`,
            onclick: () => {
              if (!f.strategy_steps.length) f.strategy_steps = State.meta.strategy_steps.map((x) => x.key);
              const i = f.strategy_steps.indexOf(s.key);
              if (i >= 0) f.strategy_steps.splice(i, 1); else f.strategy_steps.push(s.key);
              saveForm(); renderRunOptions();
            },
          }, h("span", { class: "dot" }), s.label);
        })
      ),
      h("div", { class: "hint" }, "默认全选；空选 = 全部执行")
    ));
  }
  if (!showA && !showB) {
    area.append(h("div", { class: "hint", style: "margin-top:12px" }, "当前范围无可选步骤"));
  }
}

let preRouteTimer = null;
function schedulePreRoute() {
  clearTimeout(preRouteTimer);
  preRouteTimer = setTimeout(renderPreRoute, 500);
}

async function renderPreRoute() {
  const box = $("#pre-route-body");
  if (!box) return;
  const f = State.form;
  if (!anyInput(f)) {
    box.innerHTML = "";
    box.append(
      h("div", { class: "empty-state", style: "padding:34px 10px" },
        h("div", { html: I.empty }),
        h("div", { class: "es-title" }, "等待输入"),
        h("div", { class: "es-sub" }, "填写任意产品/活动输入后，这里实时显示 R0 确定性路由结果：ad_type 判定、槽位状态与澄清清单")
      )
    );
    return;
  }
  try {
    const r = await api("/api/pre-route", {
      method: "POST",
      body: {
        product_url: f.product_url, product_text: f.product_text,
        promo_url: f.promo_url, promo_text: f.promo_text, goal_text: f.goal_text,
      },
    });
    State.preRoute = r;
    box.innerHTML = "";
    box.append(
      h("div", { class: "adtype-hero" },
        h("span", { class: `adtype-badge ${r.ad_type}` }, r.ad_type.toUpperCase()),
        h("div", { style: "flex:1;min-width:0" },
          h("div", {}, h("span", { class: `badge ${r.status}` }, r.status)),
          h("div", { style: "font-size:12px;color:var(--text-3);margin-top:6px" }, `task_profile = ${r.task_profile}`)
        )
      ),
      h("div", { class: "preview-note" }, r.decision_note || ""),
      h("div", { class: "slot-summary" },
        slotBox("product 槽", r.slots?.product),
        slotBox("promo 槽", r.slots?.promo)
      ),
      r.missing_slots?.length ? h("div", { class: "clar-item", style: "margin-top:10px" }, h("span", { class: "clar-q" }, "MISSING"), `缺失槽位：${r.missing_slots.join("、")}`) : null,
      r.clarifications?.length
        ? h("div", {},
            h("div", { class: "card-title", style: "margin:14px 0 0" }, `澄清清单（${r.clarifications.length}）`),
            h("div", { class: "clar-list" },
              ...r.clarifications.map((c) => h("div", { class: "clar-item" }, h("span", { class: "clar-q" }, "?"), h("span", {}, `[${c.slot}.${c.field}] `, c.question)))
            )
          )
        : null
    );
  } catch (e) {
    box.innerHTML = "";
    box.append(h("div", { class: "item-card", style: "border-color:rgba(248,113,113,.3)" }, `预路由失败：${esc(e.message)}`));
  }
}

function slotBox(title, slot) {
  const mode = slot?.mode || "none";
  const val =
    mode === "url" ? (slot.urls || []).join(", ") :
    mode === "manual" ? (slot.raw_text || "").slice(0, 60) : "未提供";
  return h("div", { class: "slot-box" },
    h("div", { class: "slot-title" }, title, h("span", { class: "slot-mode" }, mode)),
    h("div", { class: "slot-val", title: val }, val || "—")
  );
}

function anyInput(f) {
  return !!(f.product_url?.trim() || f.product_text?.trim() || f.promo_url?.trim() || f.promo_text?.trim());
}

async function submitJob() {
  const f = State.form;
  if (!anyInput(f)) return toast("至少填写一个产品/活动输入", "err");
  const opts = { offline: f.offline, skip_collection: f.skip_collection };
  if (f.collection_steps.length) opts.collection_steps = f.collection_steps;
  if (f.strategy_steps.length) opts.strategy_steps = f.strategy_steps;
  try {
    const res = await api("/api/jobs", {
      method: "POST",
      body: {
        stage: f.stage,
        params: {
          product_url: f.product_url, product_text: f.product_text,
          promo_url: f.promo_url, promo_text: f.promo_text, goal_text: f.goal_text,
        },
        options: opts,
      },
    });
    toast(`任务已提交（${res.note}）`, "ok");
    go("jobs", { selectedJobId: res.id, jobLogOffset: 0 });
  } catch (e) {
    toast(e.message, "err");
  }
}

/* ============================================================
 * 页面：运行监控
 * ============================================================ */

async function viewJobs() {
  const view = $("#view");
  view.innerHTML = "";
  if (!State.jobs.length) {
    view.append(h("div", { class: "empty-state" },
      h("div", { html: I.empty }),
      h("div", { class: "es-title" }, "暂无任务"),
      h("div", { class: "es-sub" }, "去「新建运行」提交第一个流水线任务", h("br"), "R → A → B 全链路或按阶段执行，这里实时展示阶段进度与日志"),
      h("button", { class: "btn btn-primary", style: "margin-top:16px", onclick: () => go("run") }, "新建运行")
    ));
    return;
  }

  const layout = h("div", { class: "jobs-layout" });
  const side = h("div", { class: "card side-list", id: "jobs-side" });
  const main = h("div", { id: "job-detail" });
  layout.append(side, main);
  view.append(layout);
  renderJobsSide();
  renderJobDetail();
}

function renderJobsSide() {
  const side = $("#jobs-side");
  if (!side) return;
  side.innerHTML = "";
  side.append(h("div", { class: "card-title" }, `任务（${State.jobs.length}）`));
  for (const j of State.jobs) {
    side.append(h(
      "div",
      { class: `job-item ${State.selectedJobId === j.id ? "active" : ""}`, onclick: () => { State.selectedJobId = j.id; State.jobLogOffset = 0; renderJobsSide(); renderJobDetail(); } },
      h("div", { class: "ji-top" }, h("span", { class: "ji-id" }, j.id), h("span", { class: `badge ${j.status}` }, j.status)),
      h("div", { class: "ji-stage" }, j.stage_label),
      h("div", { class: "ji-time" }, `${fmtTime(j.created_at).slice(5)} · ${elapsed(j.started_at, j.finished_at)}`)
    ));
  }
}

async function renderJobDetail() {
  const main = $("#job-detail");
  if (!main) return;
  if (!State.selectedJobId) {
    main.innerHTML = "";
    main.append(h("div", { class: "card" }, h("div", { class: "empty-state", style: "padding:40px" }, h("div", { class: "es-title" }, "选择左侧任务查看详情"))));
    return;
  }
  try {
    const j = await api(`/api/jobs/${State.selectedJobId}?after=${State.jobLogOffset}`);
    State.jobDetail = j;
    main.innerHTML = "";

    const head = h("div", { class: "card", style: "margin-bottom:16px" },
      h("div", { style: "display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap" },
        h("div", {},
          h("div", { style: "display:flex;align-items:center;gap:10px" },
            h("span", { class: `badge ${j.status}` }, j.status.toUpperCase()),
            h("b", { style: "font-size:15px" }, j.stage_label),
            h("span", { class: "ji-id", style: "font-family:var(--mono);font-size:12px;color:var(--text-3)" }, j.id)
          ),
          h("div", { class: "job-meta", style: "margin-top:10px" },
            h("span", { class: "tag" }, `创建 ${fmtTime(j.created_at)}`),
            j.started_at ? h("span", { class: "tag" }, `耗时 ${elapsed(j.started_at, j.finished_at)}`) : null,
            j.options?.offline ? h("span", { class: "tag tag-accent" }, "offline") : null,
            j.options?.skip_collection ? h("span", { class: "tag tag-accent" }, "skip_collection") : null
          )
        ),
        h("div", { style: "display:flex;gap:8px" },
          j.status === "running" || j.status === "queued"
            ? h("button", { class: "btn btn-danger btn-sm", onclick: () => cancelJob(j.id) }, h("span", { html: I.stop }), "取消")
            : null,
          h("button", { class: "btn btn-sm", onclick: () => rerunJob(j) }, h("span", { html: I.play }), "重跑")
        )
      ),
      j.error ? h("div", { class: "item-card", style: "margin-top:12px;border-color:rgba(248,113,113,.35);color:var(--err)" }, esc(j.error)) : null,
      h("div", { class: "phase-steps" },
        ...j.phases.map((p) => h("div", { class: `phase-step ${p.status}` },
          h("span", { class: "ps-icon" }, p.status === "done" ? "✓" : p.status === "failed" ? "✕" : p.status === "running" ? "●" : p.status === "skipped" ? "–" : String(j.phases.indexOf(p) + 1)),
          h("span", { class: "ps-label" }, p.label)
        ))
      )
    );
    main.append(head);

    main.append(
      h("div", { class: "card", style: "padding:16px" },
        h("div", { style: "display:flex;align-items:center;justify-content:space-between;margin-bottom:10px" },
          h("div", { class: "card-title", style: "margin:0" }, `实时日志（${j.log_total}）`),
          h("button", { class: "btn btn-ghost btn-sm", onclick: () => { const c = $("#log-console"); if (c) c.scrollTop = c.scrollHeight; } }, "滚到底部")
        ),
        h("div", { class: "log-console", id: "log-console" })
      )
    );

    if (j.result) {
      main.append(h("div", { class: "result-block" },
        h("div", { class: "card-title" }, "执行结果"),
        h("div", { class: "json-view", style: "max-height:340px", html: highlightJson(j.result) })
      ));
    }
    appendLogs(j.logs || []);
  } catch (e) {
    main.innerHTML = "";
    main.append(h("div", { class: "card" }, `加载失败：${esc(e.message)}`));
  }
}

function appendLogs(logs) {
  const con = $("#log-console");
  if (!con) return;
  for (const l of logs) {
    con.append(h("div", { class: `log-line ${l.kind}` }, h("span", { class: "log-t" }, l.t), h("span", { class: "log-x" }, l.text)));
  }
  const nearBottom = con.scrollHeight - con.scrollTop - con.clientHeight < 120;
  if (nearBottom || logs.length < 5) con.scrollTop = con.scrollHeight;
}

async function pollLogs() {
  if (State.route !== "jobs" || !State.selectedJobId) return;
  const con = $("#log-console");
  if (!con) return;
  try {
    const j = await api(`/api/jobs/${State.selectedJobId}?after=${State.jobLogOffset}`);
    State.jobDetail = j;
    State.jobLogOffset = j.log_total;
    appendLogs(j.logs || []);
    // 阶段状态可能变化 → 局部刷新头部的 phase steps 与状态徽章
    const badge = $("#job-detail .badge");
    const changed = badge && badge.textContent.toLowerCase() !== j.status;
    if (changed || (j.logs || []).some((l) => l.kind === "phase")) {
      renderJobDetail();
    } else {
      // 更新运行中任务的耗时标签
      const tags = $$("#job-detail .tag");
      for (const t of tags) if (t.textContent.includes("耗时")) t.textContent = `耗时 ${elapsed(j.started_at, j.finished_at)}`;
    }
    if (["done", "failed", "cancelled"].includes(j.status)) {
      await refreshJobsList();
    }
  } catch { /* 忽略瞬时错误 */ }
}

async function refreshJobsList() {
  try {
    const res = await api("/api/jobs");
    State.jobs = res.jobs;
    renderJobsSide();
  } catch { /* ignore */ }
}

async function cancelJob(id) {
  const ok = await confirmModal("取消任务", "pending 阶段将被跳过；正在执行的单步（如 LLM 调用）会在完成后停止。确认取消？", "确认取消", true);
  if (!ok) return;
  try {
    await api(`/api/jobs/${id}/cancel`, { method: "POST" });
    toast("取消请求已提交", "ok");
  } catch (e) {
    toast(e.message, "err");
  }
}

function rerunJob(j) {
  const p = j.params || {};
  State.form.product_url = p.product_url || "";
  State.form.product_text = p.product_text || "";
  State.form.promo_url = p.promo_url || "";
  State.form.promo_text = p.promo_text || "";
  State.form.goal_text = p.goal_text || "";
  State.form.stage = j.stage;
  State.form.offline = !!j.options?.offline;
  State.form.skip_collection = !!j.options?.skip_collection;
  saveForm();
  go("run");
}

/* ============================================================
 * 页面：数据契约
 * ============================================================ */

async function viewData() {
  const view = $("#view");
  view.innerHTML = "";
  const layout = h("div", { class: "data-layout" });
  layout.append(h("div", { class: "card side-list", id: "data-side" }), h("div", { id: "data-detail", style: "min-height:300px" }));
  view.append(layout);
  renderDataSide();
  renderDataDetail();
}

function renderDataSide() {
  const side = $("#data-side");
  if (!side) return;
  side.innerHTML = "";
  side.append(
    h("div", { class: "card-title" }, "scratch 文件"),
  );
  const groups = { R: [], A: [], B: [] };
  for (const f of State.overview?.files || []) groups[f.stage]?.push(f);
  for (const [sg, files] of Object.entries(groups)) {
    side.append(h("div", { class: "side-group" },
      h("div", { class: "side-group-title" }, h("span", { class: `stage-letter ${sg.toLowerCase()}`, style: "width:16px;height:16px;font-size:9.5px" }, sg), STAGE_INFO[sg].name),
      ...files.map((f) => h("div", {
        class: `datafile-item ${State.dataFile === f.name ? "active" : ""} ${f.exists ? "" : "missing"}`,
        onclick: () => { State.dataFile = f.name; State.dataTab = "overview"; renderDataSide(); renderDataDetail(); },
      },
        h("span", { class: `chip-status st-${f.status}` }),
        h("span", { class: "df-name" }, f.name),
        h("span", { class: "df-label" }, f.label)
      ))
    ));
  }
  side.append(
    h("hr", { class: "divider" }),
    h("button", {
      class: "btn btn-danger btn-sm",
      style: "width:100%;justify-content:center",
      onclick: async () => {
        const ok = await confirmModal("清空 scratch", "将删除 scratch/ 下全部流水线中间产物（10 个 JSON）。output/ 报告不受影响。确认清空？", "清空", true);
        if (!ok) return;
        const res = await api("/api/reset", { method: "POST", body: { scope: "scratch" } });
        toast(`已删除 ${res.deleted.length} 个文件`, "ok");
        refreshAll(true);
      },
    }, h("span", { html: I.trash }), "清空 scratch")
  );
}

async function renderDataDetail() {
  const main = $("#data-detail");
  if (!main) return;
  main.innerHTML = "";
  const meta = (State.meta?.scratch_files || []).find((f) => f.name === State.dataFile);
  main.append(h("div", { class: "card", style: "text-align:center;padding:50px" }, "加载中…"));
  try {
    const res = await api(`/api/scratch/${State.dataFile}`);
    main.innerHTML = "";
    if (!res.exists) {
      main.append(emptyData(meta));
      return;
    }
    renderDataFile(main, res, meta);
  } catch (e) {
    main.innerHTML = "";
    main.append(h("div", { class: "card" }, `加载失败：${esc(e.message)}`));
  }
}

function emptyData(meta) {
  return h("div", { class: "card" },
    h("div", { class: "empty-state" },
      h("div", { html: I.empty }),
      h("div", { class: "es-title" }, meta?.name || State.dataFile),
      h("div", { class: "es-sub" }, `尚未生成 · ${meta?.desc || ""}`, h("br"), "去「新建运行」执行对应阶段后自动落盘"),
      h("button", { class: "btn btn-primary", style: "margin-top:16px", onclick: () => go("run") }, "新建运行")
    )
  );
}

function renderDataFile(main, res, meta) {
  const d = res.data || {};
  const counts = {
    sources: (d.sources || []).length,
    facts: (d.facts || []).length,
    inferences: (d.inferences || []).length,
    gaps: (d.gaps || []).length,
  };

  main.append(
    h("div", { class: "detail-head" },
      h("div", {},
        h("h2", {}, h("span", { class: `badge ${d.status || "missing"}` }, (d.status || "—").toUpperCase()), res.name),
        h("div", { class: "dh-meta" }, `${meta?.label || ""} · ${meta?.desc || ""} · 更新于 ${fmtTime(res.mtime)} · ${fmtBytes(res.size)}`)
      ),
      h("div", { class: "dh-actions" },
        h("button", { class: "btn btn-sm", onclick: () => copyText(res.raw, "JSON 已复制") }, h("span", { html: I.copy }), "复制"),
        h("button", {
          class: "btn btn-danger btn-sm",
          onclick: async () => {
            const ok = await confirmModal("删除文件", `确认删除 ${res.name}？下游阶段将失去该上游数据。`, "删除", true);
            if (!ok) return;
            await api(`/api/scratch/${res.name}`, { method: "DELETE" });
            toast("已删除", "ok");
            refreshAll(true).then(() => { renderDataSide(); renderDataDetail(); });
          },
        }, h("span", { html: I.trash }), "删除")
      )
    )
  );

  const tabs = h("div", { class: "tabs" },
    tabEl("overview", "契约概览"),
    tabEl("payload", "业务载荷"),
    tabEl("raw", "原始 JSON"),
  );
  main.append(tabs);
  const body = h("div", { id: "data-file-body" });
  main.append(body);

  if (State.dataTab === "raw") {
    body.append(h("div", { class: "json-view", html: highlightJson(res.raw) }));
  } else if (State.dataTab === "payload") {
    body.append(renderPayload(State.dataFile, d));
  } else {
    body.append(
      h("div", { class: "contract-grid" },
        ccell(counts.sources, "sources 数据来源", "c-sources"),
        ccell(counts.facts, "facts 事实", "c-facts"),
        ccell(counts.inferences, "inferences 推断", "c-inferences")
      ),
      h("div", { class: "grid grid-2" },
        sectionBlock("GAPS 待补缺口", counts.gaps, d.gaps, true),
        sectionBlock("SOURCES 数据来源", counts.sources, (d.sources || []).map(srcTableItem), false)
      ),
      h("div", { class: "grid grid-2" },
        sectionBlock("FACTS 事实", counts.facts, d.facts),
        sectionBlock("INFERENCES 推断", counts.inferences, d.inferences)
      )
    );
  }
}

function tabEl(key, label) {
  return h("div", { class: `tab ${State.dataTab === key ? "active" : ""}`, onclick: () => { State.dataTab = key; renderDataDetail(); } }, label);
}

function ccell(num, label, cls) {
  return h("div", { class: `contract-cell ${cls}` }, h("div", { class: "cc-num" }, num), h("div", { class: "cc-label" }, label));
}

function sectionBlock(title, count, items, warn) {
  const list = [items || []].flat().slice(0, 30);
  return h("div", { class: "section-block" },
    h("div", { class: "sb-title", style: warn && count ? "color:var(--warn)" : "" }, title, h("span", { class: "count-tag" }, count)),
    count
      ? h("div", {}, ...list.map((it) =>
          h("div", { class: "item-card" }, typeof it === "string" ? it : h("div", { class: "mini-json", html: highlightJson(it) }))
        ))
      : h("div", { class: "item-card", style: "opacity:.6;text-align:center" }, "（空）")
  );
}

function srcTableItem(s) {
  return `${s.tool || "?"}${s.server ? ` @ ${s.server}` : ""} · ${s.query || ""}${s.retrieved_at ? ` · ${s.retrieved_at}` : ""}`;
}

/* ---- 业务载荷：按文件类型定制渲染 ---- */

function renderPayload(name, d) {
  const wrap = h("div", {});
  const add = (el) => wrap.append(el);
  const item = (txt) => h("div", { class: "item-card" }, txt);
  const jsonCard = (title, obj) => {
    if (obj == null) return null;
    return h("div", { class: "section-block" },
      h("div", { class: "sb-title" }, title),
      h("div", { class: "mini-json", style: "max-height:280px", html: highlightJson(obj) })
    );
  };

  if (name === "router.json") {
    add(h("div", { class: "adtype-hero", style: "margin-bottom:16px" },
      h("span", { class: `adtype-badge ${d.ad_type || "product"}` }, (d.ad_type || "?").toUpperCase()),
      h("div", { style: "flex:1" },
        h("div", { class: "preview-note" }, d.decision_note || ""),
        d.missing_slots?.length ? h("div", { style: "color:var(--warn);font-size:12px;margin-top:6px" }, `缺失槽位：${d.missing_slots.join("、")}`) : null
      )
    ));
    for (const [slotName, slot] of Object.entries(d.slots || {})) {
      if (!slot) continue;
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `槽位 ${slotName}（mode=${slot.mode}）`),
        slot.urls?.length ? item("URLs：" + slot.urls.join("、")) : null,
        slot.raw_text ? item("原文：" + slot.raw_text) : null,
        Object.keys(slot.resolved || {}).length ? jsonCard("resolved（已解析字段）", slot.resolved) : null,
        slot.pending_confirm?.length ? h("div", { class: "item-card", style: "border-color:rgba(251,191,36,.3)" }, "待确认字段：" + slot.pending_confirm.join("、")) : null
      ));
    }
    if (d.clarifications?.length) {
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `澄清清单（${d.clarifications.length}）`),
        ...d.clarifications.map((c) => h("div", { class: "item-card" }, h("b", { style: "color:var(--warn)" }, `? ${c.slot}.${c.field}`), " — ", c.question))
      ));
    }
    return wrap;
  }

  if (name === "objective.json") {
    add(h("div", { class: "adtype-hero", style: "margin-bottom:16px" },
      h("span", { class: "adtype-badge product" }, (d.objective || "?").toUpperCase()),
      h("div", { style: "flex:1" },
        h("div", { class: "preview-note" }, d.mapping_note || ""),
        d.cross_check_note ? h("div", { style: "color:var(--warn);font-size:12px;margin-top:6px" }, d.cross_check_note) : null
      )
    ));
    add(tbl("投放参数", [
      ["优化事件", d.optimization_event], ["归因窗口", d.attribution_window], ["出价策略", d.bid_strategy],
      ["主 KPI", d.primary_kpi?.name], ["次 KPI", (d.secondary_kpi || []).map((k) => k.name).join("、")],
      ["CPA 上限", d.guardrails?.cpa_ceiling ?? "待回填"], ["非品牌 CPC 上限", d.guardrails?.non_brand_cpc_cap ?? "待回填"], ["频次上限", d.guardrails?.frequency_cap ?? "待回填"],
    ]));
    return wrap;
  }

  if (name === "task0_product.json") {
    add(h("div", { class: "section-block" },
      h("div", { class: "sb-title" }, "基本信息"),
      item(`品类：${d.category || "—"}`),
      d.selling_points?.length ? h("div", { class: "item-card" }, "卖点：", ...d.selling_points.map((s, i) => h("span", { class: "tag tag-accent", style: "margin:2px 4px 2px 0;display:inline-block" }, `${i + 1}. ${s}`))) : null,
    ));
    add(jsonCard("specs", d.specs));
    if (d.pending_confirm?.length) add(h("div", { class: "item-card", style: "border-color:rgba(251,191,36,.3)" }, "待确认：" + d.pending_confirm.join("、")));
    return wrap;
  }

  if (name === "task1_painpoints.json") {
    for (const p of d.pain_points || []) {
      add(h("div", { class: "item-card" },
        h("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:5px" },
          h("span", { class: "tag tag-accent" }, p.id || "?"),
          p.severity ? h("span", { class: "tag" }, p.severity) : null
        ),
        h("div", { style: "color:var(--text)" }, p.text || ""),
        p.quote ? h("div", { style: "font-size:12px;color:var(--text-3);margin-top:5px;font-style:italic" }, `"${p.quote}"`) : null
      ));
    }
    return wrap;
  }

  if (name === "task2_competitor_ads.json") {
    const mkTable = (title, ads) => {
      if (!ads?.length) return null;
      return h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `${title}（${ads.length}）`),
        h("div", { class: "tbl-wrap" }, h("table", { class: "tbl" },
          h("tr", {}, h("th", {}, "品牌"), h("th", {}, "平台"), h("th", {}, "形式"), h("th", {}, "标题"), h("th", {}, "CTA"), h("th", {}, "投放起始")),
          ...ads.map((a) => h("tr", {}, h("td", { style: "color:var(--text);font-weight:600" }, a.brand || "—"), h("td", {}, a.platform || "—"), h("td", {}, a.format || a.creative_type || "—"), h("td", {}, a.headline || "—"), h("td", {}, a.cta || "—"), h("td", { class: "num" }, a.start_date || "—")))
        ))
      );
    };
    add(mkTable("常规广告", d.ads));
    add(mkTable("促销广告", d.promo_creative));
    return wrap;
  }

  if (name === "task3_landing_pages.json") {
    for (const p of d.pages || []) {
      add(h("div", { class: "item-card" },
        h("div", { style: "display:flex;justify-content:space-between;gap:8px;align-items:center" },
          h("b", { style: "color:var(--text)" }, p.brand || "?"),
          p.url ? h("a", { href: p.url, target: "_blank", style: "font-size:11.5px;color:#93c5fd;font-family:var(--mono)" }, p.url) : null
        ),
        p.hero_headline ? h("div", { style: "margin-top:6px" }, h("i", {}, `"${p.hero_headline}"`)) : null,
        p.price_anchoring ? h("div", { style: "font-size:12px;color:var(--text-3);margin-top:4px" }, `价格锚点：${p.price_anchoring}`) : null,
        (p.cta_text || []).length ? h("div", { style: "margin-top:6px" }, ...p.cta_text.map((c) => h("span", { class: "tag", style: "margin-right:4px" }, c))) : null,
      ));
    }
    return wrap;
  }

  if (name === "task4_demand_signals.json") {
    if (d.trends?.length) {
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `趋势（${d.trends.length}）`),
        ...d.trends.map((t) => h("div", { class: "item-card" },
          h("b", { style: "color:var(--text);font-family:var(--mono)" }, t.term || "?"),
          t.seasonality_note ? h("div", { style: "font-size:12.5px;margin-top:3px" }, t.seasonality_note) : null,
          t.values?.length ? h("div", { class: "mini-json" }, `values: ${JSON.stringify(t.values.slice(0, 30))}…`) : null
        ))
      ));
    }
    if (d.keywords?.length) {
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `关键词（${d.keywords.length}）`),
        h("div", { class: "tbl-wrap" }, h("table", { class: "tbl" },
          h("tr", {}, h("th", {}, "关键词"), h("th", {}, "数据")),
          ...d.keywords.slice(0, 40).map((k) => h("tr", {},
            h("td", { style: "font-family:var(--mono)" }, k.keyword || k.term || JSON.stringify(k).slice(0, 40)),
            h("td", { class: "num" }, JSON.stringify(Object.entries(k).filter(([key]) => key !== "keyword" && key !== "term").slice(0, 4)))
          ))
        ))
      ));
    }
    return wrap;
  }

  if (name === "task5_performance.json") {
    if (d.campaigns?.length) {
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `Campaigns（${d.campaigns.length}）`),
        h("div", { class: "tbl-wrap" }, h("table", { class: "tbl" },
          h("tr", {}, h("th", {}, "名称"), h("th", {}, "Spend"), h("th", {}, "CPA"), h("th", {}, "ROAS"), h("th", {}, "CPC"), h("th", {}, "CVR"), h("th", {}, "转化")),
          ...d.campaigns.map((c) => h("tr", {}, h("td", { style: "color:var(--text)" }, c.name || "—"), h("td", { class: "num" }, c.spend ?? "—"), h("td", { class: "num" }, c.cpa ?? "—"), h("td", { class: "num" }, c.roas ?? "—"), h("td", { class: "num" }, c.cpc ?? "—"), h("td", { class: "num" }, c.cvr ?? "—"), h("td", { class: "num" }, c.conversions ?? "—")))
        ))
      ));
    }
    add(jsonCard("account_totals", d.account_totals));
    add(jsonCard("promo_baseline", d.promo_baseline));
    return wrap;
  }

  if (name === "task6_strategy.json") {
    if (d.recommendations?.length) {
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, `策略建议（${d.recommendations.length}）`),
        ...d.recommendations.map((r, i) => h("div", { class: "item-card" }, h("b", { style: "color:var(--accent-2)" }, `${i + 1}. `), r))
      ));
    }
    if (d.selling_point_map?.length) {
      add(h("div", { class: "section-block" },
        h("div", { class: "sb-title" }, "卖点 × 痛点判定"),
        ...d.selling_point_map.map((m) => h("div", { class: "item-card" },
          h("span", {
            class: "badge-plain",
            style: {
              主推: "background:var(--ok-soft);color:var(--ok)",
              需小预算测试: "background:var(--warn-soft);color:var(--warn)",
              缺口机会: "background:var(--accent-soft);color:#a5b4fc",
            }[m.verdict] || "background:var(--panel-3);color:var(--text-2)",
          }, m.verdict || "?"),
          h("b", { style: "margin:0 8px;color:var(--text)" }, m.selling_point || "?"),
          m.pain_point_text ? h("span", { style: "font-size:12px" }, `↔ ${m.pain_point_text}`) : null
        ))
      ));
    }
    add(jsonCard("budget 预算", d.budget));
    add(jsonCard("stop_loss 止损", d.stop_loss));
    add(jsonCard("kano_map", d.kano_map));
    add(jsonCard("fogg_decision", d.fogg_decision));
    return wrap;
  }

  if (name === "task7_creative.json") {
    for (const b of d.briefs || []) {
      add(h("div", { class: "item-card" },
        h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px" },
          h("span", { class: "tag tag-accent", style: "font-family:var(--mono)" }, b.asset_id || "?"),
          b.placement ? h("span", { class: "tag" }, b.placement) : null,
          b.format ? h("span", { class: "tag" }, b.format) : null,
          b.objective ? h("span", { class: "tag" }, b.objective) : null,
        ),
        b.copy ? h("div", { class: "mini-json", html: highlightJson(b.copy) }) : null,
      ));
    }
    if (d.asset_matrix?.length) add(jsonCard("asset_matrix", d.asset_matrix));
    return wrap;
  }

  // 兜底：展示全部非契约字段
  const rest = { ...d };
  for (const k of ["status", "sources", "facts", "inferences", "gaps"]) delete rest[k];
  add(jsonCard("载荷", rest));
  return wrap;
}

function tbl(title, rows) {
  return h("div", { class: "section-block" },
    h("div", { class: "sb-title" }, title),
    h("div", { class: "tbl-wrap" }, h("table", { class: "tbl" },
      ...rows.map(([k, v]) => h("tr", {}, h("th", { style: "width:180px;white-space:nowrap" }, k), h("td", {}, v == null || v === "" ? "—" : String(v))))
    ))
  );
}

/* ============================================================
 * 页面：报告
 * ============================================================ */

async function viewReport() {
  const view = $("#view");
  view.innerHTML = "";
  const tabs = h("div", { class: "report-tabs" });
  for (const out of State.meta?.output_files || []) {
    tabs.append(h("button", {
      class: `btn btn-sm ${State.reportTab === out.name ? "btn-primary" : ""}`,
      onclick: () => { State.reportTab = out.name; viewReport(); },
    }, out.label, State.reportTab === out.name ? h("span", { class: "tag", style: "background:rgba(255,255,255,.15);border:none;color:#fff;margin-left:6px" }, "当前") : null));
  }
  view.append(tabs);

  const wrap = h("div", { id: "report-body" });
  view.append(wrap);
  wrap.append(h("div", { class: "card", style: "text-align:center;padding:60px" }, "加载中…"));

  try {
    const res = await api(`/api/output/${State.reportTab}`);
    wrap.innerHTML = "";
    if (!res.exists) {
      wrap.append(h("div", { class: "card" },
        h("div", { class: "empty-state" },
          h("div", { html: I.doc }),
          h("div", { class: "es-title" }, res.name + " 尚未生成"),
          h("div", { class: "es-sub" }, "跑完 B 层（S1b / S2）后自动落盘到 output/", h("br"), "可先跑「离线全链路」用 fixtures 数据快速产出"),
          h("button", { class: "btn btn-primary", style: "margin-top:16px", onclick: () => go("run", { runDraft: { stage: "full", offline: true } }) }, "跑离线全链路")
        )
      ));
      return;
    }
    const md = res.content || "";
    wrap.append(
      h("div", { class: "md-meta" },
        h("span", {}, `${fmtBytes(res.size)} · 更新于 ${fmtTime(res.mtime)}`),
        h("button", { class: "btn btn-sm", onclick: () => copyText(md, "Markdown 已复制") }, h("span", { html: I.copy }), "复制全文"),
        h("a", { class: "btn btn-sm", href: `/api/output/${res.name}/download`, style: "text-decoration:none" }, h("span", { html: I.download }), "下载 .md")
      )
    );
    let htmlText;
    if (window.marked) {
      marked.setOptions({ gfm: true, breaks: true });
      htmlText = marked.parse(md);
    } else {
      htmlText = `<pre style="white-space:pre-wrap">${esc(md)}</pre>`;
    }
    wrap.append(h("div", { class: "md-body", html: htmlText }));
  } catch (e) {
    wrap.innerHTML = "";
    wrap.append(h("div", { class: "card" }, `加载失败：${esc(e.message)}`));
  }
}

/* ============================================================
 * 页面：环境状态
 * ============================================================ */

function viewEnv() {
  const view = $("#view");
  view.innerHTML = "";
  const e = State.health;
  if (!e) {
    view.append(h("div", { class: "card" }, "加载中…"));
    return;
  }

  const envDesc = {
    MODEL: "LLM 模型名（crewai 强模型）",
    OPENAI_API_KEY: "LLM API Key",
    OPENAI_API_BASE: "中转/自建端点",
    OPENAI_MODEL_NAME: "备用模型名",
    REASONING_EFFORT: "推理深度 low/medium/high",
    GOOGLE_ADS_CONFIG_PATH: "google-ads 凭证路径",
    META_ACCESS_TOKEN: "meta-ads 凭证",
    SCRAPECREATORS_API_KEY: "facebook-ads-library 凭证",
    PYTHON_PATH: "fb 库依赖的 Python",
    SIMILARWEB_API_KEY: "similarweb 凭证",
    TAVILY_API_KEY: "评论发现（待接入）",
  };

  view.append(
    h("div", { class: "env-grid" },
      h("div", { class: "card" },
        h("div", { class: "card-title" }, "运行时"),
        h("table", { class: "kv-table" },
          kvRow("Python", e.python),
          kvRow("CrewAI", e.crewai_available ? h("span", { style: "color:var(--ok)" }, "已安装") : h("span", { style: "color:var(--err)" }, "未安装")),
          kvRow("LLM 模型", h("code", { style: "font-family:var(--mono);font-size:12px;color:#f0abfc" }, e.model)),
          kvRow("服务时间", fmtTime(e.server_time)),
        )
      ),
      h("div", { class: "card" },
        h("div", { class: "card-title" }, "MCP Server"),
        e.mcp.servers.length
          ? h("div", { style: "display:flex;flex-wrap:wrap;gap:8px" }, ...e.mcp.servers.map((s) => h("span", { class: "tag tag-accent", style: "font-family:var(--mono)" }, s)))
          : h("div", { class: "item-card", style: "color:var(--err)" }, "无可用 MCP server（检查 .codebuddy/mcp.json）")
      )
    ),
    h("div", { class: "card", style: "margin-top:16px" },
      h("div", { class: "card-title" }, "环境变量（.env）"),
      h("div", { class: "tbl-wrap" },
        h("table", { class: "tbl" },
          h("tr", {}, h("th", {}, "变量"), h("th", {}, "说明"), h("th", { style: "text-align:right" }, "状态")),
          ...ENV_ORDER.map((k) => h("tr", {},
            h("td", { class: "num", style: "font-family:var(--mono);color:var(--text)" }, k),
            h("td", {}, envDesc[k] || ""),
            h("td", { style: "text-align:right" }, e.env[k] ? h("span", { style: "color:var(--ok)" }, "● 已配置") : h("span", { style: "color:var(--text-3)" }, "○ 未配置"))
          ))
        )
      )
    ),
    h("div", { class: "grid grid-2", style: "margin-top:16px" },
      h("div", { class: "card" },
        h("div", { class: "card-title" }, `Fixtures（${e.fixtures.length}）`),
        e.fixtures.length ? h("div", {}, ...e.fixtures.map((f) => h("div", { class: "item-card", style: "font-family:var(--mono);font-size:12px" }, f))) : h("div", { class: "item-card", style: "opacity:.6" }, "无 fixtures")
      ),
      h("div", { class: "card" },
        h("div", { class: "card-title" }, "目录"),
        h("table", { class: "kv-table" },
          kvRow("scratch", h("span", { style: "font-family:var(--mono);font-size:11.5px" }, e.dirs.scratch)),
          kvRow("output", h("span", { style: "font-family:var(--mono);font-size:11.5px" }, e.dirs.output)),
        )
      )
    )
  );
}

const ENV_ORDER = ["MODEL", "OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_MODEL_NAME", "REASONING_EFFORT", "GOOGLE_ADS_CONFIG_PATH", "META_ACCESS_TOKEN", "SCRAPECREATORS_API_KEY", "PYTHON_PATH", "SIMILARWEB_API_KEY", "TAVILY_API_KEY"];

function kvRow(k, v) {
  return h("tr", {}, h("td", { class: "k" }, k), h("td", { class: "v" }, v));
}

/* ============================================================
 * 轮询与初始化
 * ============================================================ */

function stopPolling() {
  clearInterval(State.polling);
  State.polling = null;
}

function startPolling() {
  stopPolling();
  let tick = 0;
  State.polling = setInterval(async () => {
    tick++;
    try {
      // 任务页：日志流
      if (State.route === "jobs" && State.selectedJobId) {
        await pollLogs();
        if (tick % 5 === 0) await refreshJobsList();
      }
      // 任务运行中：总览自动刷新
      const needOverview =
        State.route === "dashboard" ||
        (State.overview && State.overview.running) ||
        (State.route === "data" && tick % 10 === 0);
      if (needOverview && tick % 3 === 0) {
        await refreshAll(false);
        if (State.route === "dashboard") viewDashboard();
        if (State.route === "data") renderDataSide();
      }
    } catch { /* 单次轮询失败忽略 */ }
  }, 1000);
}

async function refreshAll(rerender) {
  const [meta, health, overview, jobs] = await Promise.all([
    State.meta ? Promise.resolve(State.meta) : api("/api/meta"),
    api("/api/health"),
    api("/api/overview"),
    api("/api/jobs"),
  ]);
  State.meta = meta;
  State.health = health;
  State.overview = overview;
  State.jobs = jobs.jobs;

  const dot = $("#health-dot");
  const text = $("#health-text");
  if (dot && text) {
    dot.className = "health-dot on";
    text.textContent = `服务正常 · ${health.python}`;
  }
  if (rerender) renderView();
}

async function init() {
  if (location.hash.length > 1) {
    const r = location.hash.slice(1);
    if (PAGES[r]) State.route = r;
  }
  window.addEventListener("hashchange", () => {
    const r = location.hash.slice(1);
    if (PAGES[r] && r !== State.route) go(r);
  });
  renderNav();
  try {
    await refreshAll(false);
    renderNav();
    renderView();
    startPolling();
  } catch (e) {
    $("#view").append(h("div", { class: "card", style: "color:var(--err)" }, `后端连接失败：${esc(e.message)}`));
    const dot = $("#health-dot");
    if (dot) dot.className = "health-dot off";
    const text = $("#health-text");
    if (text) text.textContent = "服务不可用";
  }
}

init();
