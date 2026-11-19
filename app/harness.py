"""Harness 评估工程：G0–G4 五关可执行检查。

关卡定义来自 docs/技术方案.md 第九章，本机无外部 harness 服务，
因此这里把关卡落成可调用、可复现的本地评估框架（课程要求的"Harness 工程"）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit import build_audit  # noqa: E402
from src.locator import load_parts, locate  # noqa: E402
from src.main import load_defects  # noqa: E402
from src.models import Defect  # noqa: E402
from src.prompts import LOCATION_PROMPT, PROVENANCE_HEADER, REDLINE_PROMPT  # noqa: E402
from src.rules import dedupe_by_master, detect_red_lines  # noqa: E402

from .auth import PERMISSIONS, auth_store  # noqa: E402

GATES = [
    ("G0", "口径关", ["f02", "f42", "f45"]),
    ("G1", "数据关", ["f31", "f33", "f53"]),
    ("G2", "定位关", ["f10", "f42"]),
    ("G3", "红线关", ["f11", "f24", "f35", "f44"]),
    ("G4", "权限关", ["f22", "f40", "f41"]),
]


def _check(name: str, passed: bool, evidence: str) -> Dict[str, Any]:
    return {"name": name, "pass": bool(passed), "evidence": evidence}


def _g0(defects: List[Defect], parts: Dict[str, Any]) -> List[Dict[str, Any]]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checks = [
        _check("合成场景声明", "合成训练" in readme, "README 首部声明数据性质"),
        _check("提示词带事实编号", "f10" in LOCATION_PROMPT, "LOCATION_PROMPT 含 f10"),
        _check("提示词声明待验证", "待验证" in (PROVENANCE_HEADER + LOCATION_PROMPT),
               "来源头 + LOCATION_PROMPT 含待验证假设"),
        _check("定位提示词禁止关单", "不关单" in LOCATION_PROMPT, "LOCATION_PROMPT 禁止关单"),
        _check("红线提示词转人工", "接手人" in REDLINE_PROMPT, "REDLINE_PROMPT 要求 handoff 三字段"),
    ]
    d = defects[0]
    rec = build_audit(d, locate(d, parts), detect_red_lines(d))
    checks.append(_check(
        "审计六要素齐全",
        all(k in rec for k in ("业务编号", "资料版本", "事实引用", "建议结果", "人工改动", "签核人")),
        "build_audit 输出 6 字段",
    ))
    checks.append(_check("签核人不自动填", rec["签核人"] == "待人工填写", "签核人留空（f22/f45）"))
    return checks


def _g1(defects: List[Defect], _parts: Dict[str, Any]) -> List[Dict[str, Any]]:
    masters, counts = dedupe_by_master(defects)
    total_orders = sum(counts.values())
    return [
        _check("主编号唯一", len(masters) == 6, "6 条缺陷 → %d 个主编号" % len(masters)),
        _check("工单总数正确", total_orders == 7, "工单总数 %d（含 D-1005 两单）" % total_orders),
        _check("一缺陷多工单不重复计数", counts.get("BU-20261101-005") == 2,
               "复验通过率按主编号统计（f31/f53）"),
    ]


def _g2(defects: List[Defect], parts: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    clean = ("D-1001", "D-1002", "D-1003")
    hits = 0
    for d in defects:
        s = locate(d, parts)
        if d.defect_id in clean and s["part_code"] == d.expected_part:
            hits += 1
    rate = hits / len(clean)
    checks.append(_check("正常样本定位命中", hits == len(clean),
                         "%d/%d = %.0f%%（实测样本，非 98%% 验收结论，f42）" % (hits, len(clean), rate * 100)))
    bad = next(d for d in defects if d.defect_id == "D-1004")
    s = locate(bad, parts)
    checks.append(_check("描述—照片冲突被识别", s["photo_description_mismatch"] is True,
                         "D-1004 置信度压低至 %s 并转人工" % s["confidence"]))
    checks.append(_check("所有建议需人工确认", all(locate(d, parts)["needs_confirmation"] for d in defects),
                         "needs_confirmation 恒 true（f15/f22）"))
    return checks


def _g3(defects: List[Defect], _parts: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_id = {d.defect_id: d for d in defects}
    codes = {did: [x.code for x in detect_red_lines(d)] for did, d in by_id.items()}
    return [
        _check("R1 未复验关单阻断", "R1" in codes["D-1003"], "D-1003 触发 R1（f11/f42）"),
        _check("R2/R3 资料与规则冲突", set(codes["D-1005"]) >= {"R2", "R3"}, "D-1005 触发 R2+R3（f24/f44）"),
        _check("R4 系统不可用降级", "R4" in codes["D-1006"], "D-1006 触发 R4（f35/f44）"),
        _check("无红线不误报", codes["D-1001"] == [], "D-1001 无触发"),
    ]


def _g4(defects: List[Defect], parts: Dict[str, Any]) -> List[Dict[str, Any]]:
    admin = auth_store.login("评估员", "admin")
    viewer = auth_store.login("评估员", "viewer")
    rectifier = auth_store.login("评估员", "rectifier")
    assert admin and viewer and rectifier
    checks = [
        _check("viewer 不能登记缺陷", not auth_store.allows(viewer, "defect:create"),
               "viewer 权限=%s" % sorted(PERMISSIONS["viewer"])),
        _check("rectifier 不能代替签核", not auth_store.allows(rectifier, "audit:sign"),
               "整改专员仅可整理/校核/发起复核（f22）"),
        _check("admin 可执行全部", auth_store.allows(admin, "*"), "管理员含通配符权限"),
        _check("不存在借用账号接口", not hasattr(auth_store, "impersonate"), "No impersonate method（f41）"),
    ]
    d = defects[0]
    rec = build_audit(d, locate(d, parts), detect_red_lines(d))
    checks.append(_check("关单动作不由 API 自动执行",
                         rec["建议结果"]["needs_confirmation"] is True,
                         "审计记录标记待人工确认（f32/f40）"))
    return checks


RUNNERS = {"G0": _g0, "G1": _g1, "G2": _g2, "G3": _g3, "G4": _g4}


def run_harness(gate_filter: str | None = None) -> Dict[str, Any]:
    defects = load_defects()
    parts = load_parts(ROOT / "src/data/unit_parts.json")
    gates: List[Dict[str, Any]] = []
    for gid, name, refs in GATES:
        if gate_filter and gid != gate_filter:
            continue
        checks = RUNNERS[gid](defects, parts)
        gates.append({
            "id": gid,
            "name": name,
            "status": "PASS" if all(c["pass"] for c in checks) else "FAIL",
            "checks": checks,
            "fact_refs": refs,
        })
    passed = sum(1 for g in gates if g["status"] == "PASS")
    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total": len(gates),
        "passed": passed,
        "score": round(passed / len(gates) * 100, 1) if gates else 0,
        "gates": gates,
        "note": "本地 Harness 工程，按技术方案 G0–G4 关卡执行；合成数据实测，不代表业务验收通过。",
    }
