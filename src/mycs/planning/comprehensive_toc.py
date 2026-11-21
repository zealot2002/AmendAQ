from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from mycs.knowledge.service import KnowledgeService
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.planning.chapter_hints import seed_chapter_refs_from_question
from mycs.planning.query_intent import is_whole_document_query
from mycs.ui.trace_llm_capture import take_llm_captures

logger = get_logger(__name__)

DEFAULT_BATCH_SIZE = 8


class TocCatalogReviewer(Protocol):
    def review_toc_catalog_batch(
        self,
        *,
        question: str,
        batch_index: int,
        batch_total: int,
        chapter_total: int,
        chapters_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        composite_query: bool = False,
        enumerative_query: bool = False,
    ) -> dict[str, Any]: ...


class TocChildrenReviewer(Protocol):
    def review_toc_children_batch(
        self,
        *,
        question: str,
        parent_section_ref: str,
        parent_title: str,
        batch_index: int,
        batch_total: int,
        children_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        enumerative_query: bool = False,
        composite_query: bool = False,
    ) -> dict[str, Any]: ...


@dataclass
class ComprehensiveTocResult:
    """LLM-only directory traversal: all L1 batches, then all child batches per branch."""

    leaf_section_refs: list[str] = field(default_factory=list)
    leaf_nodes: list[dict[str, Any]] = field(default_factory=list)
    selected_chapter_refs: list[str] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


def _batch_size() -> int:
    return max(3, int(os.environ.get("MYCS_TOC_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))))


def _node_by_ref(nodes: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
    for n in nodes:
        if str(n.get("section_ref") or "") == ref:
            return n
    return None


def _forced_batch_chapter_select(
    llm: TocCatalogReviewer,
    *,
    question: str,
    chapters: list[dict[str, Any]],
    composite_query: bool,
    enumerative_query: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Run every chapter batch; ignore early done/stop until all batches consumed."""
    batch_size = _batch_size()
    batches = [chapters[i : i + batch_size] for i in range(0, len(chapters), batch_size)]
    selected_refs: list[str] = []
    selected_set: set[str] = set()
    batch_log: list[dict[str, Any]] = []

    for batch_idx, batch in enumerate(batches):
        batches_remaining = len(batches) - batch_idx - 1
        already = [
            {"section_ref": r, "title": str((_node_by_ref(chapters, r) or {}).get("title") or "")}
            for r in selected_refs
        ]
        decision = llm.review_toc_catalog_batch(
            question=question,
            batch_index=batch_idx + 1,
            batch_total=len(batches),
            chapter_total=len(chapters),
            chapters_in_batch=batch,
            already_selected=already,
            batches_remaining=batches_remaining,
            composite_query=composite_query,
            enumerative_query=enumerative_query,
        )
        action = str(decision.get("action") or "continue").lower()
        raw_refs = [str(r) for r in (decision.get("section_refs") or []) if r]
        batch_ref_set = {str(c.get("section_ref") or "") for c in batch if c.get("section_ref")}
        refs = [r for r in raw_refs if r in batch_ref_set]
        if raw_refs and not refs:
            log_step(
                logger,
                "comprehensive_toc_refs_not_in_batch",
                phase="L1",
                batch_index=batch_idx + 1,
                rejected=raw_refs,
                offered=sorted(batch_ref_set),
            )
        for ref in refs:
            if ref not in selected_set:
                selected_set.add(ref)
                selected_refs.append(ref)

        batch_log.append(
            {
                "phase": "L1_chapter",
                "batch_index": batch_idx + 1,
                "batch_total": len(batches),
                "batches_remaining_after": batches_remaining,
                "action": action,
                "section_refs": refs,
                "accumulated_chapters": list(selected_refs),
                "chapters_offered": batch,
                "llm_calls": take_llm_captures(),
            }
        )

    return selected_refs, batch_log


def _forced_batch_children_select(
    llm: TocChildrenReviewer,
    *,
    question: str,
    parent: dict[str, Any],
    children: list[dict[str, Any]],
    enumerative_query: bool = False,
    composite_query: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """All child batches under one parent; no early exit."""
    if not children:
        return [], []
    batch_size = _batch_size()
    batches = [children[i : i + batch_size] for i in range(0, len(children), batch_size)]
    picked_nodes: list[dict[str, Any]] = []
    picked_ids: set[str] = set()
    batch_log: list[dict[str, Any]] = []
    parent_ref = str(parent.get("section_ref") or "")
    parent_title = str(parent.get("title") or "")

    for batch_idx, batch in enumerate(batches):
        batches_remaining = len(batches) - batch_idx - 1
        already = [
            {
                "section_ref": str(n.get("section_ref") or ""),
                "title": str(n.get("title") or ""),
            }
            for n in picked_nodes
        ]
        decision = llm.review_toc_children_batch(
            question=question,
            parent_section_ref=parent_ref,
            parent_title=parent_title,
            batch_index=batch_idx + 1,
            batch_total=len(batches),
            children_in_batch=batch,
            already_selected=already,
            batches_remaining=batches_remaining,
            enumerative_query=enumerative_query,
            composite_query=composite_query,
        )
        action = str(decision.get("action") or "continue").lower()
        raw_refs = [str(r) for r in (decision.get("section_refs") or []) if r]
        batch_ref_set = {str(c.get("section_ref") or "") for c in batch if c.get("section_ref")}
        refs = [r for r in raw_refs if r in batch_ref_set]
        if raw_refs and not refs:
            log_step(
                logger,
                "comprehensive_toc_refs_not_in_batch",
                phase="L2",
                parent=parent_ref,
                batch_index=batch_idx + 1,
                rejected=raw_refs,
            )

        for ref in refs:
            node = _node_by_ref(children, ref) or _node_by_ref(batch, ref)
            if not node:
                continue
            nid = str(node.get("node_id") or "")
            if nid and nid not in picked_ids:
                picked_ids.add(nid)
                picked_nodes.append(node)

        batch_log.append(
            {
                "phase": "L2_children",
                "parent_section_ref": parent_ref,
                "parent_title": parent_title,
                "batch_index": batch_idx + 1,
                "batch_total": len(batches),
                "batches_remaining_after": batches_remaining,
                "action": action,
                "section_refs": refs,
                "children_offered": batch,
                "llm_calls": take_llm_captures(),
            }
        )

    return picked_nodes, batch_log


def run_comprehensive_toc_recall(
    *,
    llm: Any,
    svc: KnowledgeService,
    document_id: str,
    question: str,
    composite_query: bool = False,
    enumerative_query: bool | None = None,
) -> ComprehensiveTocResult:
    """
    Ideal path: L1 all batches → for each chapter expand all child batches (BFS) → leaves.
    No lexical kg_search. Does not use single-path toc_drill.
    """
    result = ComprehensiveTocResult()
    pack = svc.wiki_list_chapters(document_id=document_id)
    chapters: list[dict[str, Any]] = list(pack.get("chapters") or [])
    if not chapters:
        result.reason = "no_chapters"
        return result

    if enumerative_query is None:
        enumerative_query = is_whole_document_query(question)

    log_step(
        logger,
        "comprehensive_toc_L1_start",
        document_id=document_id,
        chapter_total=len(chapters),
        enumerative_query=enumerative_query,
    )
    selected_refs, l1_log = _forced_batch_chapter_select(
        llm,
        question=question,
        chapters=chapters,
        composite_query=composite_query,
        enumerative_query=enumerative_query,
    )
    result.trace_events.extend(l1_log)
    result.selected_chapter_refs = selected_refs
    if not result.selected_chapter_refs:
        seeded = seed_chapter_refs_from_question(question, chapters)
        if seeded:
            result.selected_chapter_refs = seeded
            result.reason = "L1_keyword_seed_chapters"
            log_step(
                logger,
                "comprehensive_toc_L1_keyword_seed",
                document_id=document_id,
                chapters=seeded,
            )
        else:
            result.reason = "L1_empty_no_chapters"
            log_step(logger, "comprehensive_toc_L1_empty", document_id=document_id)

    chapter_nodes = [
        c
        for c in chapters
        if str(c.get("section_ref") or "") in set(result.selected_chapter_refs)
    ]

    frontier: list[dict[str, Any]] = list(chapter_nodes)
    leaf_by_ref: dict[str, dict[str, Any]] = {}

    while frontier:
        parent = frontier.pop(0)
        parent_id = str(parent.get("node_id") or "")
        if not parent_id:
            continue
        bucket = svc.wiki_list_toc_children(
            parent_node_id=parent_id,
            document_id=document_id,
        )
        children = list(bucket.get("nodes") or [])
        if not children:
            if str(parent.get("kind") or "") == "leaf":
                ref = str(parent.get("section_ref") or "")
                if ref:
                    leaf_by_ref[ref] = parent
            continue

        picked, child_logs = _forced_batch_children_select(
            llm,
            question=question,
            parent=parent,
            children=children,
            enumerative_query=enumerative_query,
            composite_query=composite_query,
        )
        result.trace_events.extend(child_logs)

        if not picked:
            continue

        for node in picked:
            kind = str(node.get("kind") or "")
            if kind == "leaf":
                ref = str(node.get("section_ref") or "")
                if ref:
                    leaf_by_ref[ref] = node
            else:
                frontier.append(node)

    result.leaf_nodes = list(leaf_by_ref.values())
    result.leaf_section_refs = sorted(leaf_by_ref.keys(), key=lambda s: (len(s), s))
    if not result.reason:
        result.reason = "comprehensive_done"
    log_step(
        logger,
        "comprehensive_toc_done",
        chapters=len(result.selected_chapter_refs),
        leaves=len(result.leaf_section_refs),
        trace_steps=len(result.trace_events),
    )
    return result