# ADR 0006: local HTTP integration-runtime target

Status: accepted

## Context

The Phase 6 sandbox adapter proved the approval state machine but did not cross a real service
boundary. Buying or connecting to SAP Integration Suite is unnecessary for a portfolio
demonstration and would introduce external credentials and side effects.

## Decision

Run a separate Integration Runtime Simulator as a FastAPI service on port 8081. The service:

- authenticates requests with a development-only API key;
- requires an idempotency key;
- stores one result per transaction and idempotency-key pair;
- returns the same result for a replay;
- exposes transaction execution history;
- supports controlled timeout and HTTP 500 behavior for tests.

IntegrationOps uses a provider-neutral HTTP remediation adapter with a bounded timeout and three
attempts for transport and server failures. It does not retry HTTP 401 responses. Target-system
failures leave the approved action recoverable and append an execution_failed audit event.

The default provider remains sandbox for direct local Python runs. Docker Compose selects the
local_http provider and supplies the same development key to both services. The committed key is
an explicit local-demo value, not a production secret.

## Consequences

The project now demonstrates an actual network integration, authentication failure behavior,
retry exhaustion, idempotent replay, and failure auditing without paid infrastructure. A future
SAP or internal-runtime adapter can implement the same interface and configuration boundary.
