from __future__ import annotations

import os
import re

from mycs.wiki.canonical import WikiCanonicalDraft
from mycs.wiki.compile import ANSWER_MARK, CHAPTER_MD, QUESTION_MD
from mycs.wiki.outline import CHAPTER_RE, OutlineNode, SECTION_RE

_ANY_H3 = re.compile(r"^###\s+(.+)$", re.MULTILINE)


def ingest_strict_enabled() -> bool:
    return os.environ.get("MYCS_INGEST_STRICT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def validate_faq_markdown_contract(text: str, draft: WikiCanonicalDraft) -> list[str]:
    """Pre-persist FAQ checks stricter than the parser alone."""
    errors: list[str] = []
    if not CHAPTER_MD.search(text):
        errors.append("缺少业务域标题（行首 ## ）")
    for m in _ANY_H3.finditer(text):
        title = m.group(1).strip()
        if not re.match(r"Q\d+", title, re.IGNORECASE):
            errors.append(f"题目须为 ### Q数字. 题干，非法行：### {title}")

    chapter_spans = list(CHAPTER_MD.finditer(text))
    for i, cm in enumerate(chapter_spans):
        start = cm.end()
        end = chapter_spans[i + 1].start() if i + 1 < len(chapter_spans) else len(text)
        block = text[start:end]
        for qm in QUESTION_MD.finditer(block):
            q_start = qm.end()
            next_q = QUESTION_MD.search(block, qm.end())
            q_end = next_q.start() if next_q else len(block)
            qa_block = block[q_start:q_end]
            if not ANSWER_MARK.search(qa_block):
                errors.append(f"{qm.group(1).strip()} 缺少 **答：**")

    heading_count = len(_ANY_H3.findall(text))
    valid_q = len(QUESTION_MD.findall(text))
    if heading_count != valid_q:
        errors.append(f"共有 {heading_count} 个 ### 标题，仅 {valid_q} 个符合 Q 题号格式")

    if valid_q and len(draft.leaves) != valid_q:
        errors.append(f"应解析 {valid_q} 题，实际 {len(draft.leaves)} 叶")

    leaf_parents = {lf.parent_ref.rstrip(".") for lf in draft.leaves}
    for ch in draft.chapters:
        ref = ch.section_ref.rstrip(".")
        if ref not in leaf_parents:
            errors.append(f"业务域「{ch.title}」下没有合法题目")

    for note in draft.ingest_notes:
        errors.append(note)

    return errors


def validate_handbook_contract(text: str, roots: list[OutlineNode]) -> list[str]:
    errors: list[str] = []
    if not CHAPTER_RE.search(text):
        errors.append("缺少章标题（行首 1. 标题）")
    if not SECTION_RE.search(text):
        errors.append("缺少节标题（行首 1.1 标题）")
    leaves = sum(len(ch.children) for ch in roots)
    if leaves == 0:
        errors.append("未解析到任何节条目")
    if any(ch.chapter_num == "0" and ch.title == "Document" for ch in roots):
        errors.append("不是编号手册格式（勿将 FAQ 存为 .txt 上传）")
    return errors


def enforce_faq_contract(text: str, draft: WikiCanonicalDraft) -> None:
    if not ingest_strict_enabled():
        return
    errors = validate_faq_markdown_contract(text, draft)
    if errors:
        raise ValueError("FAQ 不符合入库规范：" + "；".join(errors[:8]) + (
            f"（另有 {len(errors) - 8} 项）" if len(errors) > 8 else ""
        ))


def enforce_handbook_contract(text: str, roots: list[OutlineNode]) -> None:
    if not ingest_strict_enabled():
        return
    errors = validate_handbook_contract(text, roots)
    if errors:
        raise ValueError("手册不符合入库规范：" + "；".join(errors))