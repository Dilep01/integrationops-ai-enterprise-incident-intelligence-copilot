# ADR 0002: Put a grounding boundary around model output

Status: accepted for Phase 3

## Context

An incident diagnosis model receives retrieved documents and operational evidence. Both model output and retrieved text are untrusted. A model can invent citations, return malformed data, or recommend a state-changing action without approval.

## Decision

All diagnosis providers implement one typed interface and return the same structured proposal. Before a proposal enters the incident report, the application:

1. checks that enough independent evidence is available;
2. parses the response against a Pydantic schema;
3. rejects evidence identifiers that were not supplied to the model;
4. requires evidence for every supported hypothesis;
5. converts unapproved state-changing recommendations into approval requests; and
6. records the provider, model, and prompt version.

Retrieved passages are explicitly marked as untrusted data in the model instructions. Model or validation failures produce an insufficient-evidence report instead of an uncited conclusion.

## Consequences

- Qwen, Llama, hosted APIs, and deterministic test engines can share one contract.
- Model changes do not bypass the evidence and action policies.
- A live model endpoint is optional during development and automated testing.
- Provider-specific capabilities must remain behind the transport interface.
