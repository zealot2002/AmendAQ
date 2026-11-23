"""已有数量 + 原文新增，且不得超过原文上限。数字只从问题和原文里取。"""

from __future__ import annotations

import re

from amendaq.answer_format import split_answer_sections

_NUM_UNIT = re.compile(r"(\d+)\s*(天|日|个|小时|元|新台币)")
_EXISTING = ("已经", "已有", "结转了", "已结转")
_GRANT = ("享有", "可获得", "授予", "新增", "每满")
_CAP = ("上限", "最多", "不超过")


def compute_capped_quantity(question: str, clauses: str) -> dict[str, int | str] | None:
    existing_hits = _near(question, _EXISTING)
    existing_vals = sorted({n for n, _u in existing_hits})
    units = {u for _n, u in existing_hits}
    if len(existing_vals) != 1 or len(units) != 1:
        return None
    unit = next(iter(units))
    grants = sorted({n for n, u in _near(clauses, _GRANT) if u == unit})
    caps = sorted({n for n, u in _near(clauses, _CAP) if u == unit})
    if len(grants) != 1 or len(caps) != 1:
        return None
    grant = grants[0]
    cap = caps[0]
    total = existing_vals[0] + grant
    return {
        "existing": existing_vals[0],
        "grant": grant,
        "cap": cap,
        "total": total,
        "result": min(total, cap),
        "unit": unit,
    }


def apply_capped_quantity(answer: str, computed: dict[str, int | str]) -> str:
    """结论里没有算出的那个数时，用该数替换结论段，依据段保留。"""
    result = int(computed["result"])
    unit = str(computed["unit"])
    public, evidence = split_answer_sections(answer)
    if re.search(rf"{result}\s*{re.escape(unit)}", public):
        return answer
    head = f"结论：{_sentence(computed)}"
    if evidence:
        return f"{head}\n\n{evidence}"
    return head


def _sentence(computed: dict[str, int | str]) -> str:
    existing = computed["existing"]
    grant = computed["grant"]
    cap = computed["cap"]
    total = computed["total"]
    result = computed["result"]
    unit = computed["unit"]
    relation = "没有超过" if int(total) <= int(cap) else "超过"
    return (
        f"已有 {existing}{unit}，加上原文写明的新增 {grant}{unit}，"
        f"合计 {total}{unit}，{relation}上限 {cap}{unit}，"
        f"因此最多可以拥有 {result}{unit}。"
    )


def _near(text: str, cues: tuple[str, ...], limit: int = 16) -> list[tuple[int, str]]:
    """数字必须紧跟在提示词后面，避免把后面另一句的天数算进来。"""
    found: list[tuple[int, str]] = []
    source = text or ""
    for cue in cues:
        start = 0
        while True:
            index = source.find(cue, start)
            if index < 0:
                break
            tail = source[index + len(cue) : index + len(cue) + limit]
            match = _NUM_UNIT.search(tail)
            if match and match.start() <= 4:
                found.append((int(match.group(1)), _unit_key(match.group(2))))
            start = index + len(cue)
    return found


def _unit_key(unit: str) -> str:
    if unit in ("天", "日"):
        return "天"
    return unit
