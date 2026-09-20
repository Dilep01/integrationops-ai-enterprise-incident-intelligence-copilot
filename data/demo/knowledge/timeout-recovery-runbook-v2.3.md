---
document_id: timeout-recovery-runbook
version: 2.3
effective_from: 2026-08-22
system: payment-adapter
environment: production
tenant_id: demo-enterprise
allowed_roles: integration-engineer,support-engineer
---

# Timeout Recovery Runbook

## Section 3.2: Downstream latency exceeds client timeout

Compare the connector timeout with p95 and p99 downstream latency. If the service remains
available but responses exceed the client deadline, restore the approved timeout through change
control. Check connection-pool saturation and retry only requests confirmed as incomplete.
