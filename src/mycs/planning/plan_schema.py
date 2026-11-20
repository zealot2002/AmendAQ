from __future__ import annotations

import re

from mycs.models import KnowledgeRequirement, KnowledgeSource, UnderstandResult
from mycs.planning.query_intent import is_whole_document_query, search_keywords_for

GRAPH_FIELDS = frozenset(
    {
        "graph.entity.search",
        "graph.entity.by_section",
        "graph.entity.catalog_match",
        "graph.entity.record",
        "graph.relation.neighbors",
        "graph.entity.evidence",
        "graph.read.query",
    }
)

DOMAIN_FIELDS = frozenset(
    {
        "case.status",
        "case.record",
        "gov.procedure.online_available",
        "gov.policy.review_time_limit",
    }
)

WIKI_FIELDS = frozenset(
    {
        "wiki.policy.catalog_match",
        "wiki.policy.body",
        "wiki.policy.evidence",
        "wiki.toc.branch",
        "wiki.toc.leaves",
    }
)

WIKI_TOC_FIELDS = frozenset({"wiki.toc.branch", "wiki.toc.leaves"})


def normalize_requirements(
    understood: UnderstandResult,
    items: list[dict],
) -> list[KnowledgeRequirement]:
    """Turn LLM JSON into validated KnowledgeRequirement list."""
    doc = understood.graph_document_id
    q = understood.raw_question
    intent = understood.intent
    if intent == "handbook_qa":
        intent = "graph_qa"

    reqs: list[KnowledgeRequirement] = []
    for item in items:
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        if field == "graph.entity.search":
            continue
        source = _source_from_item(item, field, intent)
        if source is None:
            continue
        params = dict(item.get("params") or {})
        if doc and intent == "graph_qa":
            params["document_id"] = doc
        params = _normalize_params(field, params, doc=doc, question=q)
        reqs.append(
            KnowledgeRequirement(field=field, source=source, params=params)
        )

    if intent == "graph_qa":
        reqs = [
            r
            for r in reqs
            if r.source in (KnowledgeSource.GRAPH, KnowledgeSource.WIKI)
        ]
        reqs = _ensure_graph_baseline(reqs, doc=doc, question=q)
    return reqs


def apply_toc_section_whitelist(
    reqs: list[KnowledgeRequirement],
    valid_sections: set[str],
) -> list[KnowledgeRequirement]:
    if not valid_sections:
        return reqs
    out: list[KnowledgeRequirement] = []
    for r in reqs:
        if r.field == "graph.entity.by_section":
            sec = str(r.params.get("section") or "")
            if sec and sec not in valid_sections:
                continue
        out.append(r)
    return out


def _source_from_item(
    item: dict, field: str, intent: str
) -> KnowledgeSource | None:
    raw = (item.get("source") or "").lower()
    if raw == "graph" or field in GRAPH_FIELDS:
        if field not in GRAPH_FIELDS:
            return None
        return KnowledgeSource.GRAPH
    if raw == "domain_api" or field in DOMAIN_FIELDS:
        if field not in DOMAIN_FIELDS:
            return None
        return KnowledgeSource.DOMAIN_API
    if raw == "wiki" or field in WIKI_FIELDS:
        if field not in WIKI_FIELDS:
            return None
        return KnowledgeSource.WIKI
    if field in WIKI_TOC_FIELDS:
        return KnowledgeSource.WIKI
    if intent == "graph_qa" and field in GRAPH_FIELDS:
        return KnowledgeSource.GRAPH
    return None


def _normalize_params(
    field: str,
    params: dict,
    *,
    doc: str | None,
    question: str,
) -> dict:
    if field == "graph.entity.by_section" and doc:
        params.setdefault("document_id", doc)
        if params.get("section_ref") and not params.get("section"):
            params["section"] = params.pop("section_ref")
        sec = str(params.get("section") or "")
        if sec and not re.match(r"^\d+(\.\d+)*\.?$", sec):
            params.pop("section", None)
    elif field == "graph.read.query":
        params.setdefault("nl_query", question)
        if doc:
            params.setdefault("document_id", doc)
    elif field == "graph.entity.catalog_match":
        params.setdefault("topics", [])
        if doc:
            params.setdefault("document_id", doc)
    elif field == "wiki.toc.branch" and doc:
        params.setdefault("document_id", doc)
    elif field == "wiki.toc.leaves":
        nids = params.get("node_ids") or []
        if isinstance(nids, str):
            nids = [nids] if nids else []
        params["node_ids"] = list(nids)
    return params


def _ensure_graph_baseline(
    reqs: list[KnowledgeRequirement],
    *,
    doc: str | None,
    question: str,
) -> list[KnowledgeRequirement]:
    """If LLM forgot retrieval, add one search gap (no question-specific sections)."""
    has_retrieval = any(
        r.field
        in (
            "graph.entity.by_section",
            "graph.entity.catalog_match",
            "wiki.toc.branch",
            "wiki.toc.leaves",
        )
        for r in reqs
    )
    if has_retrieval:
        if is_whole_document_query(question) and not any(
            r.field == "graph.read.query" for r in reqs
        ):
            reqs = [
                *reqs,
                KnowledgeRequirement(
                    field="graph.read.query",
                    source=KnowledgeSource.GRAPH,
                    params={"nl_query": question, "document_id": doc},
                ),
            ]
        return reqs
    out = list(reqs)
    if is_whole_document_query(question):
        out.append(
            KnowledgeRequirement(
                field="graph.read.query",
                source=KnowledgeSource.GRAPH,
                params={"nl_query": question, "document_id": doc},
            )
        )
    return out
