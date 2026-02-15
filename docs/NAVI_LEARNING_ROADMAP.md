# NAVI Learning Roadmap

This roadmap defines the path from orchestration to competitive NAVI models.

---

# M0 — Routing & Modes (Complete)
Unified registry + ModelRouter.
Strict private.
Trace foundation.

---

# M1 — Trace Schema v1
Implement structured trace events.
Ensure append-only JSONL.
Add exporter scripts.

Definition of Done:
- All run stages emit events.
- Exporters produce valid JSONL.
- Unit tests validate schema.

---

# M2 — Plan Mode v1
Implement Plan Wizard:
- Structured plan
- 2–6 clarification questions
- Plan approval required for risky tasks

Definition of Done:
- plan_proposed + plan_feedback emitted
- UI wizard works
- No auto-execution without confirmation

---

# M3 — Feedback Capture
Add:
- thumbs up/down
- patch acceptance/rejection
- plan approval/rejection

Definition of Done:
- user_rating + patch_feedback events stored
- Deduplicated per runId

---

# M4 — Dataset Exporters
Implement:
- export_intent_dataset.py
- export_plan_dataset.py
- export_tool_router_dataset.py

Definition of Done:
- Valid prompt/completion pairs
- Secrets removed
- Balanced sampling logic

---

# M5 — NAVI Scout (Intent Model)
Train small model for:
- Task classification
- Risk level
- Mode recommendation

Definition of Done:
- Higher accuracy than rule baseline
- Confidence threshold fallback

---

# M6 — NAVI Architect (Planning Model)
Train plan generator model.

Definition of Done:
- Plan acceptance rate improves
- Fewer plan revisions needed

---

# M7 — NAVI Conductor (Tool Model)
Train tool routing model.

Definition of Done:
- Higher tool success rate
- Fewer redundant calls
- Safe tool usage

---

# M8 — NAVI Guardian (Safety Model)
Train risk classifier + policy assistant.

Definition of Done:
- Reduced unsafe suggestions
- High approval prediction accuracy

---

# M9 — NAVI Core v1
Distill high-quality traces into general model.

Definition of Done:
- Comparable coding performance on internal benchmark
- Handles structured JSON tool calls

---

# M10 — Competitive Scaling
Add:
- Long-context training
- Agent benchmarks
- SWE-style test suite
- Multi-repo evaluation

Definition of Done:
- NAVI Core-Agent competitive in agentic workflows
- Stable tool usage + test-passing loop

---

# Governance

- Each milestone requires:
  - Tests
  - Evaluation metrics
  - Documentation update
  - Backward compatibility
