---
document_id: invoice-mapping-runbook
version: 3.0
effective_from: 2026-09-01
system: invoice-mapper
environment: production
tenant_id: demo-enterprise
allowed_roles: integration-engineer,support-engineer
---

# Invoice Mapping Runbook

## Section 5.1: Source-field rename

When a mapping fails after a schema release, compare the deployed mapping with the exact source
schema version. Source schema v12 renamed buyer_id to customer_id. Mapping updates require a
regression fixture covering required target fields before failed invoices are reprocessed.
