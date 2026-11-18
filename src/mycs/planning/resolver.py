from __future__ import annotations

from typing import Any

from mycs.models import KnowledgeRequirement, KnowledgeSource


class GapResolver:
    """Map knowledge gaps → Knowledge API calls (not search queries)."""

    def resolve(
        self, req: KnowledgeRequirement, context: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        field = req.field
        params = dict(req.params)

        if req.source == KnowledgeSource.DOMAIN_API:
            if field == "case.status":
                return "get_case_status", {"case_id": params["case_id"]}
            if field == "case.record":
                return "get_case", {"case_id": params["case_id"]}
            if field == "gov.procedure.online_available":
                return "get_procedure", {"procedure_id": params["procedure_id"]}
            if field == "gov.policy.review_time_limit":
                proc = params.get("procedure_id")
                if proc == "__from_case__":
                    case = context.get("case")
                    if not case:
                        raise RuntimeError("case.record required before gov.policy")
                    proc = case["procedure_id"]
                return "get_gov_policy_for_stage", {
                    "procedure_id": proc,
                    "review_stage": params["review_stage"],
                }

        if req.source == KnowledgeSource.GRAPH:
            if field == "graph.entity.search":
                scoped = context.get("wiki_scope_entity_ids")
                section_refs = context.get("wiki_scope_section_refs") or None
                section_prefix = None
                if not section_refs:
                    section_prefix = params.get("section_prefix") or context.get(
                        "wiki_scope_section_prefix"
                    )
                return "kg_search_entities", {
                    "query": params.get("query") or context.get("raw_question", ""),
                    "document_id": params.get("document_id")
                    or context.get("graph_document_id"),
                    "limit": params.get("limit", 5),
                    "entity_id_in": params.get("entity_id_in") or scoped,
                    "section_prefix": section_prefix,
                    "section_refs": section_refs,
                }
            if field == "graph.entity.by_section":
                return "kg_get_entity_by_section", {
                    "section": params["section"],
                    "document_id": params.get("document_id")
                    or context.get("graph_document_id"),
                }
            if field == "graph.entity.catalog_match":
                return "kg_find_entities", {
                    "topics": params.get("topics") or [],
                    "entity_type": params.get("entity_type", "Policy"),
                    "document_id": params.get("document_id")
                    or context.get("graph_document_id"),
                    "limit": params.get("limit", 3),
                }
            if field == "graph.entity.record":
                eid = params.get("entity_id") or context.get("_resolved_graph_entity_id")
                if not eid:
                    raise RuntimeError("resolve graph.entity.catalog_match first")
                return "kg_get_entity", {"entity_id": eid}
            if field == "graph.relation.neighbors":
                eid = params.get("entity_id") or context.get("_resolved_graph_entity_id")
                if not eid:
                    raise RuntimeError("need entity before graph.relation.neighbors")
                return "kg_neighbors", {
                    "entity_id": eid,
                    "predicate": params.get("predicate"),
                    "direction": params.get("direction", "out"),
                }
            if field == "graph.entity.evidence":
                eid = params.get("entity_id") or context.get("_resolved_graph_entity_id")
                if not eid:
                    raise RuntimeError("need entity before evidence")
                return "kg_get_evidence", {"entity_id": eid}
            if field == "graph.read.query":
                nl = params.get("nl_query") or context.get("raw_question")
                if not nl:
                    raise RuntimeError("graph.read.query needs nl_query or raw_question")
                return "kg_nl_query", {
                    "question": nl,
                    "document_id": params.get("document_id")
                    or context.get("graph_document_id"),
                }

        if req.source == KnowledgeSource.WIKI:
            if field == "wiki.toc.branch":
                doc = params.get("document_id") or context.get("graph_document_id")
                return "wiki_resolve_branch", {
                    "node_id": params.get("node_id"),
                    "section_prefix": params.get("section_prefix"),
                    "document_id": doc,
                }
            if field == "wiki.toc.leaves":
                nids = params.get("node_ids") or []
                return "wiki_get_leaves", {"node_ids": nids}
            if field == "wiki.policy.catalog_match":
                return "find_wiki_policies", {
                    "topics": params["topics"],
                    "match": params.get("match", "any"),
                    "limit": params.get("limit", 3),
                }
            if field == "wiki.policy.body":
                pid = params.get("policy_id") or context.get("_resolved_wiki_policy_id")
                if not pid:
                    raise RuntimeError("resolve wiki.policy.catalog_match first")
                return "get_wiki_policy", {"policy_id": pid}
            if field == "wiki.policy.evidence":
                pid = params.get("policy_id") or context.get("_resolved_wiki_policy_id")
                if not pid:
                    raise RuntimeError("resolve wiki policy before evidence")
                return "get_wiki_evidence", {"policy_id": pid}

        raise ValueError(f"cannot resolve gap: {field} ({req.source})")

    def after_tool(
        self,
        req: KnowledgeRequirement,
        tool: str,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        if tool == "find_wiki_policies":
            context["wiki_catalog"] = result
            hits = result.get("hits") or []
            if not hits:
                raise RuntimeError(f"no wiki policies for topics={result.get('topics')}")
            context["_resolved_wiki_policy_id"] = hits[0]["policy_id"]
            context["handbook_policy"] = hits[0]
        elif tool == "get_wiki_policy":
            context["handbook_policy"] = result
            context["_resolved_wiki_policy_id"] = result["policy_id"]
        elif tool == "get_wiki_evidence":
            context["handbook_evidence"] = result
        elif tool == "get_case":
            context["case"] = result
        elif tool == "get_case_status":
            context["case_status"] = result
            if "case" not in context:
                context["case"] = result
        elif tool == "get_procedure":
            context["procedure"] = result
        elif tool == "get_gov_policy_for_stage":
            context["policy"] = result
        elif tool in ("kg_find_entities", "kg_search_entities"):
            context["graph_catalog"] = result
            hits = result.get("hits") or []
            if not hits and tool == "kg_find_entities":
                raise RuntimeError(
                    f"no graph entities for topics={result.get('topics')}"
                )
            if hits:
                _merge_graph_entities(context, hits)
                context["_resolved_graph_entity_id"] = hits[0]["entity_id"]
                context["graph_entity"] = hits[0]
        elif tool == "kg_get_entity_by_section":
            if result.get("ok") is False or not result.get("entity_id"):
                return
            _merge_graph_entities(context, [result])
            context["graph_entity"] = result
            context["_resolved_graph_entity_id"] = result["entity_id"]
        elif tool == "kg_get_entity":
            if result.get("ok") is False or not result.get("entity_id"):
                return
            _merge_graph_entities(context, [result])
            context["graph_entity"] = result
            context["_resolved_graph_entity_id"] = result["entity_id"]
        elif tool == "kg_neighbors":
            context["graph_neighbors"] = result
        elif tool == "kg_get_evidence":
            context["graph_evidence"] = result
        elif tool == "kg_nl_query":
            context["graph_sql_result"] = result
        elif tool in ("wiki_resolve_branch", "wiki_get_subtree"):
            if result.get("ok") is False:
                return
            context["wiki_subtree"] = result
            root = result.get("root") or {}
            context["wiki_scope_node_id"] = root.get("node_id")
            pref = str(root.get("section_ref") or "")
            if pref:
                context["wiki_scope_section_prefix"] = pref
            leaves = result.get("leaves") or []
            eids = [
                str(lf.get("entity_id"))
                for lf in leaves
                if lf.get("entity_id")
            ]
            if eids:
                context["wiki_scope_entity_ids"] = eids
            _merge_wiki_leaves(context, leaves)
        elif tool == "wiki_get_leaves":
            if result.get("ok") is False:
                return
            leaves = result.get("leaves") or []
            _merge_wiki_leaves(context, leaves)
            extra = [str(lf["entity_id"]) for lf in leaves if lf.get("entity_id")]
            if extra:
                scoped_ids = list(context.get("wiki_scope_entity_ids") or [])
                for eid in extra:
                    if eid not in scoped_ids:
                        scoped_ids.append(eid)
                context["wiki_scope_entity_ids"] = scoped_ids


def _merge_wiki_leaves(context: dict[str, Any], leaves: list[dict[str, Any]]) -> None:
    bucket: list[dict[str, Any]] = context.setdefault("wiki_leaves", [])
    seen = {lf.get("node_id") for lf in bucket}
    for lf in leaves:
        nid = lf.get("node_id")
        if nid and nid not in seen:
            bucket.append(lf)
            seen.add(nid)
    refs = sorted({str(lf.get("section_ref")) for lf in bucket if lf.get("section_ref")})
    context["wiki_section_refs"] = refs
    ents = []
    for lf in bucket:
        if lf.get("entity_id"):
            ents.append(
                {
                    "entity_id": lf["entity_id"],
                    "section": lf.get("section_ref"),
                    "name": lf.get("title"),
                    "summary": lf.get("summary"),
                    "body": lf.get("body"),
                }
            )
    if ents:
        _merge_graph_entities(context, ents)


def _merge_graph_entities(context: dict[str, Any], items: list[dict[str, Any]]) -> None:
    bucket: list[dict[str, Any]] = context.setdefault("graph_entities", [])
    seen = {e.get("entity_id") for e in bucket}
    for ent in items:
        eid = ent.get("entity_id")
        if eid and eid not in seen:
            bucket.append(ent)
            seen.add(eid)
    context["graph_section_refs"] = sorted(
        {str(e.get("section")) for e in bucket if e.get("section")}
    )
