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
    规范 Markdown：### Qn. 题干 + **答：** 答案。
    宽松 txt：`1. Q：…` + `A：…`、或「问：」「答：」成对文本。
    """
    raw = (text or "").strip()
    if not raw:
        return []

    if QUESTION_LINE.search(raw) or raw.lstrip().startswith("#"):
        if not raw.lstrip().startswith("#"):
            raw = f"# {default_title}\n\n## 导入\n\n{raw}"
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