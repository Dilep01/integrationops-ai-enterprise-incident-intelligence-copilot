# ADR 0005: approval-gated remediation

Status: accepted for Phase 6

## Context

Diagnosis recommendations can include state-changing recovery steps. Allowing a model or a
single engineer to execute those steps directly would create an unacceptable automation and
segregation-of-duties risk.

## Decision

The first remediation capability supports exactly one allow-listed action:
reprocess_failed_transaction.

The action follows a persisted state machine:

1. An integration or support engineer requests the action for one explicit transaction.
2. A different user with the remediation-approver role approves or rejects it.
3. A remediation operator executes an approved action with an idempotency key.
4. Every accepted transition and idempotent replay creates an audit event.

Requests are allowed only for high-confidence investigations whose citations passed validation.
Tenant identity comes from the request context. The sandbox adapter never calls SAP, a bank,
or another external system. Its execution reference is deterministically derived from the
transaction reference and idempotency key.

## Consequences

The local console can demonstrate the complete approval flow without credentials or external
side effects. A production connector must preserve the same contracts, enforce idempotency at
the downstream system, use a trusted identity provider, protect concurrent execution with a
distributed transaction or lock, and export audit events to the enterprise audit platform.
