from __future__ import annotations

from typing import Any

from mycs.models import UnderstandResult


def build_claims(understood: UnderstandResult, context: dict[str, Any]) -> dict[str, Any]:
    if understood.intent == "graph_qa":
        entities = context.get("graph_entities") or []
        leaves = context.get("wiki_leaves") or []
        refs = list(context.get("wiki_section_refs") or context.get("graph_section_refs") or [])
        return {
            "section_refs": refs,
            "entity_names": [e.get("name") for e in entities],
            "wiki_leaf_count": len(leaves),
            "search_top_score": _top_search_score(context),
        }

    if understood.intent == "handbook_qa":
        policy = context.get("handbook_policy") or {}
        ev = context.get("handbook_evidence") or policy.get("evidence") or {}
        quote = ev.get("quote") or policy.get("body") or ""
        return {
            "policy_id": policy.get("policy_id"),
            "policy_title": policy.get("title"),
            "evidence_snippet": quote[:120],
        }

    if understood.intent == "procedure_online_only":
        proc = context.get("procedure") or {}
        return {"online_available": proc.get("online_available")}

    case = context.get("case") or {}
    return {
        "claimed_status_label": case.get("status_label", ""),
        "claimed_within_limit": True,
        "submitted_at": case.get("submitted_at"),
    }


def _top_search_score(context: dict[str, Any]) -> float:
    cat = context.get("graph_catalog") or {}
    hits = cat.get("hits") or []
    if not hits:
        return 0.0
    return float(hits[0].get("search_score") or 0.0)
