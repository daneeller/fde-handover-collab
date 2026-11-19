# Issue 草稿：建议为 FDE 交付框架补充「提示词来源追溯」与「可执行 Harness 关卡」

> 用途：提交到公开仓库的 Issue。目标仓库待确认（建议 `kalyvask/fde-simulation`，本项目方法来源即引用该框架）。

---

## Title

[Proposal] Add prompt provenance tracking and executable harness gates to project deliverables

## Body

Hi maintainers,

While applying the `workflow-decomposition` / `outcome-risk-matrix` / `4-source-convergence`
framework to a course project (property handover defect rectification), I ran into two
reproducible gaps in the deliverable structure. I would like to propose two lightweight
additions to the framework.

### Gap 1: prompts have no provenance record

A repo can contain an "agent prompts" folder and still fail the question
**"where did these prompts come from, and what do they produce?"**
In the grading feedback I received, the highest-scoring repo had all five material
folders but was still docked points because prompt provenance was implicit.

Proposed addition: a one-page `prompt-provenance.md` template with columns

```
prompt_id | source_material | fact_ids | output_artifact | code_binding | verification
```

Every prompt in the repo must appear in this table. Unregistered prompts are not
counted as deliverables.

### Gap 2: prompts are never turned into runnable code

The same feedback explicitly said: **"the missing part is turning the prompts into a
runnable prototype."** A prompt document alone is not verifiable — an evaluator cannot
execute it.

Proposed addition: require each project to include a minimal `src/` prototype where

- every prompt template has a corresponding function (`prompts.py`), and
- the business rules expressed in the prompt are executable in `rule` mode
  (no model key required), so a reviewer can run `python src/main.py --self-test`.

### Gap 3: harness gates are described but not executable

The method doc defines gates such as "data gate" and "red-line gate", but there is no
reference implementation. I implemented G0–G4 as a callable module and would be happy
to contribute it as an example.

### What I can contribute

I have a working, zero-dependency reference implementation (FastAPI + local Harness +
RAG knowledge base with fact-ID citations + role-based access) at:
https://github.com/daneeller/fde-handover-collab

Happy to open a PR adding `examples/handover-defect-mvp/` if this is of interest.

Note: all data in the example is synthetic training data; no real personal information.
