# ADR 0008: Local Ollama model boundary

## Status

Accepted

## Context

The project needs a real generative model demonstration without requiring a paid API or sending
enterprise incident evidence to an external service. The existing OpenAI-compatible transport
provided endpoint portability but only requested generic JSON mode.

## Decision

Add a dedicated Ollama transport that calls the local `/api/chat` endpoint and supplies the full
Pydantic diagnosis schema. Disable thinking traces, use deterministic sampling settings, and
continue to validate every cited evidence identifier after generation.

The deterministic engine remains the default. Ollama is opt-in through environment settings and
does not require an API key. Model errors, malformed output, unsupported hypotheses, and invented
citations continue through the existing fail-closed workflow.

## Consequences

- Local evidence stays on the workstation during model inference.
- Schema-constrained output reduces parsing failures.
- Small models may satisfy JSON syntax while still failing diagnosis policies.
- The grounding and confidence gates must not be weakened to improve a model's apparent pass rate.
- Local latency varies with model size and hardware, so model-backed evaluation records latency
  separately from deterministic regression tests.
