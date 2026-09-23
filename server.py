"""DTC 广告策略引擎 · Web 操作平台后端（FastAPI）。

启动：
    .venv/Scripts/python server.py              # 默认 http://127.0.0.1:8765
    .venv/Scripts/python server.py --port 9000

设计要点：
- 单工作线程串行执行流水线任务（scratch/ 是共享状态，禁止并行跑）；
- 前端为纯静态 SPA（web/），由本服务直接托管，无需 Node 构建链；
- /api/pre-route 调用零 LLM 的确定性路由（R0），供前端实时预览；
- 日志实时捕获：logging Handler + stdout/stderr 包装（按线程隔离）。
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from dtc_ad_strategy import mcp_config, paths, router as router_mod  # noqa: E402
from dtc_ad_strategy.schemas import OBJECTIVES  # noqa: E402

mcp_config.load_env()

# --------------------------------------------------------------------------
# 流水线元数据（阶段 / 文件 / 步骤的唯一事实源）
# --------------------------------------------------------------------------

SCRATCH_FILES: list[dict[str, str]] = [
    {"name": "router.json", "stage": "R", "label": "路由决策", "desc": "R0 槽位解析 + ad_type 判定"},
    {"name": "objective.json", "stage": "R", "label": "投放目标", "desc": "R1 objective 枚举映射 + KPI/护栏"},
    {"name": "task0_product.json", "stage": "A", "label": "产品解析", "desc": "C0 落地页/简报 → 产品事实"},
    {"name": "task1_painpoints.json", "stage": "A", "label": "痛点挖掘", "desc": "C1 评论/问答痛点"},
    {"name": "task2_competitor_ads.json", "stage": "A", "label": "竞品广告", "desc": "C2 竞品在投素材"},
    {"name": "task3_landing_pages.json", "stage": "A", "label": "落地页拆解", "desc": "C3 竞品落地页"},
    {"name": "task4_demand_signals.json", "stage": "A", "label": "需求信号", "desc": "C4 Trends/搜索趋势"},
    {"name": "task5_performance.json", "stage": "A", "label": "历史绩效", "desc": "C5 账户实绩基线"},
    {"name": "task6_strategy.json", "stage": "B", "label": "策略合成", "desc": "S0 Kano/Fogg/预算/止损"},
    {"name": "task7_creative.json", "stage": "B", "label": "素材矩阵", "desc": "S1 素材 Brief 载荷"},
]

OUTPUT_FILES: list[dict[str, str]] = [
    {"name": "strategy_report.md", "stage": "B", "label": "策略报告", "desc": "S2 汇总报告（Markdown）"},
    {"name": "creative_brief.md", "stage": "B", "label": "素材 Brief", "desc": "S1b 素材派工文档（Markdown）"},
]

COLLECTION_STEP_META: list[dict[str, str]] = [
    {"key": "product_analysis_task", "label": "产品解析 (C0)", "file": "task0_product.json"},
    {"key": "pain_points_task", "label": "痛点挖掘 (C1)", "file": "task1_painpoints.json"},
    {"key": "competitor_ads_task", "label": "竞品广告 (C2)", "file": "task2_competitor_ads.json"},
    {"key": "landing_pages_task", "label": "落地页拆解 (C3)", "file": "task3_landing_pages.json"},
    {"key": "demand_signals_task", "label": "需求信号 (C4)", "file": "task4_demand_signals.json"},
    {"key": "performance_task", "label": "历史绩效 (C5)", "file": "task5_performance.json"},
]

STRATEGY_STEP_META: list[dict[str, str]] = [
    {"key": "strategy_task", "label": "策略合成 (S0)", "file": "task6_strategy.json"},
    {"key": "creative_task", "label": "素材矩阵 (S1)", "file": "task7_creative.json"},
    {"key": "creative_brief_md_task", "label": "Brief 渲染 (S1b)", "file": "creative_brief.md"},
    {"key": "report_task", "label": "报告汇总 (S2)", "file": "strategy_report.md"},
]

COLLECTION_LABELS = {s["key"]: s["label"] for s in COLLECTION_STEP_META}
STRATEGY_LABELS = {s["key"]: s["label"] for s in STRATEGY_STEP_META}
KNOWN_SCRATCH = {f["name"] for f in SCRATCH_FILES}
KNOWN_OUTPUT = {f["name"] for f in OUTPUT_FILES}
STAGES = ("full", "router", "collection", "strategy")
STAGE_LABELS = {
    "full": "全链路 R → A → B",
    "router": "仅路由层 R",
    "collection": "仅采集层 A",
    "strategy": "仅策略层 B",
}
ENV_KEYS = [
    "MODEL",
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_MODEL_NAME",
    "REASONING_EFFORT",
    "GOOGLE_ADS_CONFIG_PATH",
    "META_ACCESS_TOKEN",
    "SCRAPECREATORS_API_KEY",
    "PYTHON_PATH",
    "SIMILARWEB_API_KEY",
    "TAVILY_API_KEY",
]

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# --------------------------------------------------------------------------
# 日志实时捕获（logging + stdout，按工作线程隔离）
# --------------------------------------------------------------------------

_tls = threading.local()


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _job_log(job: dict, text: str, kind: str = "info") -> None:
    line = ANSI_RE.sub("", text).rstrip()
    if not line:
        return
    with job["_lock"]:
        seq = job["log_seq"] = job["log_seq"] + 1
        job["logs"].append({"seq": seq, "t": _now(), "kind": kind, "text": line})


class _JobLogHandler(logging.Handler):
    """只捕获工作线程内产生的日志记录。"""

    def emit(self, record: logging.LogRecord) -> None:
        job = getattr(_tls, "job", None)
        if job is None:
            return
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            msg = record.getMessage  # type: ignore[assignment]
        if record.exc_info:
            msg = f"{msg}\n{traceback.format_exception(*record.exc_info)[-1].strip()}"
        kind = "error" if record.levelno >= logging.ERROR else "warn" if record.levelno >= logging.WARNING else "info"
        _job_log(job, f"[{record.levelname}] {msg}", kind)


class _TeeStream(io.TextIOBase):  # type: ignore[misc]
    """stdout/stderr 包装：工作线程内的输出实时进入任务日志（并透传终端）。"""

    def __init__(self, real: Any, kind: str) -> None:
        self._real = real
        self._kind = kind

    def write(self, s: Any) -> int:
        job = getattr(_tls, "job", None)
        if job is not None and s and s.strip():
            for line in str(s).splitlines():
                _job_log(job, line, self._kind)
        try:
            return self._real.write(s)
        except Exception:  # noqa: BLE001
            return len(s)

    def flush(self) -> None:
        try:
            self._real.flush()
        except Exception:  # noqa: BLE001
            pass

    def isatty(self) -> bool:
        try:
            return self._real.isatty()
        except Exception:  # noqa: BLE001
            return False

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return getattr(self._real, "encoding", "utf-8")

    def fileno(self) -> int:
        return self._real.fileno()


logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("crewai").setLevel(logging.INFO)
logging.getLogger("dtc_ad_strategy").setLevel(logging.INFO)
_h = _JobLogHandler()
_h.setLevel(logging.INFO)
logging.getLogger().addHandler(_h)

# --------------------------------------------------------------------------
# 任务管理器（单工作线程串行）
# --------------------------------------------------------------------------


def _new_job(stage: str, params: dict[str, Any], options: dict[str, Any], phases: list[dict]) -> dict:
    return {
        "id": f"job_{datetime.now().strftime('%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "started_at": None,
        "finished_at": None,
        "stage": stage,
        "stage_label": STAGE_LABELS[stage],
        "params": params,
        "options": options,
        "status": "queued",
        "cancel_requested": False,
        "phases": phases,
        "result": None,
        "error": None,
        "logs": [],
        "log_seq": 0,
        "_lock": threading.Lock(),
    }


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self._order: list[str] = []
        self._cv = threading.Condition()
        self._thread = threading.Thread(target=self._loop, name="dtc-job-worker", daemon=True)
        self._thread.start()

    # ---- 对外接口 ----
    def create(self, job: dict) -> dict:
        with self._cv:
            self.jobs[job["id"]] = job
            self._order.append(job["id"])
            self._cv.notify_all()
        return job

    def get(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        with self._cv:
            items = [self.jobs[j] for j in self._order]
        return [public_job(j) for j in reversed(items[-60:])]

    def running(self) -> dict | None:
        with self._cv:
            for jid in self._order:
                if self.jobs[jid]["status"] == "running":
                    return public_job(self.jobs[jid])
        return None

    def queued_count(self) -> int:
        with self._cv:
            return sum(1 for jid in self._order if self.jobs[jid]["status"] == "queued")

    def last_finished(self) -> dict | None:
        with self._cv:
            done = [self.jobs[j] for j in self._order if self.jobs[j]["status"] in ("done", "failed", "cancelled")]
        return public_job(done[-1]) if done else None

    def request_cancel(self, job_id: str) -> bool:
        with self._cv:
            job = self.jobs.get(job_id)
            if not job or job["status"] not in ("queued", "running"):
                return False
            job["cancel_requested"] = True
            return True

    # ---- 工作循环 ----
    def _loop(self) -> None:
        while True:
            with self._cv:
                job = None
                for jid in self._order:
                    if self.jobs[jid]["status"] == "queued":
                        job = self.jobs[jid]
                        break
                if job is None:
                    self._cv.wait(timeout=2)
                    continue
                job["status"] = "running"
                job["started_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            self._execute(job)

    def _execute(self, job: dict) -> None:
        _tls.job = job
        _job_log(job, f"任务启动：{job['stage_label']}（id={job['id']}）", "phase")
        params = {k: v for k, v in job["params"].items()}
        opts = job["options"]
        try:
            from dtc_ad_strategy.crew import DtcAdStrategyCrew
            from dtc_ad_strategy.schemas import RouterInput

            fields = RouterInput.model_fields
            inp = RouterInput(**{k: v for k, v in params.items() if k in fields})
            crew = DtcAdStrategyCrew(router_input=inp)
            results: dict[str, Any] = {}
            failed = False

            for ph in job["phases"]:
                if job["cancel_requested"]:
                    for p in job["phases"]:
                        if p["status"] == "pending":
                            p["status"] = "skipped"
                    job["status"] = "cancelled"
                    job["error"] = "用户取消：pending 阶段已跳过（进行中的单步会执行完再停）"
                    _job_log(job, "任务已取消", "warn")
                    break

                ph["status"] = "running"
                ph["started_at"] = _now()
                key = ph["key"]
                _job_log(job, f"━━ 阶段开始：{ph['label']} ━━", "phase")

                part: dict[str, Any] | None = None
                try:
                    if key == "route":
                        part = crew.route()
                    elif key == "collect_fixtures":
                        part = crew.collect(offline=True)
                    elif key.startswith("collect:"):
                        part = crew.collect(steps=[key.split(":", 1)[1]])
                    elif key.startswith("strategy:"):
                        part = crew.strategize(steps=[key.split(":", 1)[1]])
                except Exception as exc:  # noqa: BLE001
                    _job_log(job, traceback.format_exc(), "error")
                    ph["status"] = "failed"
                    job["status"] = "failed"
                    job["error"] = f"{ph['label']} 异常：{exc}"
                    failed = True
                    break

                results[key] = part
                if isinstance(part, dict) and part.get("status") == "failed":
                    ph["status"] = "failed"
                    job["status"] = "failed"
                    job["error"] = f"{ph['label']} 返回 failed，链路终止（§6 规则：任一环节 failed 即终止）"
                    _job_log(job, job["error"], "error")
                    for p in job["phases"]:
                        if p["status"] == "pending":
                            p["status"] = "skipped"
                    failed = True
                    break

                ph["status"] = "done"
                ph["finished_at"] = _now()
                _job_log(job, f"━━ 阶段完成：{ph['label']} ━━", "phase")

            if not failed and job["status"] == "running":
                job["status"] = "done"
                job["result"] = {"phases": results}
                if job["stage"] == "full":
                    job["result"]["outputs"] = {
                        "strategy_report": str(paths.OUTPUT / "strategy_report.md"),
                        "creative_brief": str(paths.OUTPUT / "creative_brief.md"),
                    }
                _job_log(job, "✔ 全部阶段完成", "phase")
        except Exception as exc:  # noqa: BLE001
            _job_log(job, traceback.format_exc(), "error")
            job["status"] = "failed"
            job["error"] = f"任务级异常：{exc}"
        finally:
            job["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            _tls.job = None


def public_job(job: dict, logs_after: int = -1) -> dict:
    """输出给前端的任务视图（剥离内部字段；logs_after=-1 表示不带日志）。"""
    with job["_lock"]:
        logs = job["logs"]
        total = job["log_seq"]
    view = {
        "id": job["id"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "stage": job["stage"],
        "stage_label": job["stage_label"],
        "params": job["params"],
        "options": job["options"],
        "status": job["status"],
        "cancel_requested": job["cancel_requested"],
        "phases": [dict(p) for p in job["phases"]],
        "result": job["result"],
        "error": job["error"],
        "log_total": total,
    }
    if logs_after >= 0:
        view["logs"] = [entry for entry in logs if entry["seq"] > logs_after]
    return view


jm = JobManager()

# --------------------------------------------------------------------------
# FastAPI 应用
# --------------------------------------------------------------------------

app = FastAPI(title="DTC 广告策略引擎 · 操作平台", version="1.0")


@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if any(path.endswith(ext) for ext in (".js", ".css", ".html")) or path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class PreRouteReq(BaseModel):
    product_url: str = ""
    product_text: str = ""
    promo_url: str = ""
    promo_text: str = ""
    goal_text: str = ""
    market: str = "US"


class JobCreateReq(BaseModel):
    stage: str = Field(default="full")
    params: PreRouteReq = Field(default_factory=PreRouteReq)
    options: dict[str, Any] = Field(default_factory=dict)


def _build_phases(stage: str, options: dict[str, Any]) -> list[dict]:
    phases: list[dict] = []
    if stage in ("full", "router"):
        phases.append({"key": "route", "label": "R · 路由层（R0 槽位 + R1 目标）", "status": "pending"})
    if stage in ("full", "collection"):
        if options.get("offline"):
            phases.append({"key": "collect_fixtures", "label": "A · 采集层（fixtures 离线载入）", "status": "pending"})
        elif not options.get("skip_collection"):
            steps = options.get("collection_steps") or [s["key"] for s in COLLECTION_STEP_META]
            for s in steps:
                phases.append({"key": f"collect:{s}", "label": f"A · {COLLECTION_LABELS.get(s, s)}", "status": "pending"})
    if stage in ("full", "strategy"):
        steps = options.get("strategy_steps") or [s["key"] for s in STRATEGY_STEP_META]
        for s in steps:
            phases.append({"key": f"strategy:{s}", "label": f"B · {STRATEGY_LABELS.get(s, s)}", "status": "pending"})
    return phases


PRESETS = [
    {
        "id": "huanuo_desk",
        "title": "HUANUO 63\" Premium Topaz (产品广告)",
        "tag": "product",
        "desc": "双电机 L 型升降桌，高载重与大桌面定位，已发布产品 URL 模式",
        "params": {
            "product_url": "https://www.huanuo.com/products/huanuo-63-inch-electric-standing-desk-topaz",
            "product_text": "HUANUO 63\" Premium Topaz L-Shaped Electric Standing Desk, dual motors, 176 lbs capacity, anti-collision sensor, memory presets, solid alloy steel frame, retail $1099.99.",
            "promo_url": "",
            "promo_text": "",
            "goal_text": "想提升转化多卖货，对齐核心客群",
            "market": "US",
        },
    },
    {
        "id": "black_friday_promo",
        "title": "黑五限时大促 20% OFF (活动广告)",
        "tag": "promo",
        "desc": "全场满减限时大促，零容错折扣活动，手工简报模式",
        "params": {
            "product_url": "",
            "product_text": "",
            "promo_url": "https://www.huanuo.com/promo/black-friday-2026",
            "promo_text": "黑五限时全场 20% OFF，优惠码 BF20，满 $300 起用，活动周期 11/20-11/30，售完即止",
            "goal_text": "黑五活动冲量，提升购买转化与 ROI",
            "market": "US",
        },
    },
    {
        "id": "hybrid_clearance",
        "title": "Topaz 升降桌秋季清仓组合 (混合广告)",
        "tag": "hybrid",
        "desc": "指定热销品 + 限时直降 $150 优惠券，同时具备产品特征与限时让利",
        "params": {
            "product_url": "https://www.huanuo.com/products/huanuo-63-inch-electric-standing-desk-topaz",
            "product_text": "HUANUO 63\" Topaz 电动升降桌，双电机高承重，静音升降",
            "promo_url": "",
            "promo_text": "秋季换新限时直降 $150，限量 500 台，code FALL150，截止 10/15",
            "goal_text": "兼顾品牌心智与当期购买转化，防守竞品流量",
            "market": "US",
        },
    },
]


# ---- 元数据 / 健康 ----


@app.get("/api/meta")
def get_meta() -> dict:
    return {
        "stages": [{"key": k, "label": v} for k, v in STAGE_LABELS.items()],
        "scratch_files": SCRATCH_FILES,
        "output_files": OUTPUT_FILES,
        "collection_steps": COLLECTION_STEP_META,
        "strategy_steps": STRATEGY_STEP_META,
        "objectives": list(OBJECTIVES),
        "presets": PRESETS,
    }


@app.get("/api/presets")
def get_presets() -> dict:
    return {"presets": PRESETS}



@app.get("/api/health")
def get_health() -> dict:
    try:
        import crewai  # noqa: F401

        crewai_ok = True
    except Exception:  # noqa: BLE001
        crewai_ok = False
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "model": (mcp_config.os.getenv("MODEL") or mcp_config.os.getenv("OPENAI_MODEL_NAME") or "gemini/gemini-2.5-flash（默认）"),
        "crewai_available": crewai_ok,
        "env": {k: bool(mcp_config.os.getenv(k)) for k in ENV_KEYS},
        "mcp": {
            "servers": mcp_config.available_servers(),
            "project_config_exists": paths.PROJECT_MCP.exists(),
        },
        "fixtures": sorted(p.name for p in paths.FIXTURES.glob("*.json")),
        "dirs": {"scratch": str(paths.SCRATCH), "output": str(paths.OUTPUT), "root": str(paths.ROOT)},
        "server_time": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# ---- 总览 ----


def _file_summary(name: str, payload: dict) -> str:
    if name == "router.json":
        return f"ad_type = {payload.get('ad_type', '—')}"
    if name == "objective.json":
        return f"objective = {payload.get('objective', '—')}"
    if name == "task0_product.json":
        pts = payload.get("selling_points") or []
        return f"{len(pts)} 条卖点 · {payload.get('category') or '品类待解析'}"
    if name == "task1_painpoints.json":
        return f"{len(payload.get('pain_points') or [])} 个痛点"
    if name == "task2_competitor_ads.json":
        ads = (payload.get("ads") or []) + (payload.get("promo_creative") or [])
        return f"{len(ads)} 条竞品素材"
    if name == "task3_landing_pages.json":
        return f"{len(payload.get('pages') or [])} 个落地页"
    if name == "task4_demand_signals.json":
        return f"{len(payload.get('trends') or [])} 组趋势 · {len(payload.get('keywords') or [])} 个关键词"
    if name == "task5_performance.json":
        return f"{len(payload.get('campaigns') or [])} 个 campaign"
    if name == "task6_strategy.json":
        return f"{len(payload.get('recommendations') or [])} 条建议"
    if name == "task7_creative.json":
        return f"{len(payload.get('briefs') or [])} 条素材 Brief"
    return ""


@app.get("/api/overview")
def get_overview() -> dict:
    files: list[dict] = []
    for meta in SCRATCH_FILES:
        p = paths.SCRATCH / meta["name"]
        item = {**meta, "exists": p.exists(), "status": "missing", "mtime": None, "size": 0, "summary": ""}
        if p.exists():
            st = p.stat()
            item["mtime"] = datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")
            item["size"] = st.st_size
            payload = router_mod.read_json(p)
            if payload:
                item["status"] = payload.get("status", "ok")
                item["summary"] = _file_summary(meta["name"], payload)
                item["counts"] = {
                    "sources": len(payload.get("sources") or []),
                    "facts": len(payload.get("facts") or []),
                    "inferences": len(payload.get("inferences") or []),
                    "gaps": len(payload.get("gaps") or []),
                }
            else:
                item["status"] = "failed"
                item["summary"] = "文件存在但 JSON 解析失败"
        files.append(item)

    outputs: list[dict] = []
    for meta in OUTPUT_FILES:
        p = paths.OUTPUT / meta["name"]
        item = {**meta, "exists": p.exists(), "mtime": None, "size": 0, "summary": ""}
        if p.exists():
            st = p.stat()
            item["mtime"] = datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds")
            item["size"] = st.st_size
            text = p.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if line.strip().startswith("#"):
                    item["summary"] = line.lstrip("# ").strip()
                    break
        outputs.append(item)

    return {
        "files": files,
        "outputs": outputs,
        "running": jm.running(),
        "queued": jm.queued_count(),
        "last_job": jm.last_finished(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# ---- 确定性预路由（零 LLM）----


@app.post("/api/pre-route")
def pre_route(req: PreRouteReq) -> dict:
    from dtc_ad_strategy.schemas import RouterInput

    inp = RouterInput(
        product_url=req.product_url.strip() or None,
        product_text=req.product_text.strip(),
        promo_url=req.promo_url.strip() or None,
        promo_text=req.promo_text.strip(),
        goal_text=req.goal_text.strip(),
        market=req.market.strip() or "US",
    )
    return router_mod.pre_route(inp)


# ---- 任务 ----


@app.post("/api/jobs", status_code=202)
def create_job(req: JobCreateReq) -> dict:
    if req.stage not in STAGES:
        raise HTTPException(400, f"stage 必须是 {'/'.join(STAGES)}")
    p = req.params
    if not any([p.product_url.strip(), p.product_text.strip(), p.promo_url.strip(), p.promo_text.strip()]):
        raise HTTPException(400, "至少填写一个产品/活动输入（URL 或文本），否则 R0 会直接判定 failed")

    opts = dict(req.options)
    valid_c = {s["key"] for s in COLLECTION_STEP_META}
    valid_s = {s["key"] for s in STRATEGY_STEP_META}
    cs = opts.get("collection_steps")
    if cs is not None:
        cs = [s for s in cs if s in valid_c]
        if not cs:
            raise HTTPException(400, "collection_steps 为空或全部非法")
        opts["collection_steps"] = cs
    ss = opts.get("strategy_steps")
    if ss is not None:
        ss = [s for s in ss if s in valid_s]
        if not ss:
            raise HTTPException(400, "strategy_steps 为空或全部非法")
        opts["strategy_steps"] = ss
    opts["offline"] = bool(opts.get("offline"))
    opts["skip_collection"] = bool(opts.get("skip_collection"))

    phases = _build_phases(req.stage, opts)
    if not phases:
        raise HTTPException(400, "当前选项组合下没有可执行的阶段（如 skip_collection + 仅采集层）")

    if jm.running() or jm.queued_count() > 0:
        note = "已有任务在跑，本任务已加入队列（scratch/ 共享，串行执行）"
    else:
        note = "立即执行"
    job = _new_job(
        req.stage,
        p.model_dump(),
        opts,
        phases,
    )
    jm.create(job)
    return {"id": job["id"], "note": note, "job": public_job(job)}


@app.get("/api/jobs")
def list_jobs() -> dict:
    return {"jobs": jm.list_jobs(), "running": jm.running(), "queued": jm.queued_count()}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, after: int = Query(default=-1)) -> dict:
    job = jm.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return public_job(job, logs_after=after)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    if not jm.request_cancel(job_id):
        raise HTTPException(400, "任务不存在或当前状态不可取消")
    return {"ok": True, "note": "取消请求已提交：pending 阶段将被跳过，进行中的单步执行完后停止"}


# ---- 文件（白名单访问）----


@app.get("/api/scratch/{name}")
def get_scratch(name: str) -> dict:
    if name not in KNOWN_SCRATCH or not NAME_RE.match(name):
        raise HTTPException(404, "未知的 scratch 文件")
    p = paths.SCRATCH / name
    if not p.exists():
        return {"name": name, "exists": False}
    st = p.stat()
    payload = router_mod.read_json(p)
    return {
        "name": name,
        "exists": True,
        "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
        "size": st.st_size,
        "data": payload if payload else {"status": "failed", "gaps": ["JSON 解析失败"]},
        "raw": p.read_text(encoding="utf-8", errors="replace"),
    }


class ScratchUpdateReq(BaseModel):
    data: dict[str, Any] | None = None
    raw: str | None = None


@app.put("/api/scratch/{name}")
def update_scratch(name: str, req: ScratchUpdateReq) -> dict:
    if name not in KNOWN_SCRATCH or not NAME_RE.match(name):
        raise HTTPException(404, "未知的 scratch 文件")
    p = paths.SCRATCH / name
    if req.data is not None:
        content = json.dumps(req.data, ensure_ascii=False, indent=2)
    elif req.raw is not None:
        try:
            parsed = json.loads(req.raw)
            content = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception as e:
            raise HTTPException(400, f"无效的 JSON 格式：{e}")
    else:
        raise HTTPException(400, "必须提供 data 或 raw 内容")
    p.write_text(content, encoding="utf-8")
    st = p.stat()
    return {
        "ok": True,
        "name": name,
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
        "note": "数据已成功保存",
    }


@app.delete("/api/scratch/{name}")
def delete_scratch(name: str) -> dict:
    if name not in KNOWN_SCRATCH:
        raise HTTPException(404, "未知的 scratch 文件")
    p = paths.SCRATCH / name
    deleted = p.exists()
    if deleted:
        p.unlink()
    return {"ok": True, "deleted": deleted}


@app.get("/api/output/{name}")
def get_output(name: str) -> dict:
    if name not in KNOWN_OUTPUT:
        raise HTTPException(404, "未知的 output 文件")
    p = paths.OUTPUT / name
    if not p.exists():
        return {"name": name, "exists": False, "content": ""}
    st = p.stat()
    return {
        "name": name,
        "exists": True,
        "mtime": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(timespec="seconds"),
        "size": st.st_size,
        "content": p.read_text(encoding="utf-8", errors="replace"),
    }


@app.get("/api/output/{name}/download")
def download_output(name: str):
    if name not in KNOWN_OUTPUT:
        raise HTTPException(404, "未知的 output 文件")
    p = paths.OUTPUT / name
    if not p.exists():
        raise HTTPException(404, "文件尚未生成")
    return FileResponse(p, filename=name, media_type="text/markdown")


# ---- 重置 ----


@app.post("/api/reset")
def reset(payload: dict[str, Any]) -> dict:
    scope = payload.get("scope", "scratch")
    deleted: list[str] = []
    if scope in ("scratch", "all"):
        for name in KNOWN_SCRATCH:
            p = paths.SCRATCH / name
            if p.exists():
                p.unlink()
                deleted.append(name)
    if scope in ("outputs", "all"):
        for name in KNOWN_OUTPUT:
            p = paths.OUTPUT / name
            if p.exists():
                p.unlink()
                deleted.append(name)
    return {"ok": True, "deleted": deleted}


# ---- 静态前端（最后挂载，避免吞掉 /api）----


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


web_dir = ROOT / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="DTC 广告策略引擎 · Web 操作平台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(mcp_config.os.getenv("DTC_WEB_PORT", "8765")))
    args = parser.parse_args()

    import uvicorn

    try:  # Windows GBK 控制台兼容
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    print(f"\n  DTC 广告策略引擎 · 操作平台")
    print(f"  -> http://{args.host}:{args.port}\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
