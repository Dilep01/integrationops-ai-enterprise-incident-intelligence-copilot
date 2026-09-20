---
document_id: payload-validation-runbook
version: 2.2
effective_from: 2026-09-05
system: payment-adapter
environment: production
tenant_id: demo-enterprise
allowed_roles: integration-engineer,support-engineer
---

# Payload Validation Runbook

## Section 2.4: Required fields after contract activation

Contract v3 requires currency on every payment request. Compare producer and consumer contract
versions, validate the corrected payload locally, and retain the original transaction reference
when resubmitting through an approved recovery action.
