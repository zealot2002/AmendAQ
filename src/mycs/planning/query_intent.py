from __future__ import annotations

import re

_WHOLE_DOC = re.compile(
    r"(所有|全部|列举|找出|有哪些|汇总|逐个|每一个|凡.*出现|整本|通篇)",
    re.I,
)
_AMOUNT = re.compile(r"(金额|限额|上限|多少元|费用上限|报销.*元|\d+\s*元)", re.I)


def is_whole_document_query(question: str) -> bool:
    """Questions that need full handbook scope, not a single TOC leaf."""
    q = (question or "").strip()
    if not q:
        return False
    if _WHOLE_DOC.search(q):
        return True
    if _AMOUNT.search(q) and len(q) > 20:
        return True
    return False


def search_keywords_for(question: str) -> str:
    """Shorter query for lexical search (long prompts score poorly)."""
    q = question.strip()
    if _AMOUNT.search(q):
        return "金额 上限 限额 元 报销 补贴 奖金"
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", q)
    if len(tokens) > 6:
        return " ".join(tokens[:6])
    return q
