# Interview talking points

## Why LangGraph?

The investigation has explicit stages and failure policies: normalize, retrieve, gather operational
facts, diagnose, validate citations, assess evidence sufficiency, and persist. A graph makes state
and allowed transitions visible and testable. It also avoids an unrestricted autonomous loop.

## Why hybrid retrieval plus reranking?

Incident language mixes exact identifiers such as HTTP codes and field names with semantic
descriptions. Sparse retrieval handles exact terms; dense retrieval handles semantic similarity.
Reciprocal-rank fusion combines both candidate lists without assuming comparable raw scores. A
cross-encoder then spends more compute on the small candidate set to improve final ordering.

## Where does authorization happen?

Tenant, environment, and role constraints are stored with chunks and applied inside the Qdrant
query. Filtering only after retrieval could expose unauthorized text to reranking or generation.
The API also derives a request principal from identity headers for the local demo; a real
deployment would accept these claims only from a trusted gateway.

## How do you reduce hallucinations?

The system uses typed output, current-run evidence IDs, citation validation, evidence-sufficiency
rules, a supported-hypothesis requirement, and fail-closed behavior. It can return insufficient
confidence instead of forcing a diagnosis. Prompt injection is rejected and secrets are redacted
before model calls.

## What makes it agentic?

The system selects incident-specific operational tools, combines their outputs with retrieved
knowledge, and follows a controlled state graph. The agent can gather and reason over evidence,
but cannot silently mutate systems. Remediation is a separate human-approved workflow.

## What did the evaluation reveal?

The cross-encoder raised MRR from 0.9375 for the deterministic baseline to 1.0000 on the 10-case
synthetic retrieval benchmark while preserving Recall@K 1.0000. The small `qwen3:1.7b` model
failed the supported-hypothesis gate for one timeout case. The workflow returned insufficient
confidence, showing that the guardrail works when a model response lacks evidence support.

## What would you do next for production?

Use approved historical incidents to create a larger, time-split evaluation set; replace demo
identity headers with gateway-issued claims; add governed connectors and per-tool credentials;
define retention and redaction controls; run concurrency and dependency-failure tests; establish
human review SLAs; and monitor retrieval drift, grounding failures, latency, and cost.

## Honest limitations

- Synthetic evidence and small benchmark datasets
- Local Ollama latency is hardware-dependent
- Mock operational tools and a local remediation target
- Production integrations and production-scale load testing remain out of scope
- Two accepted `qwen3:4b` scenarios, not a complete five-class live-model benchmark
