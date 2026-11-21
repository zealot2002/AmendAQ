from __future__ import annotations

import re
from dataclasses import dataclass

from mycs.wiki.compile import compile_faq_markdown_rules

QUESTION_LINE = re.compile(r"^###\s+Q\d+[^\n]*\s*$", re.MULTILINE)


@dataclass
class ParsedFaqRow:
    question: str
    answer: str


def _strip_q_prefix(title: str) -> str:
    t = title.strip()
    m = re.match(r"^Q\d+[.．、:\s]*", t, re.IGNORECASE)
    if m:
        return t[m.end() :].strip()
    return t


def parse_faq_import_text(text: str, *, default_title: str = "导入 FAQ") -> list[ParsedFaqRow]:
    """
    标准：`Q1：问题` 下一行 `A1：答案`，可连续多题。
    仍兼容旧稿：### Qn + **答：**、`1. Q：`、以及「问：」「答：」。
    """
    raw = (text or "").strip()
    if not raw:
        return []

    paired = _parse_qna_pairs(raw)
    if paired:
        return paired

    if QUESTION_LINE.search(raw) or raw.lstrip().startswith("#"):
        # 「### Q1」也以 # 开头，不能据此判断已经有标题。没有章节时补一章，否则解析结果为空。
        if not re.search(r"(?m)^##\s+\S", raw):
            raw = f"## 导入\n\n{raw}"
        if not re.search(r"(?m)^#\s+\S", raw):
            raw = f"# {default_title}\n\n{raw}"
        draft = compile_faq_markdown_rules(raw, source_uri="import://batch")
        rows: list[ParsedFaqRow] = []
        for leaf in draft.leaves:
            if hasattr(leaf, "title"):
                q_title = str(leaf.title or "")
                body = str(leaf.body or "").strip()
            else:
                q_title = str((leaf or {}).get("title") or "")  # type: ignore[union-attr]
                body = str((leaf or {}).get("body") or "").strip()  # type: ignore[union-attr]
            rows.append(
                ParsedFaqRow(
                    question=_strip_q_prefix(q_title),
                    answer=body,
                )
            )
        return [r for r in rows if r.question and r.answer]

    numbered = _parse_numbered_qa_blocks(raw)
    if numbered:
        return numbered
    return _parse_qa_blocks_loose(raw)


_QN_LINE = re.compile(r"^Q\s*(\d+)\s*[：:]\s*(.*)$", re.IGNORECASE)
_AN_LINE = re.compile(r"^A\s*(\d+)\s*[：:]\s*(.*)$", re.IGNORECASE)


def _parse_qna_pairs(text: str) -> list[ParsedFaqRow]:
    """Q1：问题 / A1：答案。问题和答案都可以续行，直到下一个 Q 或 A。"""
    if not re.search(r"(?im)^Q\s*\d+\s*[：:]", text):
        return []
    rows: list[ParsedFaqRow] = []
    question_parts: list[str] = []
    answer_parts: list[str] = []
    in_answer = False

    def flush() -> None:
        nonlocal question_parts, answer_parts, in_answer
        question = "\n".join(question_parts).strip()
        answer = "\n".join(answer_parts).strip()
        if question and answer:
            rows.append(ParsedFaqRow(question=question, answer=answer))
        question_parts = []
        answer_parts = []
        in_answer = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        question_line = _QN_LINE.match(line)
        if question_line:
            flush()
            if question_line.group(2).strip():
                question_parts.append(question_line.group(2).strip())
            continue
        answer_line = _AN_LINE.match(line)
        if answer_line and question_parts:
            in_answer = True
            if answer_line.group(2).strip():
                answer_parts.append(answer_line.group(2).strip())
            continue
        if not line:
            if in_answer and answer_parts:
                answer_parts.append("")
            elif question_parts:
                question_parts.append("")
            continue
        if in_answer:
            answer_parts.append(line)
        elif question_parts:
            question_parts.append(line)
    flush()
    return rows


_Q_LINE = re.compile(
    r"^(?:\d+[.．、]\s*)?(?:问|Q)\s*[：:]\s*(.+)$",
    re.IGNORECASE,
)
_A_LINE = re.compile(
    r"^(?:答|A)\s*[：:]\s*(.*)$",
    re.IGNORECASE,
)


def _parse_numbered_qa_blocks(text: str) -> list[ParsedFaqRow]:
    """1. Q：题干 / A：答案（星河手册 FAQ 清单常见格式）。"""
    if not re.search(r"(?:^|\n)\s*\d+[.．、]\s*Q\s*[：:]", text, re.IGNORECASE | re.MULTILINE):
        return []
    rows: list[ParsedFaqRow] = []
    blocks = re.split(r"(?=^\s*\d+[.．、]\s*Q\s*[：:])", text.strip(), flags=re.MULTILINE | re.IGNORECASE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        if not lines:
            continue
        mq = _Q_LINE.match(lines[0].strip())
        if not mq:
            continue
        question = _strip_q_prefix(mq.group(1).strip())
        answer_parts: list[str] = []
        for ln in lines[1:]:
            ln = ln.strip()
            if not ln:
                continue
            ma = _A_LINE.match(ln)
            if ma:
                if ma.group(1).strip():
                    answer_parts.append(ma.group(1).strip())
                continue
            if _Q_LINE.match(ln):
                break
            answer_parts.append(ln)
        answer = "\n".join(answer_parts).strip()
        if question and answer:
            rows.append(ParsedFaqRow(question=question, answer=answer))
    return rows


def _parse_qa_blocks_loose(text: str) -> list[ParsedFaqRow]:
    rows: list[ParsedFaqRow] = []
    lines = text.splitlines()
    i = 0
    q_re = _Q_LINE
    a_re = _A_LINE

    while i < len(lines):
        line = lines[i].strip()
        mq = q_re.match(line)
        if not mq:
            i += 1
            continue
        question = mq.group(1).strip()
        answer_parts: list[str] = []
        i += 1
        while i < len(lines):
            ln = lines[i].strip()
            if q_re.match(ln):
                break
            ma = a_re.match(ln)
            if ma:
                if ma.group(1).strip():
                    answer_parts.append(ma.group(1).strip())
                i += 1
                while i < len(lines):
                    nxt = lines[i].strip()
                    if not nxt or q_re.match(nxt):
                        break
                    if a_re.match(nxt):
                        break
                    answer_parts.append(nxt)
                    i += 1
                break
            if not ln:
                i += 1
                if answer_parts:
                    break
                continue
            if not answer_parts:
                answer_parts.append(ln)
            else:
                answer_parts.append(ln)
            i += 1
        answer = "\n".join(answer_parts).strip()
        if question and answer:
            rows.append(ParsedFaqRow(question=question, answer=answer))
    return rows