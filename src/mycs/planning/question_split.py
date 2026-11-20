from __future__ import annotations

import re
from typing import Any, Protocol

from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.planning.chapter_hints import is_multi_part_question

logger = get_logger(__name__)


class QuestionSplitter(Protocol):
    def split_questions(self, question: str) -> dict[str, Any]: ...


def should_attempt_question_split(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if is_multi_part_question(q):
        return True
    if "？" in q and "；" in q:
        return True
    if re.search(r"[?？].+[?？]", q):
        return True
    return False


def normalize_sub_questions(question: str, payload: dict[str, Any]) -> list[str]:
    """Return non-empty sub-questions; fall back to original single question."""
    raw = payload.get("questions") or payload.get("sub_questions") or []
    if not isinstance(raw, list):
        raw = []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        s = str(item or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    if len(out) >= 2:
        return out
    q = (question or "").strip()
    return [q] if q else []


def resolve_sub_questions(
    llm: QuestionSplitter,
    question: str,
    *,
    use_llm: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    q = (question or "").strip()
    if not q:
        return [], {"reason": "empty", "llm_invoked": False}
    if not use_llm or not should_attempt_question_split(q):
        return [q], {"reason": "single_question", "llm_invoked": False, "questions": [q]}
    try:
        payload = llm.split_questions(q)
        subs = normalize_sub_questions(q, payload)
        log_step(
            logger,
            "question_split_done",
            input_len=len(q),
            count=len(subs),
            llm_reason=payload.get("reason"),
        )
        meta = {
            "reason": str(payload.get("reason") or "llm_split"),
            "llm_invoked": True,
            "questions": subs,
        }
        return subs, meta
    except Exception as exc:
        logger.error("joyjoy: question split failed: %s", exc)
        return [q], {"reason": f"split_failed: {exc}", "llm_invoked": False, "questions": [q]}