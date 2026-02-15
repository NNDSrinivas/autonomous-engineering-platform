# NAVI Learning & Trace Specification

This document defines how NAVI learns from usage data.

---

# Core Principle

All learning is derived from structured trace events.

Traces must be:
- Append-only
- Non-blocking
- Privacy-aware
- Structured
- Versioned

---

# Trace Event Types

Each event must include:

- runId
- taskId
- endpoint
- mode
- requestedModelId
- effectiveModelId
- timestamp
- repoId (if applicable)

---

## 1. routing_decision

Emitted at request start.

Fields:
- fallbackReasonCode
- fallbackReason
- wasFallback
- endpoint

---

## 2. plan_proposed

Fields:
- planSummary
- steps[]
- questions[]
- recommendedChoices[]

---

## 3. plan_feedback

Fields:
- approved (bool)
- selectedAnswers[]
- rejectionReason (optional)

---

## 4. tool_call

Fields:
- toolName
- arguments (sanitized)
- stepIndex

---

## 5. tool_result

Fields:
- success (bool)
- latencyMs
- errorType (if any)

---

## 6. patch_proposed

Fields:
- filesChanged[]
- diffHash
- linesAdded
- linesRemoved

---

## 7. patch_feedback

Fields:
- accepted (bool)
- reverted (bool)
- userEditDetected (bool)

---

## 8. user_rating

Fields:
- thumbsUp (bool)
- tags[] (optional)

---

## 9. run_outcome

Fields:
- outcome (success | error | cancelled)
- errorCategory
- responseLength
- toolCount

---

# Privacy Rules

- Never log raw secrets.
- Never log environment variables.
- Avoid storing full file contents.
- Store hashes or structured metadata when possible.
- Provide opt-out for enterprise environments.

---

# Dataset Export Formats

All datasets are JSONL.

Each record:

```json
{
  "prompt": "...",
  "completion": "...",
  "metadata": {...}
}
```

---

## Intent Dataset

Prompt:
- user request
- minimal repo summary
- mode used

Completion:
```json
{
  "taskType": "...",
  "riskLevel": "...",
  "recommendedMode": "..."
}
```

---

## Plan Dataset

Prompt:
- task
- repo context

Completion:
```json
{
  "planSummary": "...",
  "steps": [...],
  "questions": [...]
}
```

---

## Tool Router Dataset

Prompt:
- current step
- plan context

Completion:
```json
{
  "toolCalls": [...]
}
```

---

# Evaluation Metrics

- Plan acceptance rate
- Tool success rate
- Patch acceptance rate
- User rating ratio
- Regression test pass rate
