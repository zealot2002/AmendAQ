"""Same-chapter sibling expansion for TOC drill (structured, no vectors).

A single leaf pick (e.g. §5.1 年假) drops sibling rules that share the topic
(e.g. §5.5 年假结转). Expand only leaves whose titles overlap the picked title
or are named by the question — not every sibling in the chapter.
"""

from __future__ import annotations

import re
from typing import Any

from mycs.models import KnowledgeRequirement, KnowledgeSource

_TITLE_TOKENS = re.compile(r"[\u4e00-\u9fff]{2,}")


def titles_share_topic(a: str, b: str) -> bool:
    left = (a or "").strip()
    right = (b or "").strip()
    if len(left) < 2 or len(right) < 2:
        return False
    return left in right or right in left


def select_related_siblings(
    picked: dict[str, Any],
    siblings: list[dict[str, Any]],
    question: str,
) -> list[dict[str, Any]]:
    picked_id = picked.get("node_id")
    picked_title = str(picked.get("title") or "")
    q = question or ""
    related: list[dict[str, Any]] = []
    for node in siblings:
        if node.get("node_id") == picked_id:
            continue
        if node.get("kind") not in (None, "leaf"):
            continue
        title = str(node.get("title") or "")
        if titles_share_topic(picked_title, title):
            related.append(node)
            continue
        if any(tok in q for tok in _TITLE_TOKENS.findall(title)):
            related.append(node)
    return related


def scope_section_refs(picked: dict[str, Any], siblings: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for node in [picked, *siblings]:
        ref = str(node.get("section_ref") or "").strip()
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def section_in_scopes(section_ref: str, scopes: list[str]) -> bool:
    sec = (section_ref or "").strip()
    if not sec or not scopes:
        return False
    for raw in scopes:
        scope = (raw or "").strip()
        if not scope:
            continue
        if sec == scope:
            return True
        pref = scope.rstrip(".")
        if sec == pref or sec.startswith(f"{pref}."):
            return True
    return False


def outline_covers_scopes(
    outline: list[dict[str, Any]],
    scopes: list[str],
) -> list[dict[str, Any]]:
    """Keep scoped leaves and their ancestor chapter nodes (e.g. 5. for 5.1/5.5)."""
    if not scopes:
        return outline
    kept: list[dict[str, Any]] = []
    for node in outline:
        sec = str(node.get("section_ref") or "")
        if section_in_scopes(sec, scopes):
            kept.append(node)
            continue
        chapter = sec if sec.endswith(".") else f"{sec}."
        if any(str(s).startswith(chapter) for s in scopes):
            kept.append(node)
    return kept


def ensure_by_section_requirements(
    requirements: list[KnowledgeRequirement],
    section_refs: list[str],
    *,
    document_id: str | None,
    min_refs: int = 1,
) -> tuple[list[KnowledgeRequirement], int]:
    """Append graph.entity.by_section for each ref not already in the plan."""
    refs = [str(r).strip() for r in section_refs if str(r).strip()]
    if len(refs) < min_refs:
        return requirements, 0
    have = {
        str(r.params.get("section") or "")
        for r in requirements
        if r.field == "graph.entity.by_section"
    }
    added = 0
    out = list(requirements)
    for ref in refs:
        if ref in have:
            continue
        params: dict[str, Any] = {"section": ref}
        if document_id:
            params["document_id"] = document_id
        out.append(
            KnowledgeRequirement(
                field="graph.entity.by_section",
                source=KnowledgeSource.GRAPH,
                params=params,
            )
        )
        added += 1
    return out, added


def ensure_scoped_section_requirements(
    requirements: list[KnowledgeRequirement],
    section_refs: list[str],
    *,
    document_id: str | None,
) -> tuple[list[KnowledgeRequirement], int]:
    """Force by_section for sibling-expanded leaves (>=2 refs)."""
    return ensure_by_section_requirements(
        requirements, section_refs, document_id=document_id, min_refs=2
    )
