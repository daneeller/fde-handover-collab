"""审计留痕：六要素结构化输出（f45）。"""
from __future__ import annotations

from typing import Any, Dict, List

from src.models import AuditRecord, Defect, RedLine


def build_audit(
    defect: Defect,
    suggestion: Dict[str, Any],
    red_lines: List[RedLine],
) -> Dict[str, Any]:
    """生成一条审计记录；人工改动与签核人留空，由具名人员事后补录。"""
    fact_refs: List[str] = ["f45"]
    fact_refs += list(suggestion.get("fact_refs", []))
    for line in red_lines:
        fact_refs.extend(line.fact_refs)
    # 去重且保持顺序
    fact_refs = list(dict.fromkeys(fact_refs))

    record = AuditRecord(
        business_id=defect.master_id,
        data_version=defect.data_version,
        fact_refs=fact_refs,
        suggestion={
            "defect_id": defect.defect_id,
            "location": suggestion.get("part_code"),
            "confidence": suggestion.get("confidence"),
            "needs_confirmation": suggestion.get("needs_confirmation", True),
            "red_lines": [line.code for line in red_lines],
            "snapshot_at": defect.snapshot_at,
        },
    )
    return record.to_dict()
