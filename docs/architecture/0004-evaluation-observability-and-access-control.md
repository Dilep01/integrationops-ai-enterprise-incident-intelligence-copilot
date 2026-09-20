# ADR 0004: evaluation, observability, and request-context authorization

Status: accepted for Phase 5

## Context

The incident workflow already filtered retrieved knowledge by tenant and role, but the API
accepted tenant and role values in the incident body. Those fields are untrusted caller input.
The project also needed repeatable diagnosis evaluation, trace visibility, and regression tests
for prompt injection and accidental secret disclosure.

## Decision

- Derive tenant identity and roles from X-Tenant-ID and X-Roles request headers.
- Ignore tenant and role values supplied in the incident body.
- Apply endpoint-specific role policies for investigation, viewing, feedback, and metrics.
- Reject common instruction-override patterns before an investigation starts.
- Redact bearer tokens, API keys, client secrets, and passwords before evidence is sent to a
  model transport.
- Create OpenTelemetry spans around each investigation without exporting data by default.
- Expose aggregate local counters at GET /api/v1/metrics.
- Evaluate retrieval and diagnosis separately from versioned JSONL datasets.

Header-based identity is a local portfolio adapter, not production authentication. A deployed
environment must place the API behind a trusted identity-aware gateway that removes inbound
identity headers and writes verified claims.

## Consequences

Tenant and role claims can no longer be escalated through the request body. Evaluation now
reports classification accuracy, answer relevance, faithfulness, groundedness, citation
correctness, hallucination rate, latency, and estimated model cost. The deterministic provider
reports zero model cost. OpenTelemetry stays local unless a later deployment explicitly
configures an approved exporter.
