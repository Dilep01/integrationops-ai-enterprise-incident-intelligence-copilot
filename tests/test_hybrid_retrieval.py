from pathlib import Path

from qdrant_client import QdrantClient

from integrationops.evaluation import evaluate_retrieval
from integrationops.hybrid_retrieval import (
    CrossEncoderReranker,
    QdrantHybridKnowledgeRetriever,
    SentenceTransformerEmbedder,
)
from integrationops.knowledge import load_knowledge_chunks

ROOT = Path(__file__).parents[1]
KNOWLEDGE_DIR = ROOT / "data" / "demo" / "knowledge"


def _retriever() -> QdrantHybridKnowledgeRetriever:
    retriever = QdrantHybridKnowledgeRetriever(QdrantClient(location=":memory:"))
    assert retriever.ingest_directory(KNOWLEDGE_DIR) >= 11
    return retriever


def test_structure_aware_ingestion_preserves_sections_and_access_metadata() -> None:
    chunks = load_knowledge_chunks(KNOWLEDGE_DIR)

    assert len(chunks) >= 11
    assert any(chunk.section.startswith("Section 4.3") for chunk in chunks)
    assert all(chunk.tenant_id == "demo-enterprise" for chunk in chunks)
    assert all("integration-engineer" in chunk.allowed_roles for chunk in chunks)


def test_hybrid_retrieval_finds_rotation_guidance() -> None:
    results = _retriever().retrieve(
        "HTTP 401 began after the OAuth client secret was rotated",
        environment="production",
        tenant_id="demo-enterprise",
        roles=["integration-engineer"],
        limit=3,
    )

    document_ids = {item.metadata["document_id"] for item in results}
    assert "token-renewal-runbook" in document_ids
    assert "oauth-authentication-guide" in document_ids
    assert all("retrieval_score" in item.metadata for item in results)


def test_retrieval_enforces_tenant_and_role_filters() -> None:
    retriever = _retriever()

    wrong_tenant = retriever.retrieve(
        "HTTP 401 token rotation",
        environment="production",
        tenant_id="another-enterprise",
        roles=["integration-engineer"],
    )
    wrong_role = retriever.retrieve(
        "HTTP 401 token rotation",
        environment="production",
        tenant_id="demo-enterprise",
        roles=["finance-viewer"],
    )

    assert wrong_tenant == []
    assert wrong_role == []


def test_retrieval_evaluation_dataset_passes() -> None:
    result = evaluate_retrieval(
        ROOT / "data" / "evaluation" / "retrieval_cases.jsonl",
        KNOWLEDGE_DIR,
    )

    assert result.case_count == 10
    assert result.recall_at_k == 1.0
    assert result.mean_reciprocal_rank >= 0.75
    assert result.access_control_failures == 0
    assert result.source_diversity == 1.0
    assert result.duplicate_result_rate == 0.0


def test_sentence_transformer_uses_query_and_document_encoders() -> None:
    class FakeEmbeddingModel:
        calls: list[str] = []

        def get_sentence_embedding_dimension(self) -> int:
            return 3

        def encode(self, text, **kwargs):
            del text, kwargs
            raise AssertionError("The generic encoder should not be used.")

        def encode_query(self, text, **kwargs):
            del text, kwargs
            self.calls.append("query")
            return [1.0, 0.0, 0.0]

        def encode_document(self, text, **kwargs):
            del text, kwargs
            self.calls.append("document")
            return [0.0, 1.0, 0.0]

    model = FakeEmbeddingModel()
    embedder = SentenceTransformerEmbedder("fake", model=model)

    assert embedder.dense_query("query") == [1.0, 0.0, 0.0]
    assert embedder.dense_document("document") == [0.0, 1.0, 0.0]
    assert model.calls == ["query", "document"]


def test_cross_encoder_scores_query_candidate_pairs() -> None:
    class FakeCrossEncoder:
        pairs = []

        def predict(self, pairs, **kwargs):
            del kwargs
            self.pairs = pairs
            return [0.2, 0.9]

    candidates = _retriever().retrieve(
        "HTTP 401 token rotation",
        environment="production",
        roles=["integration-engineer"],
        limit=2,
    )
    model = FakeCrossEncoder()

    scores = CrossEncoderReranker("fake", model=model).score("query", candidates)

    assert scores == [0.2, 0.9]
    assert model.pairs[0][0] == "query"


def test_reranking_deduplicates_and_limits_chunks_per_document() -> None:
    class ReverseReranker:
        def score(self, query, candidates):
            del query
            return [float(index) for index, _ in enumerate(candidates)]

    retriever = QdrantHybridKnowledgeRetriever(
        QdrantClient(location=":memory:"),
        reranker=ReverseReranker(),
        candidate_limit=12,
        max_chunks_per_document=1,
    )
    retriever.ingest_directory(KNOWLEDGE_DIR)

    results = retriever.retrieve(
        "HTTP 401 token rotation OAuth",
        environment="production",
        roles=["integration-engineer"],
        limit=3,
    )

    document_ids = [item.metadata["document_id"] for item in results]
    assert len(document_ids) == len(set(document_ids))
    assert all("rerank_score" in item.metadata for item in results)
    assert all(item.metadata["retrieval_method"] == "hybrid_rrf_reranked" for item in results)
