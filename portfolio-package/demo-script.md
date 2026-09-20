# Four-minute demo script

## 0:00–0:35 — Frame the problem

“A payment integration failed with HTTP 401 immediately after token rotation. Instead of searching
logs, runbooks, service dashboards, and old tickets separately, I give the incident to
IntegrationOps AI. The goal is not to produce a plausible answer. The goal is to produce a
reviewable diagnosis tied to authorized evidence.”

Open the console at `http://127.0.0.1:5173`.

## 0:35–1:35 — Run or open the investigation

Use: `Payment integration failed with HTTP 401 after token rotation.`

For a faster walkthrough, open:
`http://127.0.0.1:5173/?run_id=RUN-FCA7ED625E`

Point out the classification, high confidence, leading hypothesis, rejected outage hypothesis,
and recommended actions.

Say: “The system does not infer high confidence from the HTTP status alone. It combines the
configuration mismatch, failure timing, healthy downstream status, runbook instructions, and a
confirmed prior incident.”

## 1:35–2:15 — Show evidence and provenance

Open the Evidence tab. Show source type, title, excerpt, evidence ID, source ID, and reliability.
Then open Timeline to show that the v8 rotation precedes the first 401 responses.

Say: “Every hypothesis cites evidence IDs from this run. The API validates those references before
returning the report. If a model invents a citation or returns an unsupported conclusion, the
workflow rejects it.”

## 2:15–2:55 — Explain RAG and agents

Open `portfolio-package/assets/architecture.png`.

Say: “The RAG path combines dense and sparse retrieval in Qdrant, fuses candidates, then uses a
cross-encoder for reranking. Tenant, environment, and role filters are applied during retrieval.
In parallel, incident-specific read-only tools gather logs, configuration changes, status, and
incident history. LangGraph controls the sequence and produces a typed report.”

## 2:55–3:25 — Show the action boundary

Scroll to remediation.

Say: “Diagnosis is read-only. Reprocessing is a separate workflow with requester, independent
approver, operator, idempotency key, and audit events. The demo calls only a local runtime
simulator. Duplicate-payment cases are blocked from automatic reprocessing.”

## 3:25–4:00 — Close with evaluation

Say: “I evaluate retrieval separately from answer generation. The real local retrieval pipeline
reached Recall@K and MRR of 1.0 on the included 10-case synthetic benchmark, with zero ACL
failures. The local suite has 45 passing tests and 91.80% coverage. These are regression results,
not production accuracy. The next production step would be evaluating approved historical
incidents and replacing mock adapters with governed connectors.”

## Demo preparation

```powershell
# Terminal 1
$env:INTEGRATION_RUNTIME_API_KEY = "local-demo-key"
integration-runtime

# Terminal 2
$env:INTEGRATIONOPS_LLM_PROVIDER = "ollama"
$env:INTEGRATIONOPS_LLM_MODEL = "qwen3:4b"
$env:INTEGRATIONOPS_LLM_TIMEOUT_SECONDS = "240"
integrationops-api

# Terminal 3
Set-Location apps/web
npm run dev
```

For a predictable live presentation, use the saved report first. A new `qwen3:4b` investigation
may take roughly two minutes on the development laptop.
