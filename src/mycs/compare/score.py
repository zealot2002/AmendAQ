"""Deterministic checks. The model is not asked whether it was correct."""

from __future__ import annotations

import re


def score_answer(answer: str, spec: dict) -> dict:
    text = _plain(answer or "")
    missing = [item for item in spec.get("require_all", []) if not _contains(text, item)]
    groups_missed: list[list[str]] = []
    for group in spec.get("require_any", []):
        if not any(_contains(text, item) for item in group):
            groups_missed.append(list(group))
    forbidden = [item for item in spec.get("forbid", []) if item and _contains(text, item)]
    for pattern in spec.get("forbid_regex", []):
        if re.search(pattern, text):
            forbidden.append(pattern)
    ok = not missing and not groups_missed and not forbidden and bool(text.strip())
    return {
        "ok": ok,
        "missing": missing,
        "groups_missed": groups_missed,
        "forbidden": forbidden,
    }


def _plain(text: str) -> str:
    return re.sub(r"[*_`]", "", text or "")


def _contains(text: str, needle: str) -> bool:
    """Ignore spaces the model drops, and don't let 23 satisfy a required 3.

    A required integer also matches the same digits with thousands separators,
    so 18000 accepts 18,000.
    """
    chars = [ch for ch in needle if not ch.isspace()]
    if not chars:
        return False
    if all(ch.isdigit() for ch in chars):
        body = r"[,，\s]*".join(re.escape(ch) for ch in chars)
        return re.search(rf"(?<!\d){body}(?!\d)", text) is not None
    pattern = r"\s*".join(re.escape(ch) for ch in chars)
    if chars[0].isdigit():
        pattern = rf"(?<!\d){pattern}"
    if chars[-1].isdigit():
        pattern = rf"{pattern}(?!\d)"
    return re.search(pattern, text) is not None


def summarize(rows: list[dict]) -> dict:
    by_kind: dict[str, dict[str, int]] = {}
    for row in rows:
        kind = row["kind"]
        bucket = by_kind.setdefault(kind, {"n": 0, "ok": 0})
        bucket["n"] += 1
        if row["ok"]:
            bucket["ok"] += 1
    return {
        "n": len(rows),
        "ok": sum(1 for row in rows if row["ok"]),
        "by_kind": by_kind,
    }
