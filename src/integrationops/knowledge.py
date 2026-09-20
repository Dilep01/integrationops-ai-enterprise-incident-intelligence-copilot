from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    version: str
    title: str
    section: str
    content: str
    source_uri: str
    environment: str
    tenant_id: str
    allowed_roles: tuple[str, ...]
    metadata: dict[str, str]


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw.strip()
    parts = raw.split("---", 2)
    if len(parts) != 3:
        return {}, raw.strip()
    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata, parts[2].strip()


def _sections(body: str) -> list[tuple[str, str]]:
    matches = list(HEADING_PATTERN.finditer(body))
    title = matches[0].group(2).strip() if matches else "Untitled"
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        if len(match.group(1)) != 2:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[match.end() : end].strip()
        if content:
            sections.append((match.group(2).strip(), content))
    if not sections:
        plain = HEADING_PATTERN.sub("", body).strip()
        if plain:
            sections.append((title, plain))
    return sections


def _split_content(content: str, max_chars: int = 1200, overlap_chars: int = 160) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + max_chars, len(content))
        if end < len(content):
            boundary = content.rfind(". ", start, end)
            if boundary > start + max_chars // 2:
                end = boundary + 1
        chunks.append(content[start:end].strip())
        if end == len(content):
            break
        start = max(end - overlap_chars, start + 1)
    return [chunk for chunk in chunks if chunk]


def load_knowledge_chunks(knowledge_dir: Path) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        document_id = metadata.get("document_id", path.stem)
        version = metadata.get("version", "unknown")
        title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else document_id
        allowed_roles = tuple(
            role.strip()
            for role in metadata.get("allowed_roles", "integration-engineer").split(",")
            if role.strip()
        )
        for section, section_content in _sections(body):
            for index, content in enumerate(_split_content(section_content)):
                identity = f"{document_id}:{version}:{section}:{index}"
                chunk_id = sha256(identity.encode("utf-8")).hexdigest()[:24]
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        version=version,
                        title=title,
                        section=section,
                        content=content,
                        source_uri=str(path),
                        environment=metadata.get("environment", "production"),
                        tenant_id=metadata.get("tenant_id", "demo-enterprise"),
                        allowed_roles=allowed_roles,
                        metadata=metadata,
                    )
                )
    return chunks
