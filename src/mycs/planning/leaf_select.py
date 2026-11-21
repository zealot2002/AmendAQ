from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.ui.trace_llm_capture import take_llm_captures

logger = get_logger(__name__)

DEFAULT_LEAF_BATCH_SIZE = 20


class WikiLeafSelector(Protocol):
    def select_wiki_leaf_sections(
        self,
        *,
        question: str,
        batch_index: int,
        batch_total: int,
        leaves_in_batch: list[dict[str, Any]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
    ) -> dict[str, Any]: ...


@dataclass
class LeafSelectResult:
    section_refs: list[str] = field(default_factory=list)
    batch_log: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


def _batch_size() -> int:
    return max(8, int(os.environ.get("MYCS_LEAF_BATCH_SIZE", str(DEFAULT_LEAF_BATCH_SIZE))))


def _leaf_rows(outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n in outline:
        if str(n.get("kind") or "") != "leaf":
            continue
        ref = str(n.get("section_ref") or "").strip()
        if not ref:
            continue
        rows.append(
            {
                "section_ref": ref,
                "title": str(n.get("title") or "")[:200],
                "summary": str(n.get("summary") or "")[:280],
            }
        )
    return rows


def run_leaf_section_select(
    *,
    llm: WikiLeafSelector,
    question: str,
    outline: list[dict[str, Any]],
) -> LeafSelectResult:
    """LLM picks leaf section_refs from wiki_toc_outline (no lexical kg_search)."""
    result = LeafSelectResult()
    leaves = _leaf_rows(outline)
    if not leaves:
        result.reason = "no_leaves_in_outline"
        return result

    batch_size = _batch_size()
    batches = [leaves[i : i + batch_size] for i in range(0, len(leaves), batch_size)]
    selected: list[str] = []
    selected_set: set[str] = set()

    log_step(
        logger,
        "leaf_select_start",
        leaf_total=len(leaves),
        batch_total=len(batches),
        batch_size=batch_size,
    )

    for batch_idx, batch in enumerate(batches):
        batches_remaining = len(batches) - batch_idx - 1
        already = [
            {"section_ref": r, "title": _title_for_ref(leaves, r)} for r in selected
        ]
        decision = llm.select_wiki_leaf_sections(
            question=question,
            batch_index=batch_idx + 1,
            batch_total=len(batches),
            leaves_in_batch=batch,
            already_selected=already,
            batches_remaining=batches_remaining,
        )
        action = str(decision.get("action") or "continue").lower()
        refs = [str(r) for r in (decision.get("section_refs") or []) if r]
        reason = str(decision.get("reason") or "")
        batch_record = {
            "batch_index": batch_idx + 1,
            "batch_total": len(batches),
            "action": action,
            "section_refs": refs,
            "reason": reason,
            "leaves_offered": batch,
            "llm_calls": take_llm_captures(),
        }
        result.batch_log.append(batch_record)
        log_step(logger, "leaf_select_llm_reply", **batch_record)

        for ref in refs:
            if ref not in selected_set:
                selected_set.add(ref)
                selected.append(ref)

    result.section_refs = selected
    result.reason = "exhausted_batches" if selected else "no_pick"
    if not selected and len(leaves) == 1:
        result.section_refs = [str(leaves[0]["section_ref"])]
        result.reason = "single_leaf_fallback"
    log_step(logger, "leaf_select_done", selected=result.section_refs, reason=result.reason)
    return result


def _title_for_ref(leaves: list[dict[str, Any]], ref: str) -> str:
    for lf in leaves:
        if str(lf.get("section_ref") or "") == ref:
            return str(lf.get("title") or "")
    return ""