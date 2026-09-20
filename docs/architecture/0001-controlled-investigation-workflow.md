# ADR 0001: Use a controlled investigation graph

Status: accepted for Phase 1

## Context

Incident investigation needs retrieval, tool calls, retries, evidence checks, and future human approvals. A free-running agent can choose unnecessary tools, lose state, or present unsupported conclusions.

## Decision

Use a typed LangGraph workflow with explicit nodes and transitions. Tool access is read-only in Phase 1. Every conclusion must refer to evidence returned during the same investigation. Insufficient evidence is a valid result.

```text
normalize incident
  -> retrieve knowledge
  -> collect operational evidence
  -> build and rank hypotheses
  -> validate evidence and citations
  -> compose report
```

Independent retrieval and tool calls can become parallel nodes after the first vertical slice is stable.

## Consequences

- Investigation behavior is testable and recoverable.
- State-changing tools cannot be added accidentally.
- New failure classes require explicit diagnostic policies or a grounded model node.
- The deterministic Phase 1 diagnosis is intentionally narrow and will later be replaced by a provider-neutral LLM adapter guarded by the same evidence contracts.
