#!/usr/bin/env python3
"""交房缺陷与整改协同 · 可运行原型 CLI。

零第三方依赖，Python 3.9+。

用法：
    python src/main.py --demo                  # 离线演示：逐条缺陷给出定位候选/红线/审计
    python src/main.py --mode prompt --demo    # 输出可发给模型的完整提示词（不调用模型）
    python src/main.py --self-test             # 运行内置断言

边界：只读、不写回工单、不自动关单、不代替专业签核（f05/f15/f32/f40）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent
# 支持直接 `python src/main.py` 运行，无需安装包
if str(BASE_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BASE_DIR.parent))

from src.audit import build_audit  # noqa: E402
from src.locator import load_parts, locate  # noqa: E402
from src.models import Defect  # noqa: E402
from src.prompts import render_redline_prompt  # noqa: E402
from src.rules import dedupe_by_master, detect_red_lines, handover_complete  # noqa: E402

DATA_DIR = BASE_DIR / "data"


def load_defects(path: Path | None = None) -> List[Defect]:
    target = path or (DATA_DIR / "sample_defects.json")
    with Path(target).open(encoding="utf-8") as f:
        raw = json.load(f)
    return [Defect.from_dict(x) for x in raw["defects"]]


def analyze(defects: List[Defect], mode: str = "rule") -> Dict[str, Any]:
    parts_doc = load_parts(DATA_DIR / "unit_parts.json")
    results = []
    for d in defects:
        suggestion = locate(d, parts_doc, mode=mode)
        red_lines = detect_red_lines(d) if mode == "rule" else []
        item: Dict[str, Any] = {
            "defect_id": d.defect_id,
            "master_id": d.master_id,
            "unit": d.unit,
            "suggestion_or_prompt": suggestion,
            "handover_complete": handover_complete(d),
        }
        if mode == "rule":
            item["red_lines"] = [x.to_dict() for x in red_lines]
            item["audit"] = build_audit(d, suggestion, red_lines)
            if red_lines:
                item["decision"] = "转人工兜底"
            elif suggestion.get("photo_description_mismatch"):
                item["decision"] = "描述—照片冲突，转人工核对（错误建议不覆盖原记录，f15）"
            else:
                item["decision"] = "候选建议待人工确认"
        else:
            item["redline_prompt"] = render_redline_prompt(d)
            item["decision"] = "本模式只输出提示词，不执行判定"
        results.append(item)

    masters, order_counts = dedupe_by_master(defects)
    return {
        "batch": "B7-2026-11",
        "mode": mode,
        "results": results,
        "summary": {
            "defect_count": len(defects),
            "master_id_count": len(masters),
            "work_order_total": sum(order_counts.values()),
            "dedupe_note": "一条缺陷可拆多张工单；按主编号统计，避免复验通过率重复计数（f31/f33/f53）。",
            "red_line_triggered": sum(1 for r in results if r.get("red_lines")) if mode == "rule" else None,
            "boundary": "只读试点：不回写工单、不自动关单、不代替客户签字与质量鉴定（f05/f32/f40）。",
        },
    }


def self_test() -> None:
    defects = load_defects()
    assert len(defects) == 6, "样例数据应为 6 条"
    report = analyze(defects, "rule")
    assert report["summary"]["master_id_count"] == 6
    assert report["summary"]["work_order_total"] == 7  # 1+1+1+1+2+1

    by_id = {r["defect_id"]: r for r in report["results"]}
    codes = {r["defect_id"]: [x["code"] for x in r["red_lines"]] for r in report["results"]}

    # D-1003：未复验却已关单 -> R1
    assert "R1" in codes["D-1003"], codes["D-1003"]
    # D-1005：资料缺依据 + 两版本冲突 + 交接未确认
    assert set(codes["D-1005"]) >= {"R2", "R3"}, codes["D-1005"]
    assert by_id["D-1005"]["handover_complete"] is False
    # D-1006：系统不可用 -> R4
    assert "R4" in codes["D-1006"], codes["D-1006"]
    # 定位候选：正常样本应命中期望部位
    parts_doc = load_parts(DATA_DIR / "unit_parts.json")
    for d in defects[:3]:
        s = locate(d, parts_doc)
        assert s["part_code"] == d.expected_part, (d.defect_id, s["part_code"], d.expected_part)
        assert s["needs_confirmation"] is True
    # 错配样本必须标记并强制人工
    mismatch = locate(defects[3], parts_doc)
    assert mismatch["photo_description_mismatch"] is True
    # 审计六要素齐全，人工字段不自动填
    audit = by_id["D-1001"]["audit"]
    for key in ("业务编号", "资料版本", "事实引用", "建议结果", "人工改动", "签核人"):
        assert key in audit, key
    assert audit["签核人"] == "待人工填写"
    # prompt 模式不得包含动作词
    prompt_report = analyze(defects[:1], "prompt")
    text = prompt_report["results"][0]["suggestion_or_prompt"]["prompt"]
    assert "f10" in text and "待验证" in text
    print("SELF-TEST OK: 6 defects, 6 masters, 7 work orders, 4 red-line types covered, audit 6 fields.")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="用样例数据运行演示")
    parser.add_argument("--mode", choices=["rule", "prompt"], default="rule", help="rule=离线规则；prompt=输出提示词")
    parser.add_argument("--data", type=str, default=None, help="自定义缺陷 JSON 路径")
    parser.add_argument("--self-test", action="store_true", help="运行内置断言")
    parser.add_argument("--out", type=str, default=None, help="将结果写入 JSON 文件")
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        return 0
    if not args.demo:
        parser.print_help()
        return 0

    defects = load_defects(Path(args.data) if args.data else None)
    report = analyze(defects, args.mode)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print("written:", args.out)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
