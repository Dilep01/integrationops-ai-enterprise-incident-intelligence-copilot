# ADR 0009: Two-stage RAG and executable quality gates

## Status

Accepted

## Context

The original hybrid retriever combined deterministic dense hashes and sparse token signals using
reciprocal-rank fusion. It returned the final top-k directly, which left no candidate reranking
stage and allowed one document to occupy multiple result positions.

## Decision

Use a two-stage retrieval pipeline:

1. Qdrant hybrid dense and sparse retrieval produces a larger authorized candidate set.
2. A reranker scores query-document pairs.
3. Exact duplicate content is removed.
4. Per-document limits preserve source diversity before the final top-k is returned.

SentenceTransformers and CrossEncoder adapters are opt-in. Deterministic hashing and lexical
reranking remain available for offline tests. Evaluation now measures source diversity and
duplicate-result rate in addition to Recall@K and MRR.

CI enforces retrieval, diagnosis, grounding, citation, hallucination, and access-control
thresholds. A regression fails the workflow instead of producing a report that must be inspected
manually.

## Consequences

- Real model weights are not required for normal unit tests or CI.
- Candidate generation and reranking can be evaluated independently.
- Cross-encoder reranking improves precision but adds latency proportional to candidate count.
- Model-backed evaluation remains a separate, explicitly invoked benchmark.
