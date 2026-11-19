"""确定性规则引擎：红线阻断、主编号去重、交接完整性（f11/f24/f31/f33/f44）。

全部为纯函数，只读输入、只产出提示；不修改传入对象，不访问网络，不写回工单。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from src.models import Defect, RedLine


def detect_red_lines(defect: Defect) -> List[RedLine]:
    """检测四类异常触发，任一命中即强制转人工（f44）。

    R1 未复验关单：无复验授权却出现 done/closed 工单（f11/f42）。
    R2 资料缺依据：无照片或随单资料不齐（f15/f44）。
    R3 规则冲突：存在两个及以上业务规则版本，须并列提交质量经理（f24）。
    R4 关键系统不可用：按快照标记「暂未更新」，不得当作最新状态（f35/f44）。
    """
    found: List[RedLine] = []

    closed_orders = [w for w in defect.work_orders if w.status in {"done", "closed"}]
    if (not defect.reverify.authorized or defect.reverify.result is None) and closed_orders:
        found.append(RedLine(
            code="R1",
            name="未复验关单",
            detail="无复验授权或复验结果为空，但工单 %s 已置为完成/关闭；禁止自动关单（f11/f42）。"
                   % ", ".join(w.order_id for w in closed_orders),
            fact_refs=["f11", "f42", "f40"],
        ))

    if not defect.photo_ids or not defect.attachments_complete:
        found.append(RedLine(
            code="R2",
            name="资料缺依据",
            detail="照片数=%d，随单资料完整=%s；关键说明不得留在便签或群消息而不随单交接（f15/f14）。"
                   % (len(defect.photo_ids), defect.attachments_complete),
            fact_refs=["f15", "f44", "f14"],
        ))

    if len(set(defect.rule_versions)) > 1:
        found.append(RedLine(
            code="R3",
            name="两版本规则冲突",
            detail="检测到规则版本 %s；须并列附两版本交质量经理裁决，不自行合并、不选宽松条款（f24）。"
                   % " / ".join(defect.rule_versions),
            fact_refs=["f24", "f44"],
        ))

    if not defect.system_available:
        found.append(RedLine(
            code="R4",
            name="关键系统不可用",
            detail="接口不可用；仅可使用带时间戳快照并标注「暂未更新」（快照时间 %s），重连后按业务编号去重补齐（f35）。"
                   % defect.snapshot_at,
            fact_refs=["f35", "f44"],
        ))

    return found


def dedupe_by_master(defects: List[Defect]) -> Tuple[List[str], Dict[str, int]]:
    """按主编号去重，返回 (主编号列表, 每个主编号的工单数)。

    一条缺陷可拆多张工单，复验通过率若按工单计数会重复（f31/f33/f53）。
    """
    grouped: Dict[str, int] = {}
    for d in defects:
        grouped[d.master_id] = grouped.get(d.master_id, 0) + len(d.work_orders)
    return sorted(grouped), grouped


def handover_complete(defect: Defect) -> bool:
    """交接五要素齐全 + 对方确认接手，才算完成（f23）。"""
    return defect.handover.five_elements and defect.handover.confirmed_by_receiver


def stale_snapshot(defect: Defect, max_age_hours: int = 1) -> bool:
    """超过一个同步周期标记「待刷新」（f34）。仅按字符串时间戳粗判，便于离线演示。"""
    from datetime import datetime, timedelta

    try:
        t = datetime.fromisoformat(defect.snapshot_at)
    except ValueError:
        return True
    return datetime.now(t.tzinfo) - t > timedelta(hours=max_age_hours)
