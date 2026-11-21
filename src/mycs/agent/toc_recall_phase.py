"""graph_qa 召回：仅扁平 FAQ（kb_faq_item）。"""
from __future__ import annotations

from typing import Any, Callable

from mycs.db.catalog_mode import CATALOG_FLAT_FAQ
from mycs.knowledge.service import KnowledgeService
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.planning.chapter_hints import is_composite_handbook_query
from mycs.planning.flat_faq import run_flat_faq_recall

logger = get_logger(__name__)

TraceEmit = Callable[[str, dict[str, Any]], None]
ProgressFn = Callable[[str], None]


def _outline_from_leaf_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "leaf",
            "section_ref": n.get("section_ref"),
            "title": n.get("title"),
            "summary": n.get("summary"),
            "node_id": n.get("node_id"),
        }
        for n in nodes
    ]


def run_graph_qa_catalog_recall(
    *,
    llm: Any,
    svc: KnowledgeService,
    document_id: str,
    question: str,
    plan_context: dict[str, object],
    context: dict[str, object],
    emit: TraceEmit,
    progress: ProgressFn,
) -> tuple[set[str], list[str]]:
    progress("正在按 FAQ 标题分批勾选…")
    flat = run_flat_faq_recall(
        llm=llm,
        svc=svc,
        document_id=document_id,
        question=question,
        composite_query=is_composite_handbook_query(question),
    )
    for row in flat.trace_events:
        emit("faq_title_batch", row)
    emit(
        "faq_flat_recall",
        {
            "leaf_count": len(flat.leaf_section_refs),
            "entry_batches": len(flat.trace_events),
            "reason": flat.reason,
        },
    )
    outline = _outline_from_leaf_nodes(flat.leaf_nodes)
    plan_context["catalog_note"] = (
        f"扁平 FAQ：共浏览 {len(flat.trace_events)} 批标题，"
        f"选中 {len(flat.leaf_section_refs)} 条问答。"
    )
    plan_context["faq_toc_outline"] = outline
    plan_context["wiki_toc_outline"] = outline
    plan_context["recall_source"] = "flat_faq"
    plan_context["catalog_mode"] = CATALOG_FLAT_FAQ
    plan_context["recall_reason"] = flat.reason
    context["faq_toc_outline"] = outline
    context["wiki_toc_outline"] = outline
    valid = set(flat.leaf_section_refs)
    doc_title = svc.document_display_title(document_id=document_id)
    emit(
        "outline",
        {
            "outline_count": len(outline),
            "document_id": document_id,
            "document_title": doc_title,
            "source": "flat_faq",
            "valid_leaf_count": len(valid),
            "outline_nodes": outline,
            "catalog_note": plan_context.get("catalog_note"),
        },
    )
    log_step(
        logger,
        "agent_toc_ready",
        document_id=document_id,
        mode="flat_faq",
        leaf_count=len(valid),
    )
    return valid, list(flat.leaf_section_refs)


__all__ = ["run_graph_qa_catalog_recall"]