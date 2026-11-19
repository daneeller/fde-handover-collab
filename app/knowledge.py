"""知识库：轻量 RAG 检索 + 知识图谱（LLM Wiki）。

默认使用仓库内合成材料与本地规则，不调用模型、不需要密钥（符合课程要求）。
检索结果一律附带来源文件与事实编号，避免无依据回答（f00–f55 / f45）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "knowledge_base"

SOURCES = [
    ("fact", ROOT / "property-handover/02-访谈记录/访谈事实编号索引.md"),
    ("spec", ROOT / "docs/技术方案.md"),
    ("prompt", ROOT / "property-handover/07-智能体提示词/提示词来源追溯表.md"),
    ("process", ROOT / "property-handover/03-现场调研分析/现状流程图.md"),
    ("audit", ROOT / "property-handover/02-访谈记录/访谈记录.md"),
]


def _tokens(text: str) -> List[str]:
    """中文 bigram + 英文单词，纯 Python，无第三方依赖。"""
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text.lower())
    if len(cleaned) < 2:
        return [cleaned] if cleaned else []
    return [cleaned[i:i + 2] for i in range(len(cleaned) - 1)]


def _parse_fact_table(path: Path) -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []
    if not path.exists():
        return docs
    for line in path.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*f\d{2}\s*\|", line.strip()):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 4:
            continue
        docs.append({
            "text": cols[2],
            "source": path.name,
            "fact_id": cols[0],
            "kind": "访谈事实",
            "role": cols[1],
        })
    return docs


def _split_sections(path: Path, kind: str, heading: str) -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []
    if not path.exists():
        return docs
    title, buf = "", []
    for line in path.read_text(encoding="utf-8").splitlines() + ["## __END__"]:
        if line.startswith(heading):
            if title and buf:
                docs.append({
                    "text": " ".join(buf)[:1200],
                    "source": path.name,
                    "fact_id": "",
                    "kind": kind,
                    "section": title,
                })
            title, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line.strip())
    return docs


class KnowledgeBase:
    """从仓库材料现场构建语料，保证知识库与交付文档同源。"""

    def __init__(self) -> None:
        self.docs: List[Dict[str, str]] = []
        for kind, path in SOURCES:
            if kind == "fact":
                self.docs.extend(_parse_fact_table(path))
            elif kind == "audit":
                # 访谈记录按角色小节切分，避免单文档过长
                self.docs.extend(_split_sections(path, "访谈原文", "## "))
            else:
                self.docs.extend(_split_sections(path, kind, "## "))
        self._index = [(set(_tokens(d["text"])), d) for d in self.docs]

    def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        q = set(_tokens(query or ""))
        hits: List[Dict[str, Any]] = []
        for dtokens, doc in self._index:
            if not q or not dtokens:
                continue
            overlap = q & dtokens
            score = len(overlap) / ((len(q) ** 0.5) * (len(dtokens) ** 0.5))
            # 事实编号精确命中加权（如查询里出现 f10）
            fact_ids = re.findall(r"f\d{2}", query or "")
            if doc.get("fact_id") in fact_ids:
                score += 0.5
            if score > 0:
                item = dict(doc)
                item["score"] = round(score, 4)
                item["evidence"] = " ".join(sorted(overlap)[:12])
                hits.append(item)
        hits.sort(key=lambda x: x["score"], reverse=True)
        return {
            "query": query,
            "corpus_size": len(self.docs),
            "total_hits": len(hits),
            "results": hits[:top_k],
            "note": "本地合成语料检索，无模型调用；命中片段均附来源文件与事实编号。",
        }

    def graph(self) -> Dict[str, Any]:
        path = KB_DIR / "graph.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"nodes": [], "edges": [], "note": "graph.json 缺失"}

    def mermaid(self) -> str:
        g = self.graph()
        lines = ["graph LR"]
        for n in g.get("nodes", []):
            lines.append('  %s["%s"]' % (n["id"], n["label"]))
        for e in g.get("edges", []):
            lines.append("  %s -->|%s| %s" % (e["source"], e.get("label", ""), e["target"]))
        return "\n".join(lines)


knowledge_base = KnowledgeBase()
