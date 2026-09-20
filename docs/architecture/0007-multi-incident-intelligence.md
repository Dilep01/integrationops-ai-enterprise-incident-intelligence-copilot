# ADR 0007: multi-incident deterministic intelligence

Status: accepted for Phase 7

## Context

The original vertical slice demonstrated strong grounding and safety behavior but its operational
tools and deterministic diagnosis policy were specific to one HTTP 401 scenario. That made the
architecture reusable while leaving the visible product behavior too narrow.

## Decision

Support five explicit incident classes:

- authentication failure;
- timeout;
- mapping error;
- invalid payload;
- duplicate transaction.

Classification remains deterministic for the offline baseline. Each supported class has
incident-specific logs, configuration evidence, historical incidents, authorized runbooks,
ranked competing hypotheses, and guarded recommendations. Service-health collection is routed
only to authentication and timeout investigations where it can distinguish availability from
the leading cause.

Reports include a chronological timeline built from operational evidence timestamps. Duplicate
transactions cannot enter the automatic reprocessing flow even when diagnosis confidence is
high; they require downstream-ledger reconciliation.

## Consequences

The offline evaluation now contains 16 diagnosis cases and 10 retrieval/ACL cases. These are
synthetic regression cases, not evidence of production accuracy. A future model-backed provider
must pass the same contracts and per-class evaluation before replacing the deterministic
baseline.
