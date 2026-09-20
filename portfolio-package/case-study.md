# IntegrationOps AI

## The problem

An HTTP 401 in an invoice-to-payment flow rarely explains itself. An engineer may need to compare
application logs, the latest secret rotation, downstream service health, an OAuth guide, a
runbook, and a similar resolved incident. A generic chatbot can produce a plausible answer, but
plausibility is not enough for operational work. The diagnosis must show which evidence supports
it, respect access rules, expose uncertainty, and keep state-changing actions under human control.

## What I built

IntegrationOps AI is a local incident intelligence platform for five common integration failures:
authentication, timeout, mapping, invalid payload, and duplicate transaction. A React console
sends the incident to a FastAPI service. A controlled LangGraph workflow normalizes the request,
routes read-only tools, retrieves relevant knowledge, builds ranked hypotheses, validates every
citation, and returns a typed incident report.

The example authentication investigation correlates five evidence types. It finds that secret
version v8 became active while the adapter still referenced v7, connects the timing to 17 HTTP 401
responses, confirms that the bank endpoint is reachable, retrieves the token-rotation runbook,
and links a resolved incident with the same cause. The result rejects the outage hypothesis and
recommends a sequence that includes approval before token replacement or transaction reprocessing.

## Why this is more than a chatbot

The workflow separates retrieval, operational facts, diagnosis, and action. Read-only tools expose
logs, configuration changes, service status, and incident history. The model does not receive an
unrestricted tool loop. Its output must match a Pydantic schema and cite evidence IDs from the
current investigation. Invented citations, malformed output, insufficient support, or an
unavailable model cause the workflow to fail closed.

Authorization is part of retrieval. Tenant, environment, and role metadata are applied in the
Qdrant filter before results reach the model. Prompt-injection patterns are rejected and likely
secrets are redacted at the model boundary.

## RAG design

Documents are parsed into section-aware chunks with version, effective date, system, environment,
tenant, role, and source metadata. The production-shaped local path uses:

1. `all-MiniLM-L6-v2` dense embeddings.
2. Qdrant dense and sparse candidate search.
3. Reciprocal-rank fusion.
4. `ms-marco-MiniLM-L-6-v2` cross-encoder reranking.
5. Exact-content deduplication and one-result-per-document diversity.

The real-model retrieval run reached Recall@K 1.0000 and MRR 1.0000 on the included 10-case
synthetic regression dataset, with zero access-control failures. The deterministic baseline keeps
tests fast and reproducible.

## Agentic workflow and safety

The agent graph uses incident-specific routing instead of calling every tool for every query.
Diagnosis and remediation are deliberately separate. The only state-changing example,
`reprocess_failed_transaction`, requires a requester, an independent approver, and an operator.
Execution requires an idempotency key and targets only the included Integration Runtime Simulator.
Every transition is recorded in an audit log. Duplicate-payment incidents are excluded from
automatic reprocessing until downstream reconciliation occurs.

## Evaluation and engineering quality

The repository includes separate diagnosis and retrieval fixtures, retrieval metrics, grounding
checks, citation validation, access-control tests, latency/token/cost fields, and executable
thresholds. The local quality run passed 45 tests with 91.80% Python coverage. Ruff, frontend
type-checking, frontend build, npm audit, database migration cycles, and Docker Compose validation
also passed locally.

The GitHub Actions workflow repeats these gates on push and pull requests. The latest remote
result is available on the repository Actions page.

## Local model result

Ollama keeps the demo credential-free. On the development laptop, `qwen3:4b` produced accepted,
grounded authentication and timeout reports in 108–152 seconds. The smaller `qwen3:1.7b` passed
four of five smoke scenarios; its timeout response was rejected by the support gate. This shows
that the safety policy remained stricter than the desire to always return an answer.

## Current boundary

This is a learning and portfolio system, not a deployed operations product. All enterprise
evidence is synthetic, operational tools are mock adapters, and remediation reaches only a local
simulator. A production version would need trusted identity propagation, secret management,
connector-specific authorization, data-retention controls, load and failure testing, and
evaluation on approved historical incidents.
