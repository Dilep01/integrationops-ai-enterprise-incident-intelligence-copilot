# Delivery roadmap

Production-only identity, telemetry exporter, SAP, and downstream connector work is intentionally
deferred. The current scope is learning and demonstrating GenAI, agentic workflows, and RAG.

## Phase 1: deterministic vertical slice

- HTTP 401 after client-secret rotation
- Local versioned knowledge retrieval
- Mock read-only operational tools
- Evidence-backed diagnosis and citation validation
- FastAPI endpoint and regression tests

## Phase 2: hybrid RAG

- [x] Structure-aware ingestion
- [x] Qdrant dense and sparse retrieval
- [x] Metadata and ACL filtering
- [x] Reciprocal-rank fusion
- [x] Retrieval evaluation dataset
- [x] Cross-encoder reranking and source diversity tuning

## Phase 3: provider-neutral model integration

- [x] Provider-neutral diagnosis interface
- [x] Structured diagnosis generation
- [x] Evidence sufficiency gate
- [x] Competing hypotheses and contradiction checks
- [x] Hallucinated-citation rejection
- [x] Approval policy for state-changing recommendations
- [x] Prompt and model version tracking
- [x] Validation against a user-selected live model endpoint

## Phase 4: persistence and incident console

- [x] SQLite/PostgreSQL investigation repository
- [x] Durable LangGraph checkpoints
- [x] Tenant-scoped history and report retrieval
- [x] Engineer feedback persistence
- [x] React incident workspace
- [x] Evidence viewer and grounding details
- [x] Expanded multi-event incident timeline

## Phase 5: evaluation, observability, and security

- [x] OpenTelemetry investigation traces
- [x] Local operational metrics
- [x] Offline retrieval and diagnosis evaluation runner
- [x] Tenant isolation and role-based access
- [x] Prompt-injection and data-leakage tests
- [ ] Trusted identity-provider integration for deployment
- [ ] External telemetry exporter configuration for deployment

## Phase 6: approval-gated remediation

- [x] One allow-listed, idempotent action
- [x] Separate human review and approval
- [x] Tenant-scoped action state machine
- [x] Complete action audit trail
- [x] Sandbox execution adapter
- [x] Local HTTP integration-runtime simulator
- [x] Target authentication, retry, timeout, and idempotency contract tests
- [ ] User-selected production connector and downstream idempotency validation

## Phase 7: multi-incident intelligence

- [x] Authentication failure diagnosis
- [x] Timeout diagnosis
- [x] Mapping-error diagnosis
- [x] Invalid-payload diagnosis
- [x] Duplicate-transaction diagnosis
- [x] Incident-specific operational evidence
- [x] Versioned runbooks for every supported class
- [x] Sixteen-case diagnosis evaluation
- [x] Duplicate-payment remediation safety block

## Phase 8: local model validation

- [x] Dedicated Ollama transport
- [x] Schema-constrained diagnosis output
- [x] Deterministic sampling and disabled reasoning traces
- [x] Ollama contract and failure-path tests
- [x] Live authentication and timeout validation with qwen3:4b
- [x] Five-scenario small-model safety-gate smoke test
- [ ] Live five-scenario evaluation with qwen3:4b

## Phase 9: production-style RAG learning pipeline

- [x] SentenceTransformers bi-encoder adapter
- [x] Cross-encoder reranking adapter
- [x] Hybrid candidate generation before reranking
- [x] Duplicate-content removal
- [x] Per-document source diversity
- [x] Diversity and duplicate-rate evaluation metrics
- [x] Live real-model retrieval benchmark

## Phase 10: engineering reliability

- [x] Alembic configuration and initial migration
- [x] SQLite upgrade and downgrade test
- [x] Executable RAG and diagnosis quality thresholds
- [x] GitHub Actions backend checks
- [x] GitHub Actions frontend build and audit
- [x] Docker Compose validation in CI
