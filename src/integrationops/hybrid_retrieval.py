from __future__ import annotations

import math
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from integrationops.knowledge import KnowledgeChunk, load_knowledge_chunks
from integrationops.models import Evidence, EvidenceSourceType

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]+", re.IGNORECASE)


def _tokens(value: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(value)]


class DenseEmbedder(Protocol):
    dimensions: int

    def dense_document(self, text: str) -> list[float]: ...

    def dense_query(self, text: str) -> list[float]: ...


class Reranker(Protocol):
    def score(self, query: str, candidates: list[Evidence]) -> list[float]: ...


class HashingEmbedder:
    """Deterministic offline embedder used for reproducible local tests.

    Production deployments can replace this adapter with a SentenceTransformers
    implementation without changing the retriever or evidence contracts.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def dense(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token, count in Counter(_tokens(text)).items():
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def dense_document(self, text: str) -> list[float]:
        return self.dense(text)

    def dense_query(self, text: str) -> list[float]:
        return self.dense(text)

    def sparse(self, text: str) -> models.SparseVector:
        weights: dict[int, float] = {}
        for token, count in Counter(_tokens(text)).items():
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big")
            weights[index] = weights.get(index, 0.0) + 1.0 + math.log(count)
        ordered = sorted(weights.items())
        return models.SparseVector(
            indices=[index for index, _ in ordered],
            values=[value for _, value in ordered],
        )


class SentenceTransformerEmbedder:
    """Bi-encoder adapter with distinct query and document encoding paths."""

    def __init__(self, model_name: str, *, model: Any | None = None) -> None:
        if model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "SentenceTransformers is not installed. Install the 'rag' extra."
                ) from exc
            model = SentenceTransformer(model_name, trust_remote_code=False)
        self.model = model
        dimension_getter = getattr(self.model, "get_embedding_dimension", None)
        if dimension_getter is None:
            dimension_getter = getattr(self.model, "get_sentence_embedding_dimension", None)
        if dimension_getter is None:
            raise ValueError("The embedding model does not expose a dimension method.")
        dimensions = dimension_getter()
        if dimensions is None:
            raise ValueError("The embedding model did not report its vector dimensions.")
        self.dimensions = int(dimensions)

    @staticmethod
    def _as_list(vector: Any) -> list[float]:
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        return [float(value) for value in values]

    def dense_document(self, text: str) -> list[float]:
        encoder = getattr(self.model, "encode_document", self.model.encode)
        vector = encoder(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return self._as_list(vector)

    def dense_query(self, text: str) -> list[float]:
        encoder = getattr(self.model, "encode_query", self.model.encode)
        vector = encoder(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return self._as_list(vector)

    def sparse(self, text: str) -> models.SparseVector:
        return HashingEmbedder().sparse(text)


class LexicalReranker:
    """Fast deterministic reranker retained for offline tests and comparison."""

    def score(self, query: str, candidates: list[Evidence]) -> list[float]:
        query_tokens = set(_tokens(query))
        scores: list[float] = []
        for candidate in candidates:
            candidate_tokens = set(_tokens(f"{candidate.title} {candidate.excerpt}"))
            union = query_tokens | candidate_tokens
            scores.append(len(query_tokens & candidate_tokens) / len(union) if union else 0.0)
        return scores


class CrossEncoderReranker:
    """Pairwise relevance scorer applied only to the hybrid candidate set."""

    def __init__(self, model_name: str, *, model: Any | None = None) -> None:
        if model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError(
                    "SentenceTransformers is not installed. Install the 'rag' extra."
                ) from exc
            model = CrossEncoder(model_name, trust_remote_code=False)
        self.model = model

    def score(self, query: str, candidates: list[Evidence]) -> list[float]:
        pairs = [(query, f"{item.title}\n{item.excerpt}") for item in candidates]
        if not pairs:
            return []
        scores = self.model.predict(
            pairs,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        values = scores.tolist() if hasattr(scores, "tolist") else list(scores)
        return [float(value) for value in values]


class QdrantHybridKnowledgeRetriever:
    def __init__(
        self,
        client: QdrantClient,
        *,
        collection_name: str = "integrationops_knowledge",
        embedder: DenseEmbedder | None = None,
        reranker: Reranker | None = None,
        candidate_limit: int = 12,
        max_chunks_per_document: int = 1,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.embedder = embedder or HashingEmbedder()
        self.reranker = reranker
        self.candidate_limit = candidate_limit
        self.max_chunks_per_document = max_chunks_per_document

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=self.embedder.dimensions,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={"sparse": models.SparseVectorParams()},
        )

    def ingest(self, chunks: list[KnowledgeChunk]) -> int:
        self.ensure_collection()
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector={
                    "dense": self.embedder.dense_document(self._searchable_text(chunk)),
                    "sparse": self.embedder.sparse(self._searchable_text(chunk)),
                },
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "version": chunk.version,
                    "title": chunk.title,
                    "section": chunk.section,
                    "content": chunk.content,
                    "source_uri": chunk.source_uri,
                    "environment": chunk.environment,
                    "tenant_id": chunk.tenant_id,
                    "allowed_roles": list(chunk.allowed_roles),
                    "metadata": chunk.metadata,
                },
            )
            for chunk in chunks
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(points)

    def ingest_directory(self, knowledge_dir: Path) -> int:
        return self.ingest(load_knowledge_chunks(knowledge_dir))

    def retrieve(
        self,
        query: str,
        *,
        environment: str,
        tenant_id: str = "demo-enterprise",
        roles: list[str] | None = None,
        limit: int = 3,
    ) -> list[Evidence]:
        roles = roles or ["integration-engineer"]
        if not roles:
            return []
        access_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="environment", match=models.MatchValue(value=environment)
                ),
                models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
                models.FieldCondition(key="allowed_roles", match=models.MatchAny(any=roles)),
            ]
        )
        candidate_limit = max(self.candidate_limit, limit)
        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=self.embedder.dense_query(query),
                    using="dense",
                    filter=access_filter,
                    limit=candidate_limit,
                ),
                models.Prefetch(
                    query=self.embedder.sparse(query),
                    using="sparse",
                    filter=access_filter,
                    limit=candidate_limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=candidate_limit,
            with_payload=True,
        )
        candidates = [self._to_evidence(point) for point in response.points]
        return self._rerank_and_diversify(query, candidates, limit)

    def _rerank_and_diversify(
        self,
        query: str,
        candidates: list[Evidence],
        limit: int,
    ) -> list[Evidence]:
        if self.reranker is not None:
            scores = self.reranker.score(query, candidates)
            if len(scores) != len(candidates):
                raise ValueError("Reranker returned a different number of scores than candidates.")
            rescored: list[Evidence] = []
            for candidate, score in zip(candidates, scores, strict=True):
                metadata = {
                    **candidate.metadata,
                    "rerank_score": score,
                    "retrieval_method": "hybrid_rrf_reranked",
                }
                rescored.append(candidate.model_copy(update={"metadata": metadata}))
            candidates = [
                candidate
                for _, candidate in sorted(
                    zip(scores, rescored, strict=True),
                    key=lambda item: item[0],
                    reverse=True,
                )
            ]

        selected: list[Evidence] = []
        seen_content: set[str] = set()
        per_document: Counter[str] = Counter()
        for candidate in candidates:
            normalized_content = " ".join(candidate.excerpt.lower().split())
            document_id = str(candidate.metadata.get("document_id", candidate.source_id))
            if normalized_content in seen_content:
                continue
            if per_document[document_id] >= self.max_chunks_per_document:
                continue
            seen_content.add(normalized_content)
            per_document[document_id] += 1
            selected.append(candidate)
            if len(selected) == limit:
                break
        return selected

    @staticmethod
    def _searchable_text(chunk: KnowledgeChunk) -> str:
        return f"{chunk.title}\n{chunk.section}\n{chunk.content}"

    @staticmethod
    def _to_evidence(point: models.ScoredPoint) -> Evidence:
        payload = point.payload or {}
        document_id = str(payload.get("document_id", "unknown"))
        version = str(payload.get("version", "unknown"))
        section = str(payload.get("section", "unknown"))
        metadata = dict(payload.get("metadata", {}))
        metadata.update(
            {
                "document_id": document_id,
                "chunk_id": str(payload.get("chunk_id", "unknown")),
                "version": version,
                "section": section,
                "retrieval_score": point.score,
            }
        )
        return Evidence(
            source_type=EvidenceSourceType.DOCUMENT,
            source_id=f"{document_id}:v{version}:{section}",
            title=f"{payload.get('title', document_id)} — {section}",
            excerpt=str(payload.get("content", "")),
            reliability=0.9,
            source_uri=str(payload.get("source_uri", "")) or None,
            metadata=metadata,
        )


def build_demo_hybrid_retriever(knowledge_dir: Path) -> QdrantHybridKnowledgeRetriever:
    from integrationops.config import get_settings

    settings = get_settings()
    if settings.embedding_provider == "sentence_transformer":
        embedder: DenseEmbedder = SentenceTransformerEmbedder(settings.embedding_model)
    elif settings.embedding_provider == "hashing":
        embedder = HashingEmbedder()
    else:
        raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")

    if settings.reranker_provider == "cross_encoder":
        reranker: Reranker | None = CrossEncoderReranker(settings.reranker_model)
    elif settings.reranker_provider == "lexical":
        reranker = LexicalReranker()
    elif settings.reranker_provider == "none":
        reranker = None
    else:
        raise ValueError(f"Unsupported reranker provider: {settings.reranker_provider}")

    retriever = QdrantHybridKnowledgeRetriever(
        QdrantClient(location=":memory:"),
        collection_name=settings.qdrant_collection,
        embedder=embedder,
        reranker=reranker,
        candidate_limit=settings.retrieval_candidate_limit,
        max_chunks_per_document=settings.retrieval_max_chunks_per_document,
    )
    retriever.ingest_directory(knowledge_dir)
    return retriever
