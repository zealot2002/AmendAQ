from __future__ import annotations

from typing import Any

from mycs.models import KnowledgeRequirement, KnowledgeSource
from mycs.planning.sibling_expand import ensure_by_section_requirements


def search_hit_sections(context: dict[str, Any], *, top: int = 3) -> list[str]:
    hits = (context.get("graph_catalog") or {}).get("hits") or []
    if not hits:
        hits = list(context.get("graph_entities") or [])[:top]
    refs: list[str] = []
    for h in hits[:top]:
        sec = str(h.get("section") or "").strip()
        score = float(h.get("search_score") or 0)
        if sec and score > 0:
            refs.append(sec)
    return refs


def supplement_requirements_after_search(
    requirements: list[KnowledgeRequirement],
    context: dict[str, Any],
    *,
    document_id: str | None,
) -> tuple[list[KnowledgeRequirement], int]:
    """
    寻址补强：search 已命中实体时，强制补 graph.entity.by_section，避免只搜到分数不落叶。
    """
    refs = search_hit_sections(context)
    if not refs:
        return requirements, 0
    out, added = ensure_by_section_requirements(
        requirements,
        refs,
        document_id=document_id,
        min_refs=1,
    )
    if added:
        for req in out:
            if req.field != "graph.entity.by_section":
                continue
            sec = str(req.params.get("section") or req.params.get("section_ref") or "")
            if sec in refs:
                req.satisfied = False
                req.result = None
    return out, added