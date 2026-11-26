"""FastAPI MVP 入口：交房缺陷与整改协同。

启动：
    python -m uvicorn app.main:app --reload --port 8000

五要素：FastAPI / Harness / 知识库 / 权限分层 / 在线部署。
边界：只读试点，所有建议需人工确认，不写回真实业务系统（f05/f15/f32/f40）。
"""
from __future__ import annotations

import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from src.audit import build_audit  # noqa: E402
from src.locator import load_parts, locate  # noqa: E402
from src.main import load_defects  # noqa: E402
from src.models import Defect, Handover, Reverify, WorkOrder  # noqa: E402
from src.rules import dedupe_by_master, detect_red_lines, handover_complete  # noqa: E402

from .auth import PERMISSIONS, ROLE_LABELS, User, auth_store  # noqa: E402
from .harness import run_harness  # noqa: E402
from .knowledge import knowledge_base  # noqa: E402

app = FastAPI(
    title="交房缺陷与整改协同 · MVP",
    description="FastAPI + Harness + RAG 知识库 + 权限分层；合成数据演示，只读不回写。",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PARTS = load_parts(ROOT / "src/data/unit_parts.json")


class Store:
    """演示用内存态；重启恢复样例，不连接任何真实业务系统。"""

    def __init__(self) -> None:
        self.defects: List[Defect] = load_defects()
        self.audits: Dict[str, Dict[str, Any]] = {}
        self.reviews: Dict[str, Dict[str, Any]] = {}
        self.last_harness: Optional[Dict[str, Any]] = None

    def get(self, defect_id: str) -> Defect:
        for d in self.defects:
            if d.defect_id == defect_id:
                return d
        raise HTTPException(404, "缺陷不存在")


store = Store()


# ---------- 权限依赖 ----------
def require(permission: str) -> Callable[..., User]:
    def dependency(
        authorization: Optional[str] = Header(default=None),
        x_auth_token: Optional[str] = Header(default=None, alias="X-Auth-Token"),
    ) -> User:
        # 云端反向代理会接管 Authorization 头，故提供 X-Auth-Token 备用通道
        token = x_auth_token
        if not token and authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1]
        if not token:
            raise HTTPException(401, "缺少 Token（Authorization: Bearer 或 X-Auth-Token）")
        user = auth_store.resolve(token)
        if not user:
            raise HTTPException(401, "Token 无效或已过期")
        if not auth_store.allows(user, permission):
            raise HTTPException(403, "角色 %s 无权限 %s" % (user.role, permission))
        return user
    return dependency


# ---------- 请求模型 ----------
class LoginRequest(BaseModel):
    name: str = Field(default="演示用户", description="具名操作人员")
    role: str = Field(default="viewer", description="admin/inspector/rectifier/auditor/viewer")


class DefectCreate(BaseModel):
    unit: str = Field(..., description="户号，如 7栋-1802")
    description: str = Field(..., description="缺陷描述")
    photo_ids: List[str] = Field(default_factory=list, description="照片引用")
    expected_part: Optional[str] = Field(default=None, description="可选：预期部位编码（演示验收用）")


class ReviewRequest(BaseModel):
    decision: str = Field(..., description="采纳 / 不采纳 / 转人工")
    note: str = Field(default="", description="人工改动说明，由具名人员填写")


# ---------- 基础与健康 ----------
@app.get("/", response_class=HTMLResponse)
def root(accept: Optional[str] = Header(default=None)):
    """浏览器访问展示演示界面；API 客户端（Accept: application/json）仍取项目信息。"""
    if accept and "text/html" in accept:
        return HTMLResponse((Path(__file__).parent / "ui.html").read_text(encoding="utf-8"))
    return JSONResponse({
        "project": "交房缺陷与整改协同 · MVP",
        "five_elements": ["FastAPI", "Harness", "知识库(RAG+图谱)", "权限分层", "在线部署"],
        "boundary": "只读试点；不回写工单、不自动关单、不代替客户签字（f05/f32/f40）",
        "docs": "/docs",
        "ui": "/ui",
    })


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def ui() -> HTMLResponse:
    """面向演示的正常界面首页；调用本服务现有 API 展示真实数据。"""
    return HTMLResponse((Path(__file__).parent / "ui.html").read_text(encoding="utf-8"))


@app.get("/api/v1/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "defects": len(store.defects), "corpus": len(knowledge_base.docs)}


# ---------- 权限 ----------
@app.post("/api/v1/auth/login")
def login(req: LoginRequest) -> Dict[str, Any]:
    user = auth_store.login(req.name, req.role)
    if not user:
        raise HTTPException(400, "未知角色；可选：" + ", ".join(sorted(PERMISSIONS)))
    return {"token": user.token, "name": user.name, "role": user.role,
            "label": user.label, "permissions": sorted(PERMISSIONS[user.role])}


@app.get("/api/v1/me")
def me(user: User = Depends(require("defect:read"))) -> Dict[str, Any]:
    return {"name": user.name, "role": user.role, "label": ROLE_LABELS[user.role],
            "permissions": sorted(PERMISSIONS[user.role])}


# ---------- 最小业务闭环 ----------
@app.get("/api/v1/defects")
def list_defects(user: User = Depends(require("defect:read"))) -> Dict[str, Any]:
    master_ids, counts = dedupe_by_master(store.defects)
    return {
        "items": [asdict(d) for d in store.defects],
        "summary": {
            "defect_count": len(store.defects),
            "master_id_count": len(master_ids),
            "work_order_total": sum(counts.values()),
            "dedupe_note": "按主编号统计，避免一缺陷多工单导致复验通过率重复计数（f31/f33/f53）",
        },
    }


@app.post("/api/v1/defects", status_code=201)
def create_defect(req: DefectCreate, user: User = Depends(require("defect:create"))) -> Dict[str, Any]:
    idx = len(store.defects) + 1
    defect = Defect(
        defect_id="D-%04d" % (1000 + idx),
        master_id="BU-20261101-%03d" % idx,
        unit=req.unit,
        description=req.description,
        photo_ids=req.photo_ids,
        floorplan_version=PARTS.get("version", "floorplan-v3"),
        source_system="交付验房",
        data_version=1,
        snapshot_at="2026-11-19T09:00:00+08:00",
        reverify=Reverify(authorized=False),
        work_orders=[],
        attachments_complete=bool(req.photo_ids),
        rule_versions=["v2.1"],
        system_available=True,
        handover=Handover(five_elements=False, confirmed_by_receiver=False),
        expected_part=req.expected_part,
    )
    store.defects.append(defect)
    return {"created": asdict(defect), "operator": user.name,
            "note": "新登记缺陷未复验、无工单；关单仍由人工按现有流程执行（f11/f32）"}


@app.post("/api/v1/defects/{defect_id}/locate")
def locate_defect(defect_id: str, mode: str = Query(default="rule", pattern="^(rule|prompt)$"),
                  user: User = Depends(require("locate:run"))) -> Dict[str, Any]:
    d = store.get(defect_id)
    suggestion = locate(d, PARTS, mode=mode)
    red_lines = [x.to_dict() for x in detect_red_lines(d)]
    audit = build_audit(d, suggestion, detect_red_lines(d))
    store.audits[defect_id] = audit
    return {
        "defect_id": defect_id,
        "unit": d.unit,
        "suggestion_or_prompt": suggestion,
        "red_lines": red_lines,
        "handover_complete": handover_complete(d),
        "decision": "转人工兜底" if red_lines else "候选建议待人工确认（f15/f22）",
        "audit": audit,
        "operator": user.name,
    }


@app.post("/api/v1/defects/{defect_id}/review")
def review_defect(defect_id: str, req: ReviewRequest,
                  user: User = Depends(require("review:write"))) -> Dict[str, Any]:
    d = store.get(defect_id)
    record = {
        "defect_id": defect_id,
        "business_id": d.master_id,
        "decision": req.decision,
        "human_change": req.note,
        "reviewer": user.name,
        "role": user.role,
        "fact_refs": ["f22", "f45"],
        "note": "人工复核已留痕；本接口不修改缺陷状态、不关单（f32/f40）",
    }
    store.reviews[defect_id] = record
    if defect_id in store.audits:
        store.audits[defect_id]["人工改动"] = req.note or "无改动"
        store.audits[defect_id]["签核人"] = user.name
    return record


@app.get("/api/v1/defects/{defect_id}/audit")
def get_audit(defect_id: str, user: User = Depends(require("audit:read"))) -> Dict[str, Any]:
    store.get(defect_id)
    return store.audits.get(defect_id, {"note": "尚未生成审计记录，请先调用 /locate"})


# ---------- 知识库：RAG + LLM Wiki ----------
@app.get("/api/v1/knowledge/search")
def knowledge_search(q: str = Query(..., description="检索问题"),
                     top_k: int = Query(default=5, ge=1, le=20),
                     user: User = Depends(require("knowledge:read"))) -> Dict[str, Any]:
    return knowledge_base.search(q, top_k)


@app.get("/api/v1/knowledge/graph")
def knowledge_graph(user: User = Depends(require("knowledge:read"))) -> Dict[str, Any]:
    return knowledge_base.graph()


@app.get("/api/v1/knowledge/mermaid")
def knowledge_mermaid(user: User = Depends(require("knowledge:read"))) -> Dict[str, str]:
    return {"mermaid": knowledge_base.mermaid()}


# ---------- Harness ----------
@app.post("/api/v1/harness/run")
def harness_run(gate: Optional[str] = Query(default=None, pattern="^(G0|G1|G2|G3|G4)$"),
                user: User = Depends(require("harness:read"))) -> Dict[str, Any]:
    store.last_harness = run_harness(gate)
    return store.last_harness


@app.get("/api/v1/harness/report")
def harness_report(user: User = Depends(require("harness:read"))) -> Dict[str, Any]:
    return store.last_harness or {"note": "尚未运行，请先 POST /api/v1/harness/run"}


# 保留 replace 导入供后续状态复制扩展使用，避免静态检查误报
_ = replace
