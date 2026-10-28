from __future__ import annotations

import inspect
from typing import Any, Callable

from mycs.knowledge.service import KnowledgeService, ensure_database
from mycs.log import get_logger
from mycs.log_detail import summarize_tool_result, log_step

logger = get_logger(__name__)

ToolFn = Callable[..., dict[str, Any]]


class ToolRegistry:
    def __init__(self, service: KnowledgeService | None = None) -> None:
        ensure_database()
        self._svc = service or KnowledgeService()
        self._tools: dict[str, ToolFn] = {
            "find_wiki_policies": self._find_wiki_policies,
            "get_wiki_policy": self._get_wiki_policy,
            "get_wiki_evidence": self._get_wiki_evidence,
            "get_case": self._get_case,
            "get_case_status": self._get_case_status,
            "get_procedure": self._get_procedure,
            "get_gov_policy_for_stage": self._get_gov_policy_for_stage,
            "kg_search_entities": self._kg_search_entities,
            "kg_get_entity_by_section": self._kg_get_entity_by_section,
            "kg_find_entities": self._kg_find_entities,
            "kg_get_entity": self._kg_get_entity,
            "kg_neighbors": self._kg_neighbors,
            "kg_get_evidence": self._kg_get_evidence,
            "kg_run_readonly_sql": self._kg_run_readonly_sql,
            "kg_nl_query": self._kg_nl_query,
            "wiki_get_toc_outline": self._wiki_get_toc_outline,
            "wiki_resolve_branch": self._wiki_resolve_branch,
            "wiki_get_subtree": self._wiki_get_subtree,
            "wiki_get_leaves": self._wiki_get_leaves,
            "wiki_list_mounts": self._wiki_list_mounts,
            "wiki_publish_mount": self._wiki_publish_mount,
            "wiki_update_node": self._wiki_update_node,
        }

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def call(self, name: str, **params: Any) -> dict[str, Any]:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        fn = self._tools[name]
        sig = inspect.signature(fn)
        allowed = {k: v for k, v in params.items() if k in sig.parameters}
        if allowed != params:
            logger.info(
                "tool %s dropped extra params: %s",
                name,
                {k: v for k, v in params.items() if k not in allowed},
            )
        log_step(logger, "tool_call", api=name, params=allowed)
        try:
            out = fn(**allowed)
            log_step(logger, "tool_return", api=name, summary=summarize_tool_result(name, out))
            return out
        except Exception as exc:
            logger.warning("tool %s failed: %s", name, exc)
            return {"ok": False, "error": str(exc), "tool": name}

    def _find_wiki_policies(
        self, topics: list[str], match: str = "any", limit: int = 5
    ) -> dict[str, Any]:
        return self._svc.find_wiki_policies(topics=topics, match=match, limit=limit)

    def _get_wiki_policy(self, policy_id: str) -> dict[str, Any]:
        return self._svc.get_wiki_policy(policy_id)

    def _get_wiki_evidence(self, policy_id: str) -> dict[str, Any]:
        return self._svc.get_wiki_evidence(policy_id)

    def _get_case(self, case_id: str) -> dict[str, Any]:
        return self._svc.get_case(case_id)

    def _get_case_status(self, case_id: str) -> dict[str, Any]:
        return self._svc.get_case_status(case_id)

    def _get_procedure(self, procedure_id: str) -> dict[str, Any]:
        return self._svc.get_procedure(procedure_id)

    def _get_gov_policy_for_stage(
        self, procedure_id: str, review_stage: str
    ) -> dict[str, Any]:
        return self._svc.get_gov_policy_for_stage(procedure_id, review_stage)

    def _kg_search_entities(
        self,
        query: str,
        document_id: str | None = None,
        limit: int = 5,
        entity_id_in: list[str] | None = None,
        section_prefix: str | None = None,
    ) -> dict[str, Any]:
        return self._svc.kg_search_entities(
            query=query,
            document_id=document_id,
            limit=limit,
            entity_id_in=entity_id_in,
            section_prefix=section_prefix,
        )

    def _kg_get_entity_by_section(
        self, section: str, document_id: str | None = None
    ) -> dict[str, Any]:
        return self._svc.kg_get_entity_by_section(section, document_id=document_id)

    def _kg_find_entities(
        self,
        topics: list[str] | None = None,
        entity_type: str | None = None,
        name_contains: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        return self._svc.kg_find_entities(
            topics=topics or [],
            entity_type=entity_type,
            name_contains=name_contains,
            document_id=document_id,
            limit=limit,
        )

    def _kg_get_entity(self, entity_id: str) -> dict[str, Any]:
        return self._svc.kg_get_entity(entity_id)

    def _kg_neighbors(
        self,
        entity_id: str,
        predicate: str | None = None,
        direction: str = "out",
    ) -> dict[str, Any]:
        return self._svc.kg_neighbors(
            entity_id, predicate=predicate, direction=direction
        )

    def _kg_get_evidence(self, entity_id: str) -> dict[str, Any]:
        return self._svc.kg_get_evidence(entity_id)

    def _kg_run_readonly_sql(self, sql: str) -> dict[str, Any]:
        return self._svc.kg_run_readonly_sql(sql)

    def _kg_nl_query(
        self, question: str, document_id: str | None = None
    ) -> dict[str, Any]:
        return self._svc.kg_nl_query(question, document_id=document_id)

    def _wiki_get_toc_outline(
        self,
        document_id: str | None = None,
        mount_id: str | None = None,
        max_nodes: int = 200,
    ) -> dict[str, Any]:
        return self._svc.wiki_get_toc_outline(
            document_id=document_id, mount_id=mount_id, max_nodes=max_nodes
        )

    def _wiki_resolve_branch(
        self,
        document_id: str | None = None,
        node_id: str | None = None,
        section_prefix: str | None = None,
    ) -> dict[str, Any]:
        return self._svc.wiki_resolve_branch(
            node_id=node_id,
            section_prefix=section_prefix,
            document_id=document_id,
        )

    def _wiki_get_subtree(self, node_id: str) -> dict[str, Any]:
        return self._svc.wiki_get_subtree(node_id)

    def _wiki_get_leaves(self, node_ids: list[str]) -> dict[str, Any]:
        return self._svc.wiki_get_leaves(node_ids)

    def _wiki_list_mounts(self) -> dict[str, Any]:
        return self._svc.wiki_list_mounts()

    def _wiki_publish_mount(self, mount_id: str, actor: str = "ui") -> dict[str, Any]:
        return self._svc.wiki_publish_mount(mount_id, actor=actor)

    def _wiki_update_node(
        self,
        node_id: str,
        title: str | None = None,
        summary: str | None = None,
        parent_id: str | None = None,
        disabled: bool | None = None,
    ) -> dict[str, Any]:
        return self._svc.wiki_update_node(
            node_id,
            title=title,
            summary=summary,
            parent_id=parent_id,
            disabled=disabled,
        )
