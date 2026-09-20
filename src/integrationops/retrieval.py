from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from integrationops.models import Evidence, EvidenceSourceType

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]+", re.IGNORECASE)


class KnowledgeRetriever(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        environment: str,
        tenant_id: str = "demo-enterprise",
        roles: list[str] | None = None,
        limit: int = 3,
    ) -> list[Evidence]: ...


@dataclass(frozen=True)
class KnowledgeDocument:
    path: Path
    document_id: str
    version: str
    body: str
    metadata: dict[str, str]


def _tokens(value: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(value)}


def _parse_document(path: Path) -> KnowledgeDocument:
    raw = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    body = raw
    if raw.startswith("---"):
        _, header, body = raw.split("---", 2)
        for line in header.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
    return KnowledgeDocument(
        path=path,
        document_id=metadata.get("document_id", path.stem),
        version=metadata.get("version", "unknown"),
        body=body.strip(),
        metadata=metadata,
    )


class LocalKnowledgeRetriever:
    """Phase 1 retriever with the same evidence contract planned for Qdrant."""

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir

    def retrieve(
        self,
        query: str,
        *,
        environment: str,
        tenant_id: str = "demo-enterprise",
        roles: list[str] | None = None,
        limit: int = 3,
    ) -> list[Evidence]:
        del tenant_id, roles
        query_tokens = _tokens(query)
        ranked: list[tuple[float, KnowledgeDocument]] = []

        for path in self.knowledge_dir.glob("*.md"):
            document = _parse_document(path)
            document_environment = document.metadata.get("environment")
            if document_environment and document_environment != environment:
                continue
            document_tokens = _tokens(document.body)
            overlap = len(query_tokens & document_tokens)
            exact_bonus = (
                4 if "http 401" in query.lower() and "http 401" in document.body.lower() else 0
            )
            rotation_bonus = (
                3 if "rotation" in query.lower() and "rotation" in document.body.lower() else 0
            )
            score = overlap + exact_bonus + rotation_bonus
            if score:
                ranked.append((score, document))

        ranked.sort(key=lambda item: (item[0], item[1].version), reverse=True)
        return [self._to_evidence(document) for _, document in ranked[:limit]]

    @staticmethod
    def _to_evidence(document: KnowledgeDocument) -> Evidence:
        relevant_lines = [
            line.strip()
            for line in document.body.splitlines()
            if line.strip() and not line.startswith("#")
        ]
        excerpt = " ".join(relevant_lines)[:900]
        return Evidence(
            source_type=EvidenceSourceType.DOCUMENT,
            source_id=f"{document.document_id}:v{document.version}",
            title=f"{document.document_id} v{document.version}",
            excerpt=excerpt,
            reliability=0.9,
            source_uri=str(document.path),
            metadata=document.metadata,
        )
