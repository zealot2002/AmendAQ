from __future__ import annotations

import os
import re


def expose_answer_evidence() -> bool:
    """开发调试可设为 1，在界面/API 中保留「依据」段。"""
    return os.environ.get("MYCS_CHAT_SHOW_EVIDENCE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def split_answer_sections(text: str) -> tuple[str, str]:
    """
    Split LLM compose output into user-facing conclusion and evidence block.
    Returns (public, evidence); public has leading「结论：」stripped when present.
    """
    raw = (text or "").strip()
    if not raw:
        return "", ""
    m = re.search(r"\n\s*依据[：:]", raw)
    if m:
        head = raw[: m.start()].strip()
        evidence = raw[m.start() :].strip()
    else:
        head, evidence = raw, ""

    for prefix in ("结论：", "结论:"):
        if head.startswith(prefix):
            head = head[len(prefix) :].strip()
            break
    return head or raw, evidence


def _public_too_terse(public: str, evidence: str) -> bool:
    """旧 prompt 常把细则只写在依据里；对用户展示时补上。"""
    p = (public or "").strip()
    ev = (evidence or "").strip()
    if not p or not ev or len(ev) < 12:
        return False
    if len(p) >= 120:
        return False
    if p.count("\n") >= 2:
        return False
    if p.count("。") <= 1 and len(p) < 100:
        return True
    return len(p) < 48


def answer_for_user(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if expose_answer_evidence():
        return raw
    public, evidence = split_answer_sections(raw)
    public = (public or raw).strip()
    if evidence and _public_too_terse(public, evidence):
        detail = re.sub(r"^依据[：:]\s*", "", evidence.strip(), count=1)
        if detail:
            return f"{public}\n\n{detail}".strip()
    return public