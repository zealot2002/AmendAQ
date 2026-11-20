from __future__ import annotations

import re
from typing import Any

# Question facet → substring match on chapter title (after ingest TOC titles)
_FACETS: list[tuple[list[str], list[str]]] = [
    (["年假", "假期", "病假", "育儿假", "结转", "未使用"], ["假期"]),
    (["报销", "费用", "差旅", "发票"], ["报销", "薪酬"]),
    (["离职", "辞职", "交接", "通知", "纪律"], ["离职", "纪律"]),
    (["电脑", "笔记本", "门禁", "财产", "归还", "设备"], ["离职", "纪律", "信息", "安全"]),
    (["绩效", "目标", "评估"], ["绩效"]),
    (["礼品", "馈赠", "招待"], ["行为", "准则"]),
    (["远程", "出勤", "协作日"], ["出勤", "远程"]),
    (["安全", "访客"], ["安全", "访客"]),
    (["举报", "投诉"], ["举报", "问题"]),
    (["学习预算", "专业课程", "课程", "培训", "认证", "学习"], ["绩效", "发展"]),
    (["AI", "智能推荐", "推荐号码", "推荐可靠", "数据分析", "走势图"], ["数据分析"]),
    (["店主", "申请成为", "代销证", "入驻", "好势店主"], ["店主"]),
    (["模拟选号", "选号", "购彩", "代购"], ["模拟选号", "订单代购"]),
]

# Leaf title/summary hints for composite questions (multi-item recall).
_LEAF_FACETS: list[tuple[list[str], list[str]]] = [
    (["年假", "未使用"], ["年假"]),
    (["报销", "费用", "尚未报销"], ["报销"]),
    (["电脑", "笔记本", "财产", "归还"], ["财产", "电脑"]),
    (["离职", "辞职"], ["辞职", "离职", "财产"]),
    (["学习预算", "专业课程", "课程"], ["学习", "预算"]),
    (["AI", "推荐可靠", "推荐号码", "智能推荐"], ["AI推荐", "推荐"]),
    (["店主", "申请成为"], ["申请成为", "店主申请", "怎么申请"]),
]

_COMPOSITE = re.compile(
    r"(综合|分别|同时|还有|以及|既要|哪些事项|多.*方面|请.*区分|必须.*原则|"
    r"未使用|尚未|在手上|处理哪些)",
    re.I,
)
_OFFBOARDING = re.compile(r"离职|辞职|办理离职|交接", re.I)


def is_multi_part_question(question: str) -> bool:
    """用户一次输入多道独立小问题（换行或多问号）。"""
    q = (question or "").strip()
    if not q:
        return False
    lines = [ln.strip() for ln in q.splitlines() if ln.strip()]
    if len(lines) >= 2:
        return True
    return len(re.findall(r"[?？]", q)) >= 2


def question_lines_for_seeding(question: str) -> list[str]:
    q = (question or "").strip()
    if not q:
        return []
    if is_multi_part_question(q):
        lines = [ln.strip() for ln in q.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return lines
    return [q]


def merged_chapter_seeds(question: str, chapters: list[dict[str, Any]]) -> list[str]:
    """Per sub-question facet → chapter; composite 时与 LLM 章选并集。"""
    out: list[str] = []
    seen: set[str] = set()
    for sub in question_lines_for_seeding(question):
        for ref in seed_chapter_refs_from_question(sub, chapters):
            if ref not in seen:
                seen.add(ref)
                out.append(ref)
    return out


def is_composite_handbook_query(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if _COMPOSITE.search(q):
        return True
    if _OFFBOARDING.search(q) and len(re.findall(r"[\u4e00-\u9fff]{2,}", q)) >= 8:
        return True
    return False


def seed_chapter_refs_from_question(
    question: str,
    chapters: list[dict[str, Any]],
) -> list[str]:
    """Lexical facet → chapter title match; seeds chapter recall (composite or keyword facets)."""
    q = question or ""
    if not q:
        return []
    hits: list[str] = []
    seen: set[str] = set()
    training_q = any(k in q for k in ("学习预算", "专业课程", "培训", "认证"))
    for keywords, title_needles in _FACETS:
        if not any(k in q for k in keywords):
            continue
        if training_q and keywords == ["报销", "费用", "差旅", "发票"]:
            continue
        for ch in chapters:
            ref = str(ch.get("section_ref") or "").strip()
            title = str(ch.get("title") or "")
            if not ref:
                continue
            if any(n in title for n in title_needles):
                if ref not in seen:
                    seen.add(ref)
                    hits.append(ref)
    return hits


def drill_matches_seeded_chapters(
    scope_section_prefix: str | None,
    seeded_chapter_refs: list[str],
) -> bool:
    """True if drilled scope sits under one of the keyword-seeded chapters."""
    if not seeded_chapter_refs:
        return True
    if not scope_section_prefix:
        return False
    pref = str(scope_section_prefix).strip()
    for ch in seeded_chapter_refs:
        base = ch.rstrip(".")
        if pref == ch or pref == base or pref.startswith(f"{base}."):
            return True
    return False


def seed_leaf_sections_from_question(
    question: str,
    outline: list[dict[str, Any]],
) -> list[str]:
    """Pick leaf section_ref values for composite multi-item questions."""
    q = question or ""
    if not is_composite_handbook_query(q):
        return []
    leaves = [n for n in outline if n.get("kind") == "leaf"]
    refs: list[str] = []
    seen: set[str] = set()
    for keywords, title_needles in _LEAF_FACETS:
        if not any(k in q for k in keywords):
            continue
        for leaf in leaves:
            sec = str(leaf.get("section_ref") or "").strip()
            if not sec or sec in seen:
                continue
            blob = f"{leaf.get('title') or ''} {leaf.get('summary') or ''}"
            if any(n in blob for n in title_needles) or any(k in blob for k in keywords):
                seen.add(sec)
                refs.append(sec)
    return refs
