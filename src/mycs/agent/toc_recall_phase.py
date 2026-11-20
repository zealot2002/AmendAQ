"""graph_qa 召回阶段：按 catalog_mode 选择扁平 FAQ 或全面章节目录。"""
from __future__ import annotations

from typing import Any, Callable

from mycs.db.catalog_mode import CATALOG_FLAT_FAQ
from mycs.knowledge.service import KnowledgeService
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.planning.chapter_hints import is_composite_handbook_query
from mycs.planning.comprehensive_toc import run_comprehensive_toc_recall
from mycs.planning.flat_faq import run_flat_faq_recall

from mycs.agent.toc_comprehensive_phase import by_section_requirements

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


def run_graph_qa_flat_faq(
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
    progress("正在按 FAQ 标题分批勾选（扁平列表，不下钻章）…")
    composite_q = is_composite_handbook_query(question)
    flat = run_flat_faq_recall(
        llm=llm,
        svc=svc,
        document_id=document_id,
        question=question,
        composite_query=composite_q,
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
    plan_context["wiki_selected_chapters"] = []
    plan_context["catalog_note"] = (
        f"扁平 FAQ：共浏览 {len(flat.trace_events)} 批标题，"
        f"选中 {len(flat.leaf_section_refs)} 条问答。"
    )
    plan_context["wiki_toc_outline"] = outline
    plan_context["recall_source"] = "flat_faq"
    plan_context["catalog_mode"] = CATALOG_FLAT_FAQ
    context["wiki_toc_outline"] = outline
    valid = set(flat.leaf_section_refs)
    doc_title = svc.document_display_title(document_id=document_id)
    emit(
        "outline",
        {
            "outline_count": len(outline),
            "document_id": document_id,
            "document_title": doc_title,
            "scoped": True,
            "selected_chapters": [],
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
    mode = svc.document_catalog_mode(document_id=document_id)
    if mode == CATALOG_FLAT_FAQ:
        return run_graph_qa_flat_faq(
            llm=llm,
            svc=svc,
            document_id=document_id,
            question=question,
            plan_context=plan_context,
            context=context,
            emit=emit,
            progress=progress,
        )

    from mycs.agent.toc_comprehensive_phase import run_graph_qa_comprehensive_toc

    plan_context["catalog_mode"] = mode
    valid, refs = run_graph_qa_comprehensive_toc(
        llm=llm,
        svc=svc,
        document_id=document_id,
        question=question,
        plan_context=plan_context,
        context=context,
        emit=emit,
        progress=progress,
    )
    plan_context["recall_source"] = "comprehensive_toc"
    return valid, refs


__all__ = ["by_section_requirements", "run_graph_qa_catalog_recall", "run_graph_qa_flat_faq"]