from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from mycs.knowledge.service import KnowledgeService
from mycs.log import get_logger
from mycs.log_detail import log_step
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
        chapters_in_batch: list[dict[str, Any]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
    ) -> dict[str, Any]: ...


@dataclass
class TocBatchSelectResult:
    selected_section_refs: list[str] = field(default_factory=list)
    total_chapters: int = 0
    batches_shown: int = 0
    batch_size: int = DEFAULT_BATCH_SIZE
    batch_log: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""


def _batch_size() -> int:
    return max(3, int(os.environ.get("MYCS_TOC_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))))


def run_toc_batch_chapter_select(
    *,
    llm: TocCatalogReviewer,
    svc: KnowledgeService,
    document_id: str,
    question: str,
) -> TocBatchSelectResult:
    """
    Send chapter-level TOC to LLM in batches.
    Goal: pick all chapters that may contain the answer; request next batch if unsure.
    """
    result = TocBatchSelectResult(batch_size=_batch_size())
    pack = svc.wiki_list_chapters(document_id=document_id)
    chapters: list[dict[str, Any]] = list(pack.get("chapters") or [])
    result.total_chapters = len(chapters)
    if not chapters:
        result.reason = "no_chapters"
        return result

    batch_size = result.batch_size
    batches = [chapters[i : i + batch_size] for i in range(0, len(chapters), batch_size)]
    selected_refs: list[str] = []
    selected_set: set[str] = set()

    log_step(
        logger,
        "toc_batch_start",
        document_id=document_id,
        chapter_total=len(chapters),
        batch_total=len(batches),
        batch_size=batch_size,
    )

    for batch_idx, batch in enumerate(batches):
        result.batches_shown = batch_idx + 1
        batches_remaining = len(batches) - batch_idx - 1
        already = [{"section_ref": r, "title": _title_for_ref(chapters, r)} for r in selected_refs]

        log_step(
            logger,
            "toc_batch_ask_llm",
            batch_index=batch_idx + 1,
            batch_total=len(batches),
            chapters_in_batch=batch,
        )
        decision = llm.review_toc_catalog_batch(
            question=question,
            batch_index=batch_idx + 1,
            batch_total=len(batches),
            chapter_total=len(chapters),
            chapters_in_batch=batch,
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
            "chapters_offered": batch,
            "llm_calls": take_llm_captures(),
        }
        result.batch_log.append(batch_record)
        log_step(logger, "toc_batch_llm_reply", **batch_record)

        if action in ("need_full_handbook", "full", "all"):
            selected_refs = [str(c.get("section_ref") or "") for c in chapters if c.get("section_ref")]
            result.selected_section_refs = selected_refs
            result.reason = "llm_requested_full_handbook"
            return result

        for ref in refs:
            if ref not in selected_set:
                selected_set.add(ref)
                selected_refs.append(ref)

        if action in ("done", "stop"):
            result.selected_section_refs = selected_refs
            result.reason = reason or "done"
            return result

        if action in ("pick", "select") and refs and batches_remaining == 0:
            result.selected_section_refs = selected_refs
            result.reason = reason or "last_batch"
            return result

        # continue / next_batch: proceed to next batch

    result.selected_section_refs = selected_refs
    if not selected_refs:
        result.selected_section_refs = [str(c.get("section_ref") or "") for c in chapters if c.get("section_ref")]
        result.reason = "fallback_all_chapters"
    else:
        result.reason = "exhausted_batches"
    log_step(
        logger,
        "toc_batch_done",
        selected=result.selected_section_refs,
        reason=result.reason,
    )
    return result


def _title_for_ref(chapters: list[dict[str, Any]], section_ref: str) -> str:
    for c in chapters:
        if str(c.get("section_ref") or "") == section_ref:
            return str(c.get("title") or "")
    return ""


def section_under_chapters(section_ref: str, chapter_prefixes: list[str]) -> bool:
    sr = (section_ref or "").strip()
    if not sr:
        return False
    for pref in chapter_prefixes:
        cp = pref.rstrip(".")
        if sr == cp or sr.startswith(f"{cp}."):
            return True
    return False
