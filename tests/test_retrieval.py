from pathlib import Path

from integrationops.models import EvidenceSourceType
from integrationops.retrieval import LocalKnowledgeRetriever


def test_retrieval_prioritizes_rotation_guidance() -> None:
    knowledge_dir = Path(__file__).parents[1] / "data" / "demo" / "knowledge"
    retriever = LocalKnowledgeRetriever(knowledge_dir)

    results = retriever.retrieve(
        "Payment integration failed with HTTP 401 after token rotation",
        environment="production",
        limit=3,
    )

    assert len(results) == 3
    assert all(item.source_type == EvidenceSourceType.DOCUMENT for item in results)
    assert any("client secret" in item.excerpt.lower() for item in results)
    assert any(item.metadata.get("version") == "4.1" for item in results)
