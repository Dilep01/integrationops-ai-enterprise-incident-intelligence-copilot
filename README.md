# IntegrationOps AI

IntegrationOps AI is an evidence-grounded incident intelligence copilot for enterprise API and integration failures. It combines deterministic investigation workflows, retrieval, read-only operational tools, citation validation, and explicit uncertainty handling.

This repository contains a local, credential-free implementation through Phase 10. It investigates
authentication failures, timeouts, mapping errors, invalid payloads, and duplicate transactions
using synthetic enterprise evidence.

## Implemented in Phase 1

- Typed incident, evidence, hypothesis, and report contracts
- A controlled LangGraph investigation workflow
- Mock log, configuration-change, service-status, and incident-history tools
- Structure-aware document ingestion
- Qdrant dense and sparse retrieval with reciprocal-rank fusion
- Tenant, environment, and role filters applied during retrieval
- Ranked hypotheses with supporting and contradicting evidence
- Citation integrity validation
- Provider-neutral structured diagnosis engine
- Evidence-sufficiency and model-grounding policies
- Approval enforcement for state-changing recommendations
- FastAPI endpoints and automated tests
- Docker Compose definitions for the API, PostgreSQL, and Qdrant
- Durable LangGraph checkpoints and SQL investigation history
- React incident console with evidence and feedback views
- Request-context tenant isolation and role-based authorization
- Prompt-injection rejection and model-boundary secret redaction
- OpenTelemetry investigation spans and local operational metrics
- Offline retrieval and diagnosis evaluation datasets
- Four-eyes remediation approval with durable action audit events
- One allow-listed, idempotent transaction-reprocessing action through a sandbox adapter
- Separate local Integration Runtime Simulator with API-key authentication
- HTTP remediation adapter with bounded retries and failure auditing
- Incident-specific tool routing and deterministic diagnosis policies
- Chronological operational evidence timeline
- Versioned runbooks for all five supported incident classes
- Local Ollama diagnosis with schema-constrained output
- SentenceTransformers embeddings and cross-encoder reranking
- Retrieval deduplication, source diversity, and executable evaluation thresholds
- Alembic schema migrations and GitHub Actions quality gates

## Run locally

Python 3.11 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn integrationops.api:app --reload
```

Open `http://127.0.0.1:8000/docs`, or run the demo:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/investigations `
  -ContentType application/json `
  -Body '{"message":"Payment integration failed with HTTP 401 after token rotation.","environment":"production"}'
```

Run checks:

```powershell
pytest
ruff check .
integrationops-evaluate
integrationops-evaluate --enforce
```

The offline benchmark currently contains 16 diagnosis cases and 10 retrieval/ACL cases. These
small synthetic datasets are regression fixtures; their scores must not be interpreted as
production accuracy.

Example incident messages:

```text
Payment integration failed with HTTP 401 after token rotation.
Bank API requests timed out after the client timeout was reduced.
Invoice mapping failed after buyer_id was renamed to customer_id.
HTTP 422 invalid payload is missing required currency.
Duplicate transaction after retry lost the Idempotency-Key.
```

Run the web console in a second terminal:

```powershell
Set-Location apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The Vite development server proxies API calls to FastAPI on port `8000`.

The local web console sends the demo tenant and role headers. In a deployment, a trusted
identity-aware gateway must replace these demo values with verified claims and strip any
caller-supplied identity headers.

The metrics snapshot is available at GET /api/v1/metrics. OpenTelemetry spans are created
locally but are not exported until an approved deployment explicitly configures an exporter.

## Docker

```powershell
docker compose up --build
```

The console runs on port `3000`, the API on `8000`, the Integration Runtime Simulator on
`8081`, Qdrant on `6333`, and PostgreSQL on `5432`. Docker Compose automatically selects
the local HTTP remediation provider and uses `local-demo-key` as an explicit development-only
credential. Override `INTEGRATION_RUNTIME_API_KEY` in your local environment when desired.

Local runs use `.data/integrationops.db` for investigation history and `.data/checkpoints.sqlite3` for LangGraph checkpoints. Docker switches investigation storage to PostgreSQL and keeps checkpoints on a named volume.

## Local remediation target

The normal Python default remains `INTEGRATIONOPS_REMEDIATION_PROVIDER=sandbox`. To exercise
the real local HTTP boundary without Docker, start the target in one terminal:

```powershell
$env:INTEGRATION_RUNTIME_API_KEY = "local-demo-key"
integration-runtime
```

Then start IntegrationOps in another terminal:

```powershell
$env:INTEGRATIONOPS_REMEDIATION_PROVIDER = "local_http"
$env:INTEGRATIONOPS_REMEDIATION_BASE_URL = "http://127.0.0.1:8081"
$env:INTEGRATIONOPS_REMEDIATION_API_KEY = "local-demo-key"
integrationops-api
```

These values are local demonstration settings. Do not reuse them for a deployed environment.

## Safety boundary

Operational investigation tools remain read-only. Phase 6 adds one approval-gated remediation
action, reprocess_failed_transaction. Local execution calls only the included Integration
Runtime Simulator and does not call SAP, a bank API, or another external system. The requester
cannot approve the action, execution
requires an operator role and idempotency key, and each transition is written to the audit log.
Duplicate-transaction investigations are excluded from automatic reprocessing because the
original payment must first be reconciled with the downstream ledger.

## Retrieval modes

The application uses an embedded Qdrant instance by default, allowing hybrid retrieval and ACL
tests to run without Docker. The default hashing embedder and lexical reranker keep tests fast and
reproducible.

Install and enable the real local retrieval models with:

```powershell
python -m pip install -e ".[dev,rag]"
$env:INTEGRATIONOPS_EMBEDDING_PROVIDER = "sentence_transformer"
$env:INTEGRATIONOPS_RERANKER_PROVIDER = "cross_encoder"
integrationops-evaluate --enforce
```

The first stage combines dense and sparse candidates through reciprocal-rank fusion. The second
stage uses a cross-encoder to score query-document pairs, removes duplicate content, and limits
repeated chunks from one document. The real-model benchmark reached Recall@K 1.0, MRR 1.0,
source diversity 1.0, duplicate rate 0, and zero ACL failures on the synthetic dataset. See
[the RAG validation record](docs/evaluation/rag-live-validation.md).

## Database migrations

Local tests may create ephemeral schemas directly. Versioned databases should use Alembic:

```powershell
alembic upgrade head
alembic current
```

The initial migration supports SQLite and PostgreSQL-compatible SQLAlchemy schemas. CI verifies
upgrade, downgrade, and re-upgrade behavior.

## Diagnosis providers

`INTEGRATIONOPS_LLM_PROVIDER=mock` is the safe offline default. It uses the same typed result contract and safety policies as a model-backed run. Set the provider to `openai_compatible` to use an approved endpoint that implements `/chat/completions`, then configure `INTEGRATIONOPS_LLM_BASE_URL`, `INTEGRATIONOPS_LLM_MODEL`, and optionally `INTEGRATIONOPS_LLM_API_KEY`.

To use a locally installed Ollama model without an API key:

```powershell
$env:INTEGRATIONOPS_LLM_PROVIDER = "ollama"
$env:INTEGRATIONOPS_LLM_MODEL = "qwen3:4b"
$env:INTEGRATIONOPS_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:INTEGRATIONOPS_LLM_TIMEOUT_SECONDS = "240"
integrationops-api
```

Ollama receives the full diagnosis JSON schema, deterministic sampling settings, and
`think=false`. The deterministic provider remains the default so tests and offline use do not
depend on a running model server. When the API runs inside Docker on Windows, use
`http://host.docker.internal:11434` for `INTEGRATIONOPS_OLLAMA_BASE_URL`.

On the development laptop, `qwen3:4b` produced grounded, high-confidence results for the
authentication and timeout smoke cases, but required 108-152 seconds per request. The smaller
`qwen3:1.7b` was faster, but one of five incident classes failed the supported-hypothesis gate.
Use 4B for the portfolio demo and retain the deterministic provider for fast regression tests.
See [the live validation record](docs/evaluation/ollama-live-validation.md).

Model responses are accepted only when they match the diagnosis schema and cite evidence from the current investigation. The system fails closed if the endpoint is unavailable, returns malformed JSON, or invents an evidence identifier.

See [the architecture decisions](docs/architecture/0001-controlled-investigation-workflow.md) and [the delivery plan](docs/architecture/roadmap.md).

## Portfolio handoff

The self-contained [portfolio package](portfolio-package/README.md) includes verified project
copy, structured metadata, resume and interview material, architecture artwork, and real local
application screenshots. Repository and hosted-demo links remain unset until publication.
