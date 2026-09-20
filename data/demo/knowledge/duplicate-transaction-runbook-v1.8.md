---
document_id: duplicate-transaction-runbook
version: 1.8
effective_from: 2026-09-08
system: payment-adapter
environment: production
tenant_id: demo-enterprise
allowed_roles: integration-engineer,support-engineer
---

# Duplicate Transaction Runbook

## Section 6.1: Idempotency lost during retry

Never automatically reprocess a duplicate transaction. Verify the original transaction in the
downstream ledger, preserve the original Idempotency-Key on retries, and reconcile the business
reference before an operator decides whether another submission is safe.
