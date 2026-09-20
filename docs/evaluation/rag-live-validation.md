# Real-model RAG validation

Date: 2026-09-20

The benchmark ran locally with:

- Dense model: `sentence-transformers/all-MiniLM-L6-v2`
- Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Candidate fusion: Qdrant reciprocal-rank fusion over dense and sparse retrieval
- Final selection: cross-encoder score, exact-content deduplication, and one chunk per document

No API key or paid endpoint was used. Public model checkpoints were downloaded once and cached
locally.

## Results

| Metric | Result |
| --- | ---: |
| Retrieval cases | 10 |
| Recall@K | 1.0000 |
| Mean reciprocal rank | 1.0000 |
| Source diversity | 1.0000 |
| Duplicate result rate | 0.0000 |
| Access-control failures | 0 |

The dataset is intentionally small and synthetic. These values are regression results for the
included incident classes and must not be described as production accuracy.

## Comparison

The deterministic hashing and lexical baseline achieved Recall@K 1.0000 and MRR 0.9375. The real
embedding and reranking pipeline preserved recall and moved the expected source to rank one in
every scored case, increasing MRR to 1.0000.
