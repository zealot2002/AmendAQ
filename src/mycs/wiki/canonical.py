from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mycs.wiki.outline import OutlineNode


@dataclass
class CanonicalEvidence:
    quote: str
    source_uri: str = ""
    effective_from: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> CanonicalEvidence:
        raw = raw or {}
        return cls(
            quote=str(raw.get("quote") or ""),
            source_uri=str(raw.get("source_uri") or ""),
            effective_from=str(raw.get("effective_from") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "quote": self.quote,
            "source_uri": self.source_uri,
            "effective_from": self.effective_from,
        }


@dataclass
class CanonicalChapter:
    section_ref: str
    title: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CanonicalChapter:
        return cls(
            section_ref=str(raw.get("section_ref") or "").strip(),
            title=str(raw.get("title") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"section_ref": self.section_ref, "title": self.title}


@dataclass
class CanonicalLeaf:
    section_ref: str
    parent_ref: str
    title: str
    summary: str
    body: str
    evidence: CanonicalEvidence = field(default_factory=CanonicalEvidence)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CanonicalLeaf:
        return cls(
            section_ref=str(raw.get("section_ref") or "").strip(),
            parent_ref=str(raw.get("parent_ref") or "").strip(),
            title=str(raw.get("title") or "").strip(),
            summary=str(raw.get("summary") or "").strip(),
            body=str(raw.get("body") or "").strip(),
            evidence=CanonicalEvidence.from_dict(raw.get("evidence")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_ref": self.section_ref,
            "parent_ref": self.parent_ref,
            "title": self.title,
            "summary": self.summary,
            "body": self.body,
            "evidence": self.evidence.to_dict(),
        }


@dataclass
class WikiCanonicalDraft:
    """LLM / rules compiler output aligned with wiki_toc_node + kg_entity."""

    document_title: str
    chapters: list[CanonicalChapter] = field(default_factory=list)
    leaves: list[CanonicalLeaf] = field(default_factory=list)
    ingest_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": {"title": self.document_title},
            "chapters": [c.to_dict() for c in self.chapters],
            "leaves": [lf.to_dict() for lf in self.leaves],
            "ingest_notes": list(self.ingest_notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WikiCanonicalDraft:
        doc = data.get("document") or {}
        title = str(doc.get("title") or data.get("document_title") or "Document")
        chapters = [CanonicalChapter.from_dict(c) for c in data.get("chapters") or []]
        leaves = [CanonicalLeaf.from_dict(lf) for lf in data.get("leaves") or []]
        notes = [str(n) for n in data.get("ingest_notes") or []]
        return cls(document_title=title, chapters=chapters, leaves=leaves, ingest_notes=notes)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _quote_in_body(quote: str, body: str) -> bool:
    if not body:
        return False
    q = (quote or "").strip()
    if not q:
        return True
    if q in body:
        return True
    return _norm_ws(q) in _norm_ws(body)


def validate_canonical(
    draft: WikiCanonicalDraft,
    *,
    source_text: str | None = None,
    min_coverage: float | None = None,
) -> list[str]:
    """Deterministic checks before SQLite persist."""
    errors: list[str] = []
    if not draft.chapters:
        errors.append("chapters: empty")
    if not draft.leaves:
        errors.append("leaves: empty")

    ch_refs: set[str] = set()
    for c in draft.chapters:
        ch_refs.add(c.section_ref)
        ch_refs.add(c.section_ref.rstrip("."))
    if len({c.section_ref for c in draft.chapters}) != len(draft.chapters):
        errors.append("chapters: duplicate section_ref")

    leaf_refs: set[str] = set()
    for lf in draft.leaves:
        if not lf.section_ref:
            errors.append("leaf: missing section_ref")
            continue
        if lf.section_ref in leaf_refs:
            errors.append(f"leaf: duplicate section_ref {lf.section_ref}")
        leaf_refs.add(lf.section_ref)
        if not lf.body.strip():
            errors.append(f"leaf {lf.section_ref}: empty body")
        elif not _quote_in_body(lf.evidence.quote, lf.body):
            errors.append(f"leaf {lf.section_ref}: evidence.quote not substring of body")
        if lf.parent_ref and lf.parent_ref not in ch_refs:
            errors.append(f"leaf {lf.section_ref}: unknown parent_ref {lf.parent_ref}")

    for ch in draft.chapters:
        if not ch.section_ref or not ch.title:
            errors.append(f"chapter {ch.section_ref!r}: missing ref or title")

    if source_text and min_coverage is not None and min_coverage > 0:
        joined = " ".join(lf.body for lf in draft.leaves)
        if len(_norm_ws(joined)) < min_coverage * len(_norm_ws(source_text)):
            errors.append(
                f"coverage: compiled body too short vs source (threshold {min_coverage})"
            )

    return errors


def canonical_to_outline_roots(draft: WikiCanonicalDraft) -> list[OutlineNode]:
    """Map compiler JSON to chapter → leaf OutlineNode tree."""
    ch_by_ref: dict[str, OutlineNode] = {}
    roots: list[OutlineNode] = []

    for ch in draft.chapters:
        ref = ch.section_ref.rstrip(".")
        num = ref.split(".")[0] if ref else str(len(roots) + 1)
        node = OutlineNode(
            node_key=f"ch_{ref.replace('.', '_')}",
            kind="chapter",
            section_ref=ch.section_ref if ch.section_ref.endswith(".") else f"{ch.section_ref}.",
            title=ch.title,
            chapter_num=num,
        )
        ch_by_ref[ch.section_ref.rstrip(".")] = node
        ch_by_ref[ch.section_ref] = node
        roots.append(node)

    for lf in draft.leaves:
        parent = ch_by_ref.get(lf.parent_ref.rstrip(".")) or ch_by_ref.get(lf.parent_ref)
        if not parent and roots:
            parent = roots[-1]
        if not parent:
            continue
        leaf = OutlineNode(
            node_key=f"sec_{lf.section_ref.replace('.', '_')}",
            kind="leaf",
            section_ref=lf.section_ref,
            title=lf.title,
            body=lf.body,
            summary=lf.summary or lf.title,
            chapter_num=parent.chapter_num,
        )
        parent.children.append(leaf)

    for ch in roots:
        ch.children.sort(key=lambda n: _sort_ref(n.section_ref))
    roots.sort(key=lambda n: _sort_ref(n.section_ref))
    return roots


def leaf_evidence_quotes(draft: WikiCanonicalDraft) -> dict[str, str]:
    out: dict[str, str] = {}
    for lf in draft.leaves:
        q = (lf.evidence.quote or lf.body[:500]).strip()
        out[lf.section_ref] = q
    return out


def _sort_ref(ref: str) -> tuple[int, ...]:
    parts = [p for p in ref.replace(".", " ").split() if p.isdigit()]
    return tuple(int(p) for p in parts) if parts else (0,)