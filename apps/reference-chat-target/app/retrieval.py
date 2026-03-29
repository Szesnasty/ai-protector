"""Minimal keyword-based retrieval over a local knowledge base."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

_KB_PATH = pathlib.Path(__file__).parent / "data" / "kb.json"


@dataclass(frozen=True, slots=True)
class KBDocument:
    id: str
    title: str
    body: str
    tags: list[str]


_kb_docs: list[KBDocument] = []


def load_kb() -> None:
    global _kb_docs
    if not _KB_PATH.exists():
        _kb_docs = []
        return
    with open(_KB_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    _kb_docs = [
        KBDocument(id=d["id"], title=d["title"], body=d["body"], tags=d["tags"])
        for d in raw
    ]


def retrieve(query: str, top_k: int = 3) -> list[KBDocument]:
    """Score documents by naive keyword overlap and return top-k."""
    if not _kb_docs:
        return []
    query_tokens = set(query.lower().split())
    scored: list[tuple[float, KBDocument]] = []
    for doc in _kb_docs:
        doc_tokens = (
            set(doc.body.lower().split())
            | set(doc.title.lower().split())
            | {t.lower() for t in doc.tags}
        )
        overlap = len(query_tokens & doc_tokens)
        if overlap > 0:
            scored.append((overlap, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def format_context(docs: list[KBDocument]) -> str:
    if not docs:
        return ""
    parts = ["[Retrieval Context]"]
    for doc in docs:
        parts.append(f"--- {doc.title} (id: {doc.id}) ---\n{doc.body}")
    return "\n\n".join(parts)
