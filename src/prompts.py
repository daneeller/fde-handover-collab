"""提示词模板（可复制、可追溯）。

每个模板都标注：来源材料、事实编号、对应产出物。
与 property-handover/07-智能体提示词/ 下的说明文件一一对应。
渲染函数只做字符串拼装，不调用任何模型接口。
"""
from __future__ import annotations

from typing import Any, Dict

from src.models import Defect

LOCATION_PROMPT = """你是「交房缺陷与整改协同」试点的只读定位辅助助手。
任务：根据缺陷描述与照片元数据，给出户型部位候选与返工位置提示。

【输入】
- 缺陷编号：{defect_id}
- 户号：{unit}
- 描述：{description}
- 照片引用：{photo_ids}
- 户型图版本：{floorplan_version}
- 资料版本：{data_version}
- 快照时间：{snapshot_at}
- 可选部位：{parts}

【输出要求】
1. 只输出 JSON，字段：part_code, part_name, confidence, evidence_text, needs_confirmation, repair_note。
2. evidence_text 必须逐字引用输入中的描述或照片信息，不得编造。
3. needs_confirmation 恒为 true；本助手不确认部位、不关单、不改状态。
4. 若描述与照片互相矛盾，或匹配不到部位，必须输出 UNKNOWN 并写明「转人工核对」。
5. 每条判断末尾附事实编号：f10（照片—部位错配）、f15（错误不覆盖原记录）、f42（98% 口径未定）。
6. 98% 是缺陷定位准确率，判定人与样本量尚未核实，不得声称达到任何准确率。

【禁止】
- 不生成关单、赔偿、责任认定、客户答复等结论。
- 不覆盖原记录；建议须与原记录并列展示。
"""

REDLINE_PROMPT = """你是「交房缺陷与整改协同」试点的只读规则检查助手。
任务：识别异常触发并转人工，不执行任何业务动作。

【输入】
{input_json}

【检查项（任一命中即转人工）】
R1 未复验关单：无复验授权或复验结果为空却有关闭/完成工单（f11/f42）。
R2 资料缺依据：无照片或随单资料不齐（f15/f44）。
R3 两版本规则冲突：存在两个及以上规则版本（f24）。
R4 关键系统不可用：接口不可用时只用带时间戳快照，标注「暂未更新」（f35/f44）。

【输出要求】
1. 只输出 JSON 数组，每项含：code, name, detail, fact_refs, handoff。
2. handoff 必须包含三个字段：触发原因、接手人、确认时间；接手人与确认时间留空由人工填写。
3. 不得输出「自动关单」「自动通过」「自动赔偿」等动作。
4. 无命中时输出空数组。
"""

PROVENANCE_HEADER = """【来源追溯】
- 输入材料：property-handover/01-业务挖掘 + 02-访谈记录 + 03-现场调研分析 + 04-项目原有资料
- 事实编号体系：f00–f55，见 property-handover/02-访谈记录/访谈事实编号索引.md
- 提示词来源与产出映射：property-handover/07-智能体提示词/提示词来源追溯表.md
- 数据性质：合成训练场景，全部结论为待验证假设
"""


def render_location_prompt(defect: Defect, parts_doc: Dict[str, Any]) -> str:
    parts = ", ".join(
        "%s=%s(%s)" % (p.get("code", ""), p.get("name", ""), "/".join(p.get("keywords", [])[:3]))
        for p in parts_doc.get("parts", [])
    )
    return "\n".join([
        PROVENANCE_HEADER,
        LOCATION_PROMPT.format(
            defect_id=defect.defect_id,
            unit=defect.unit,
            description=defect.description,
            photo_ids=", ".join(defect.photo_ids) or "无",
            floorplan_version=defect.floorplan_version,
            data_version=defect.data_version,
            snapshot_at=defect.snapshot_at,
            parts=parts,
        ),
    ])


def render_redline_prompt(defect: Defect) -> str:
    payload = {
        "defect_id": defect.defect_id,
        "reverify": {"authorized": defect.reverify.authorized, "result": defect.reverify.result},
        "work_orders": [{"order_id": w.order_id, "status": w.status} for w in defect.work_orders],
        "photo_ids": defect.photo_ids,
        "attachments_complete": defect.attachments_complete,
        "rule_versions": defect.rule_versions,
        "system_available": defect.system_available,
        "snapshot_at": defect.snapshot_at,
    }
    import json
    return "\n".join([
        PROVENANCE_HEADER,
        REDLINE_PROMPT.format(input_json=json.dumps(payload, ensure_ascii=False, indent=2)),
    ])
