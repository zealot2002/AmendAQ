from __future__ import annotations

import re
from typing import Any


def _chinese_bigrams(segment: str) -> set[str]:
    """Overlapping 2-char units so「走势图…」与「走势图能投屏…」能匹配。"""
    seg = segment.strip()
    if len(seg) < 2:
        return set()
    if len(seg) <= 6:
        return {seg}
    out: set[str] = set()
    for i in range(len(seg) - 1):
        out.add(seg[i : i + 2])
    return out


def tokenize(text: str) -> set[str]:
    text = text.lower()
    tokens: set[str] = set()
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.update(_chinese_bigrams(seg))
    tokens.update(re.findall(r"[a-z0-9]{2,}", text))
    for m in re.finditer(r"\d+[,\d]*", text):
        tokens.add(m.group().replace(",", ""))
    return tokens


def score_entity(query: str, title: str, summary: str, body: str | None = None) -> float:
    qtok = tokenize(query)
    if not qtok:
        return 0.0
    title_t = tokenize(title)
    sum_t = tokenize(summary)
    body_t = tokenize((body or "")[:500])
    score = 0.0
    for t in qtok:
        if t in title_t:
            score += 4.0
        if t in sum_t:
            score += 2.0
        if t in body_t:
            score += 1.0
    # penalize FAQ appendix noise
    blob = (summary + (body or ""))[:400]
    if "Q：" in blob or "常见问题" in blob:
        score *= 0.15
    if len(summary) > 600:
        score *= 0.5
    return score
