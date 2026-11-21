from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from mycs.knowledge.search import score_entity
from mycs.knowledge.service import KnowledgeService
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.planning.query_intent import is_whole_document_query
from mycs.ui.trace_llm_capture import take_llm_captures

logger = get_logger(__name__)

DEFAULT_BATCH_SIZE = 8
DEFAULT_FAQ_SINGLE_PASS_MAX = 120
DEFAULT_FAQ_RECALL_MAX_PICKS = 5
DEFAULT_FAQ_RECALL_MAX_PICKS_ENUM = 24


def faq_title_notes(
    *,
    enumerative_query: bool,
    composite_query: bool,
    pick_cap: int,
) -> tuple[str, str]:
    """Ordinary「通常 1～3 条」只用于单件事。多件事另有自己的上限，不再叠加上限句。"""
    from mycs.prompts import prompt

    if enumerative_query:
        kind_note = "\n\n" + prompt("faq_title_enumerative", pick_cap=pick_cap)
    elif composite_query:
        kind_note = ""
    else:
        kind_note = "\n\n" + prompt("faq_title_ordinary", pick_cap=pick_cap)
    composite_note = (
        "\n\n" + prompt("faq_title_composite", pick_cap=pick_cap) if composite_query else ""
    )
    return kind_note, composite_note


class FaqTitleReviewer(Protocol):
    def review_faq_title_batch(
        self,
        *,
        question: str,
        document_title: str,
        batch_index: int,
        batch_total: int,
        entry_total: int,
        entries_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        enumerative_query: bool = False,
        composite_query: bool = False,
        recall_exhaustive_batches: bool = True,
        max_picks: int = 5,
    ) -> dict[str, Any]: ...


@dataclass
class FlatFaqResult:
    leaf_section_refs: list[str] = field(default_factory=list)
    leaf_nodes: list[dict[str, Any]] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


def _batch_size() -> int:
    return max(3, int(os.environ.get("MYCS_TOC_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))))


def _faq_single_pass_max() -> int:
    return max(8, int(os.environ.get("MYCS_FAQ_SINGLE_PASS_MAX", str(DEFAULT_FAQ_SINGLE_PASS_MAX))))


def _recall_max_picks(*, enumerative_query: bool) -> int:
    if enumerative_query:
        return max(
            1,
            int(
                os.environ.get(
                    "MYCS_FAQ_RECALL_MAX_PICKS_ENUM",
                    str(DEFAULT_FAQ_RECALL_MAX_PICKS_ENUM),
                )
            ),
        )
    return max(
        1,
        int(os.environ.get("MYCS_FAQ_RECALL_MAX_PICKS", str(DEFAULT_FAQ_RECALL_MAX_PICKS))),
    )


def _trim_faq_picks(
    question: str,
    nodes: list[dict[str, Any]],
    *,
    enumerative_query: bool,
) -> tuple[list[dict[str, Any]], int]:
    """When LLM picks more than max_picks, rerank by score_entity and trim."""
    if not nodes:
        return [], 0
    cap = _recall_max_picks(enumerative_query=enumerative_query)
    if len(nodes) <= cap:
        return nodes, 0
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, node in enumerate(nodes):
        title = str(node.get("title") or "")
        summary = str(node.get("summary") or "")
        scored.append((score_entity(question, title, summary), idx, node))
    scored.sort(key=lambda row: (-row[0], row[1]))
    kept = [row[2] for row in scored[:cap]]
    dropped = max(0, len(nodes) - len(kept))
    log_step(
        logger,
        "flat_faq_rerank_topk",
        offered=len(nodes),
        kept=len(kept),
        max_picks=cap,
        enumerative=enumerative_query,
        dropped=dropped,
    )
    return kept, dropped


def _faq_effective_batch_size(leaf_count: int) -> int:
    if leaf_count <= _faq_single_pass_max():
        return leaf_count
    return _batch_size()


def _node_by_ref(nodes: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
    for n in nodes:
        if str(n.get("section_ref") or "") == ref:
            return n
    return None


def _forced_batch_faq_title_select(
    llm: FaqTitleReviewer,
    *,
    question: str,
    document_title: str,
    leaves: list[dict[str, Any]],
    enumerative_query: bool = False,
    composite_query: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if not leaves:
        return [], [], 0
    pick_cap = _recall_max_picks(enumerative_query=enumerative_query)
    batch_size = _faq_effective_batch_size(len(leaves))
    batches = [leaves[i : i + batch_size] for i in range(0, len(leaves), batch_size)]
    log_step(
        logger,
        "flat_faq_batch_plan",
        leaf_total=len(leaves),
        batch_size=batch_size,
        batch_total=len(batches),
        single_pass=len(batches) == 1,
    )
    picked_nodes: list[dict[str, Any]] = []
    picked_ids: set[str] = set()
    batch_log: list[dict[str, Any]] = []

    for batch_idx, batch in enumerate(batches):
        batches_remaining = len(batches) - batch_idx - 1
        already = [
            {
                "section_ref": str(n.get("section_ref") or ""),
                "title": str(n.get("title") or ""),
            }
            for n in picked_nodes
        ]
        decision = llm.review_faq_title_batch(
            question=question,
            document_title=document_title,
            batch_index=batch_idx + 1,
            batch_total=len(batches),
            entry_total=len(leaves),
            entries_in_batch=batch,
            already_selected=already,
            batches_remaining=batches_remaining,
            enumerative_query=enumerative_query,
            composite_query=composite_query,
            max_picks=pick_cap,
        )
        action = str(decision.get("action") or "continue").lower()
        raw_refs = [str(r) for r in (decision.get("section_refs") or []) if r]
        batch_ref_set = {str(c.get("section_ref") or "") for c in batch if c.get("section_ref")}
        refs = [r for r in raw_refs if r in batch_ref_set]
        if raw_refs and not refs:
            log_step(
                logger,
                "flat_faq_refs_not_in_batch",
                batch_index=batch_idx + 1,
                rejected=raw_refs,
            )

        for ref in refs:
            node = _node_by_ref(leaves, ref) or _node_by_ref(batch, ref)
            if not node:
                continue
            nid = str(node.get("node_id") or "")
            if nid and nid not in picked_ids:
                picked_ids.add(nid)
                picked_nodes.append(node)

        batch_log.append(
            {
                "phase": "faq_title",
                "batch_index": batch_idx + 1,
                "batch_total": len(batches),
                "batches_remaining_after": batches_remaining,
                "action": action,
                "section_refs": refs,
                "entries_offered": batch,
                "llm_calls": take_llm_captures(),
            }
        )

    trimmed, dropped = _trim_faq_picks(
        question,
        picked_nodes,
        enumerative_query=enumerative_query,
    )
    if dropped:
        batch_log.append(
            {
                "phase": "faq_title_rerank",
                "max_picks": _recall_max_picks(enumerative_query=enumerative_query),
                "before": len(picked_nodes),
                "after": len(trimmed),
                "dropped_by_rank": dropped,
            }
        )
    return trimmed, batch_log, dropped


def run_flat_faq_recall(
    *,
    llm: Any,
    svc: KnowledgeService,
    document_id: str,
    question: str,
    composite_query: bool = False,
    enumerative_query: bool | None = None,
) -> FlatFaqResult:
    """Flat FAQ: all published leaves as (title, summary) list; LLM picks per batch — no chapter drill."""
    result = FlatFaqResult()
    pack = svc.faq_list_published_leaves(document_id=document_id)
    leaves: list[dict[str, Any]] = list(pack.get("leaves") or [])
    if not leaves:
        result.reason = "no_leaves"
        log_step(
            logger,
            "flat_faq_no_published_leaves",
            document_id=document_id,
            hint="ingest_and_publish",
        )
        return result

    if enumerative_query is None:
        enumerative_query = is_whole_document_query(question)

    doc_title = svc.document_display_title(document_id=document_id)
    log_step(
        logger,
        "flat_faq_start",
        document_id=document_id,
        leaf_total=len(leaves),
        enumerative_query=enumerative_query,
    )
    picked, batch_log, trim_dropped = _forced_batch_faq_title_select(
        llm,
        question=question,
        document_title=doc_title,
        leaves=leaves,
        enumerative_query=enumerative_query,
        composite_query=composite_query,
    )
    result.trace_events.extend(batch_log)
    if trim_dropped:
        result.reason = "flat_faq_done_trimmed"
    leaf_by_ref: dict[str, dict[str, Any]] = {}
    for node in picked:
        ref = str(node.get("section_ref") or "")
        if ref:
            leaf_by_ref[ref] = node
    result.leaf_nodes = list(leaf_by_ref.values())
    result.leaf_section_refs = sorted(leaf_by_ref.keys(), key=lambda s: (len(s), s))
    result.reason = "flat_faq_done" if result.leaf_section_refs else "flat_faq_empty"
    log_step(
        logger,
        "flat_faq_done",
        document_id=document_id,
        leaves=len(result.leaf_section_refs),
        trace_steps=len(result.trace_events),
    )
    return result