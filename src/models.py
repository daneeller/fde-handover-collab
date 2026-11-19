"""数据模型：对应技术方案第五章 Ontology，字段均带事实编号来源。

本模块只定义只读数据容器；原型不提供任何写回业务系统的方法（f32）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WorkOrder:
    order_id: str
    status: str
    assignee: str = ""

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "WorkOrder":
        return cls(
            order_id=str(raw.get("order_id", "")),
            status=str(raw.get("status", "")),
            assignee=str(raw.get("assignee", "")),
        )


@dataclass(frozen=True)
class Reverify:
    authorized: bool
    result: Optional[str] = None
    at: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Reverify":
        return cls(
            authorized=bool(raw.get("authorized", False)),
            result=raw.get("result"),
            at=raw.get("at"),
        )


@dataclass(frozen=True)
class Handover:
    five_elements: bool
    confirmed_by_receiver: bool

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Handover":
        return cls(
            five_elements=bool(raw.get("five_elements", False)),
            confirmed_by_receiver=bool(raw.get("confirmed_by_receiver", False)),
        )


@dataclass(frozen=True)
class Defect:
    """缺陷条目（f10/f21/f31/f33）。

    master_id 为跨系统唯一主键；一条缺陷可拆多张工单，统计须按主编号去重。
    """

    defect_id: str
    master_id: str
    unit: str
    description: str
    photo_ids: List[str]
    floorplan_version: str
    source_system: str
    data_version: int
    snapshot_at: str
    reverify: Reverify
    work_orders: List[WorkOrder]
    attachments_complete: bool
    rule_versions: List[str]
    system_available: bool
    handover: Handover
    expected_part: Optional[str] = None

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Defect":
        return cls(
            defect_id=str(raw["defect_id"]),
            master_id=str(raw["master_id"]),
            unit=str(raw["unit"]),
            description=str(raw["description"]),
            photo_ids=list(raw.get("photo_ids", [])),
            floorplan_version=str(raw.get("floorplan_version", "")),
            source_system=str(raw.get("source_system", "")),
            data_version=int(raw.get("data_version", 1)),
            snapshot_at=str(raw.get("snapshot_at", "")),
            reverify=Reverify.from_dict(raw.get("reverify", {})),
            work_orders=[WorkOrder.from_dict(x) for x in raw.get("work_orders", [])],
            attachments_complete=bool(raw.get("attachments_complete", False)),
            rule_versions=list(raw.get("rule_versions", [])),
            system_available=bool(raw.get("system_available", False)),
            handover=Handover.from_dict(raw.get("handover", {})),
            expected_part=raw.get("expected_part"),
        )


@dataclass(frozen=True)
class LocationSuggestion:
    """定位建议（候选，不是结论）。f10/f15/f42。"""

    part_code: str
    part_name: str
    confidence: float
    hits: List[str]
    alternatives: List[str] = field(default_factory=list)
    needs_confirmation: bool = True
    fact_refs: List[str] = field(default_factory=lambda: ["f10", "f15", "f42"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "part_code": self.part_code,
            "part_name": self.part_name,
            "confidence": round(self.confidence, 3),
            "hits": self.hits,
            "alternatives": self.alternatives,
            "needs_confirmation": self.needs_confirmation,
            "fact_refs": self.fact_refs,
        }


@dataclass(frozen=True)
class RedLine:
    """异常触发：任一出现即转人工，不得自动关单（f11/f24/f44）。"""

    code: str
    name: str
    detail: str
    fact_refs: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "detail": self.detail,
            "fact_refs": self.fact_refs,
        }


@dataclass(frozen=True)
class AuditRecord:
    """审计留痕六要素（f45）。

    human_change 与 signer 只能由具名人员事后填写，原型留空而非自动填充，
    以保证「不代替专业签核」。
    """

    business_id: str
    data_version: int
    fact_refs: List[str]
    suggestion: Dict[str, Any]
    human_change: Optional[str] = None
    signer: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "业务编号": self.business_id,
            "资料版本": self.data_version,
            "事实引用": self.fact_refs,
            "建议结果": self.suggestion,
            "人工改动": self.human_change if self.human_change else "待人工填写",
            "签核人": self.signer if self.signer else "待人工填写",
        }
