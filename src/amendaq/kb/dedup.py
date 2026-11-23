from __future__ import annotations

import re


def normalize_faq_question(question: str) -> str:
    """题干去重键：去空白、去题号前缀、不区分大小写。"""
    q = (question or "").strip()
    q = re.sub(r"\s+", " ", q)
    q = re.sub(r"^\d+[.．、]\s*", "", q)
    q = re.sub(r"^Q\d+[.．、]\s*", "", q, flags=re.IGNORECASE)
    q = re.sub(r"^(?:问|Q)\s*[：:]\s*", "", q, flags=re.IGNORECASE)
    return q.casefold()


def normalize_faq_answer(answer: str) -> str:
    a = (answer or "").strip()
    a = re.sub(r"\s+", " ", a)
    return a.casefold()


def faq_pair_key(question: str, answer: str) -> tuple[str, str]:
    return normalize_faq_question(question), normalize_faq_answer(answer)