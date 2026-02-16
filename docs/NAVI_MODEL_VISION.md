# NAVI Model Vision

## What "NAVI Model" Means

NAVI is not just a wrapper over external LLM APIs.

NAVI is an Autonomous Engineering Intelligence (AEI) runtime composed of:

1. **NAVI Modes** (user-facing orchestration layer)
2. **NAVI Worker Models** (specialized internal models)
3. **NAVI Core Models** (larger general-purpose models, trained progressively)
4. **Policy + Tooling Runtime** (governance + execution control)
5. **Trace-based Learning System**

NAVI is a system, not a single model.

---

# User-Facing NAVI Modes

These are orchestration behaviors:

- **NAVI Orbit** → Intelligent auto-selection + orchestration
- **NAVI Sprint** → Fast responses
- **NAVI Forge** → Deep reasoning and engineering tasks
- **NAVI Vault** → Strict private/local inference

Modes determine:
- Routing strategy
- Tool usage permissions
- Fallback behavior
- Budgeting and safety controls

---

# Internal NAVI Worker Models

These are proprietary models trained on NAVI trace data.

## NAVI Scout
- Task classification
- Risk scoring
- Mode recommendation

## NAVI Architect
- Step planning
- Clarification question generation
- Structured task breakdown

## NAVI Conductor
- Tool routing
- Tool call structuring (JSON)
- Multi-step agent sequencing

## NAVI Scribe
- PR summaries
- Code explanations
- Changelog generation

## NAVI Guardian
- Risk analysis
- Policy enforcement classification
- Approval prediction

These models are small and efficient.

---

# NAVI Core Models (Later Phases)

## NAVI Core
General-purpose coding + reasoning model.

## NAVI Core-Code
Optimized for code synthesis and diff generation.

## NAVI Core-Agent
Optimized for multi-step tool usage.

These are trained using:
- Distillation
- Supervised fine-tuning (SFT)
- Preference tuning (DPO/RLAIF)
- Tool usage traces

---

# What NAVI Is NOT (Non-Goals)

- Not training a frontier-scale GPT competitor immediately.
- Not replacing external models on day one.
- Not sacrificing safety for autonomy.
- Not silently overriding user choices.

---

# Long-Term Competitive Positioning

NAVI competes by:

- Deterministic orchestration
- Transparent routing
- Approval-driven autonomy
- Structured planning
- Proprietary learning from engineering traces
- Integrated tool governance
- Repo + org awareness

NAVI's advantage is **system intelligence**, not raw parameter count.
