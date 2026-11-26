# PR 草稿：添加可运行的 MVP 参考实现示例

> 用途：在目标仓库（建议 `kalyvask/fde-simulation`）提交 Pull Request。提交前需 fork 目标仓库、建分支、放文件、开 PR。

---

## Title

Add runnable MVP reference example: prompt provenance, G0–G4 harness, and cited RAG knowledge base

## Body

This PR adds a self-contained reference example demonstrating the three gaps discussed
in issue #<ISSUE_NUMBER>. It does not change any existing framework code.

### What is added

```
examples/handover-defect-mvp/
├── README.md                       # 五要素说明 + 启动命令 + 验收样例
├── prompt-provenance.md            # 提示词来源登记表（prompt -> material -> fact_ids -> code）
├── app/
│   ├── main.py                     # FastAPI 服务（18 endpoints, /docs）
│   ├── auth.py                     # 分层权限 + HMAC 无状态 token
│   ├── harness.py                  # G0–G4 可执行评估框架
│   └── knowledge.py                # 本地 RAG 检索 + 引用 + 知识图谱
├── src/                            # 零依赖规则引擎（rule / prompt 双模式）
├── knowledge_base/graph.json       # LLM Wiki 风格实体关系图
├── tests/                          # 12 项自动化测试
└── docs/90min-mvp-prompt.docx      # 可直接交给开发 Agent 的研发提示词
```

### Why it is useful

1. **Prompt provenance is explicit**: each prompt has `source_material`, `fact_ids`,
   `output_artifact`, and `code_binding`. Reviewers can trace any claim back to f00–f55.
2. **Prompts are executable**: `python src/main.py --self-test` runs the exact rules
   described in the prompt documents, with no API key or model call.
3. **Harness gates are runnable**: `POST /api/v1/harness/run` returns a structured
   G0–G4 report on the synthetic sample, instead of a textual checklist only.
4. **Knowledge base cites sources**: RAG hits return `source` and `fact_id`; the
   knowledge graph is versioned JSON plus Mermaid output.
5. **Safe by construction**: all outputs carry `needs_confirmation=true`; audit records
   leave `signer` empty until a named human fills it. No write-back or auto-closure.

### How to verify

```bash
cd examples/handover-defect-mvp
pip install -r requirements.txt
python src/main.py --self-test
python -m unittest discover -s tests -v
uvicorn app.main:app --reload --port 8000
curl -X POST http://127.0.0.1:8000/api/v1/harness/run -H "Authorization: Bearer <token>"
```

Expected: 12 tests pass; harness gates report pass on the synthetic sample; all data is synthetic.

### Checklist

- [ ] No existing framework files modified
- [ ] All example data is synthetic; no personal information
- [ ] Zero third-party dependency in `src/` core logic
- [ ] README includes start commands and acceptance samples
