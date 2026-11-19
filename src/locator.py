"""缺陷定位辅助：把「描述+照片元数据 → 户型部位」从提示词落成可运行逻辑（f10/f42）。

两种运行方式：
  mode="rule"    —— 零依赖关键词匹配，可离线跑，输出候选与置信度，绝不自动确认；
  mode="prompt"  —— 不调用模型，只把同一份业务规则渲染成完整提示词，供外部模型执行。
两种方式都强制返回 needs_confirmation=True 或由红线转人工，不产生关单动作。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.models import Defect, LocationSuggestion
from src.prompts import render_location_prompt


def load_parts(path: str | Path) -> Dict[str, Any]:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def _score(defect: Defect, part: Dict[str, Any]) -> Tuple[int, List[str]]:
    text = defect.description
    hits = [kw for kw in part.get("keywords", []) if kw and kw in text]
    return len(hits), hits


def locate(defect: Defect, parts_doc: Dict[str, Any], mode: str = "rule") -> Dict[str, Any]:
    """产出定位候选。返回 dict，便于 CLI 直接 JSON 序列化。"""
    if mode == "prompt":
        return {
            "mode": "prompt",
            "defect_id": defect.defect_id,
            "prompt": render_location_prompt(defect, parts_doc),
            "note": "本模式仅输出提示词；模型返回仍须人工确认（f15/f22），不得自动关单。",
        }
    if mode != "rule":
        raise ValueError("mode must be 'rule' or 'prompt'")

    parts: List[Dict[str, Any]] = parts_doc.get("parts", [])
    scored = [(*_score(defect, p), p) for p in parts]
    scored.sort(key=lambda x: x[0], reverse=True)

    top_score, top_hits, top_part = scored[0]
    tied = [p for s, _, p in scored if s == top_score and s > 0]
    alternatives = [part["code"] + " " + part["name"] for score, _, part in scored[1:4] if score > 0]

    # 描述中同时出现「照片为X」与另一部位关键词时，视为描述-照片错配，强制人工核对（f10）
    photo_mismatch = any(
        ("照片为" + kw) in defect.description or ("照片拍的是" in defect.description and kw in defect.description)
        for p in parts for kw in p.get("keywords", [])
    )
    needs_confirmation = True  # 任何情况下都不自动确认：采纳与否由具名人员决定（f22）
    if top_score == 0:
        confidence = 0.0
        top_hits = []
    elif photo_mismatch or len(tied) > 1:
        confidence = round(0.35 + 0.1 * top_score, 3)
    else:
        confidence = round(min(0.5 + 0.15 * top_score, 0.9), 3)

    suggestion = LocationSuggestion(
        part_code=top_part.get("code", "UNKNOWN"),
        part_name=top_part.get("name", "待核实"),
        confidence=confidence,
        hits=top_hits,
        alternatives=alternatives,
        needs_confirmation=needs_confirmation,
    )
    result = suggestion.to_dict()
    result.update({
        "mode": "rule",
        "defect_id": defect.defect_id,
        "unit": defect.unit,
        "photo_ids": defect.photo_ids,
        "photo_description_mismatch": photo_mismatch,
        "repair_note": top_part.get("repair_note", "待核实"),
        "floorplan_version": parts_doc.get("version", "unknown"),
        "snapshot_at": defect.snapshot_at,
    })
    return result
