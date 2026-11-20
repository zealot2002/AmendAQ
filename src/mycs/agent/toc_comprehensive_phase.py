"""graph_qa 全面目录遍历阶段：供 AgentLoop 调用，替代 drill + 词元 search。"""
from __future__ import annotations

from typing import Any, Callable

from mycs.knowledge.service import KnowledgeService
from mycs.log_detail import log_step
from mycs.models import KnowledgeRequirement, KnowledgeSource
from mycs.log import get_logger
from mycs.planning.chapter_hints import is_composite_handbook_query
from mycs.planning.comprehensive_toc import run_comprehensive_toc_recall

logger = get_logger(__name__)

TraceEmit = Callable[[str, dict[str, Any]], None]
ProgressFn = Callable[[str], None]


def by_section_requirements(
    document_id: str | None, section_refs: list[str]
) -> list[KnowledgeRequirement]:
    doc = document_id or ""
    out: list[KnowledgeRequirement] = []
    for ref in section_refs:
        if not ref:
            continue
        out.append(
            KnowledgeRequirement(
                field="graph.entity.by_section",
                source=KnowledgeSource.GRAPH,
                params={"section": ref, "document_id": doc},
            )
        )
    return out


def run_graph_qa_comprehensive_toc(
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
    """
    返回 (valid_leaf_sections, leaf_section_refs)。
 填充 plan_context / context 的 outline 与章节说明。
    """
    progress("正在全面浏览目录（逐批、不下钻单路径）…")
    composite_q = is_composite_handbook_query(question)
    comp = run_comprehensive_toc_recall(
        llm=llm,
        svc=svc,
        document_id=document_id,
        question=question,
        composite_query=composite_q,
    )
    for row in comp.trace_events:
        step = "toc_catalog_batch" if row.get("phase") == "L1_chapter" else "toc_children_batch"
        emit(step, row)
    emit(
        "toc_comprehensive",
        {
            "selected_chapters": comp.selected_chapter_refs,
            "leaf_count": len(comp.leaf_section_refs),
            "reason": comp.reason,
        },
    )
    outline = [
        {
            "kind": "leaf",
            "section_ref": n.get("section_ref"),
            "title": n.get("title"),
            "summary": n.get("summary"),
            "node_id": n.get("node_id"),
        }
        for n in comp.leaf_nodes
    ]
    plan_context["wiki_selected_chapters"] = comp.selected_chapter_refs
    plan_context["recall_source"] = "comprehensive_toc"
    plan_context["catalog_note"] = (
        f"全面目录遍历：{len(comp.selected_chapter_refs)} 章、"
        f"{len(comp.leaf_section_refs)} 条叶节点（LLM 分批，不提前停止）。"
    )
    plan_context["wiki_toc_outline"] = outline
    context["wiki_toc_outline"] = outline
    valid = set(comp.leaf_section_refs)
    doc_title = svc.document_display_title(document_id=document_id)
    emit(
        "outline",
        {
            "outline_count": len(outline),
            "document_id": document_id,
            "document_title": doc_title,
            "scoped": True,
            "selected_chapters": comp.selected_chapter_refs,
            "source": "comprehensive_toc",
            "valid_leaf_count": len(valid),
            "outline_nodes": outline,
            "catalog_note": plan_context.get("catalog_note"),
        },
    )
    log_step(
        logger,
        "agent_toc_ready",
        document_id=document_id,
        mode="comprehensive",
        leaf_count=len(valid),
        chapters=comp.selected_chapter_refs,
    )
    return valid, list(comp.leaf_section_refs)