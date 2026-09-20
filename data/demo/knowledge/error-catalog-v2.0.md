---
document_id: integration-error-catalog
version: 2.0
effective_from: 2026-06-15
system: payment-adapter
environment: production
tenant_id: demo-enterprise
allowed_roles: integration-engineer,support-engineer
---

# Integration Error Catalogue

## HTTP 401

HTTP 401 indicates that the downstream service did not accept the supplied authentication credentials. Common causes include an expired token, a token issued with an inactive client secret, an incorrect audience, or an invalid issuer. HTTP 401 alone does not identify which cause occurred.

## HTTP 409

HTTP 409 with a repeated business reference indicates a duplicate or conflicting transaction.
Before any retry, verify the original transaction status and confirm that the original
Idempotency-Key is preserved.

## HTTP 422

HTTP 422 indicates that the payload was syntactically readable but failed contract validation.
Use the returned field errors and the active API contract version to locate missing or invalid
fields.

## HTTP 504 and client timeout

A client timeout can occur while the downstream service remains available. Compare the configured
timeout with observed downstream latency before treating the event as an outage.

## Transformation failure

A transformation failure after a schema deployment usually indicates that the mapping references
a renamed, removed, or type-incompatible source field. Validate the deployed mapping against the
exact source and target schema versions.
