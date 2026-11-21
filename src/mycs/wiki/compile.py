from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.prompts import prompt
from mycs.wiki.canonical import WikiCanonicalDraft
from mycs.wiki.ingest_progress import IngestProgressFn, noop_ingest_progress, report_ingest_progress

logger = get_logger(__name__)


def compile_system() -> str:
    return prompt("compile")

CHAPTER_MD = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
QUESTION_MD = re.compile(r"^###\s+(Q\d+[^\n]*)\s*$", re.MULTILINE)
ANSWER_MARK = re.compile(r"\*\*答[：:]\*\*\s*")

CHUNK_BY = re.compile(r"(?=^##\s+)", re.MULTILINE)
MAX_SINGLE_PASS_CHARS = int(os.environ.get("MYCS_COMPILE_CHUNK_CHARS", "14000"))


class JsonChatLLM(Protocol):
    def _json_chat(
        self, system: str, user: str, max_tokens: int | None = ...
    ) -> dict[str, Any]: ...


def compile_faq_markdown_rules(text: str, *, source_uri: str = "") -> WikiCanonicalDraft:
    """Deterministic FAQ compiler (## modules + ### Qn + 答：)."""
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    doc_title = (title_match.group(1).strip() if title_match else "FAQ").strip()
    notes: list[str] = []

    chapters: list[dict[str, str]] = []
    leaves: list[dict[str, Any]] = []
    chap_idx = 0
    leaf_counters: dict[str, int] = {}

    chapter_spans = list(CHAPTER_MD.finditer(text))
    if not chapter_spans:
        notes.append("rules: no ## chapters found")
        return WikiCanonicalDraft.from_dict(
            {"document": {"title": doc_title}, "chapters": [], "leaves": [], "ingest_notes": notes}
        )

    for i, m in enumerate(chapter_spans):
        chap_idx += 1
        ch_ref = str(chap_idx)
        ch_title = m.group(1).strip()
        chapters.append({"section_ref": ch_ref, "title": ch_title})
        leaf_counters[ch_ref] = 0
        start = m.end()
        end = chapter_spans[i + 1].start() if i + 1 < len(chapter_spans) else len(text)
        block = text[start:end]
        q_iter = list(QUESTION_MD.finditer(block))
        for j, qm in enumerate(q_iter):
            q_title = qm.group(1).strip()
            q_start = qm.end()
            q_end = q_iter[j + 1].start() if j + 1 < len(q_iter) else len(block)
            qa_block = block[q_start:q_end].strip()
            body = qa_block
            am = ANSWER_MARK.search(qa_block)
            if am:
                body = qa_block[am.end() :].strip()
            elif qa_block:
                body = qa_block
            if not body:
                notes.append(f"rules: empty answer under {q_title} in chapter {ch_ref}")
                continue
            leaf_counters[ch_ref] += 1
            leaf_ref = f"{ch_ref}.{leaf_counters[ch_ref]}"
            quote = body if len(body) <= 600 else body[:600]
            summary = body[:280] + ("…" if len(body) > 280 else "")
            leaves.append(
                {
                    "section_ref": leaf_ref,
                    "parent_ref": ch_ref,
                    "title": q_title,
                    "summary": summary,
                    "body": body,
                    "evidence": {
                        "quote": quote,
                        "source_uri": source_uri,
                        "effective_from": "",
                    },
                }
            )

    q_nums = [int(x) for x in re.findall(r"^###\s+Q(\d+)", text, re.MULTILINE)]
    if q_nums:
        expected = set(range(min(q_nums), max(q_nums) + 1))
        found = set(q_nums)
        missing = sorted(expected - found)
        if missing:
            notes.append(f"rules: missing question numbers in markdown: {missing}")

    draft = WikiCanonicalDraft.from_dict(
        {
            "document": {"title": doc_title},
            "chapters": chapters,
            "leaves": leaves,
            "ingest_notes": notes,
        }
    )
    log_step(
        logger,
        "compile_faq_rules_done",
        title=doc_title,
        chapters=len(chapters),
        leaves=len(leaves),
        notes=len(notes),
    )
    return draft


def _split_compile_chunks(text: str) -> list[str]:
    parts = CHUNK_BY.split(text)
    chunks: list[str] = []
    buf = ""
    for p in parts:
        if not p.strip():
            continue
        if len(buf) + len(p) > MAX_SINGLE_PASS_CHARS and buf:
            chunks.append(buf)
            buf = p
        else:
            buf = (buf + p) if buf else p
    if buf.strip():
        chunks.append(buf)
    return chunks if chunks else [text]


def _llm_compile_piece(llm: JsonChatLLM, text: str, *, source_uri: str) -> WikiCanonicalDraft:
    user = json.dumps(
        {"source_uri": source_uri, "markdown": text},
        ensure_ascii=False,
    )
    data = llm._json_chat(compile_system(), user, max_tokens=8192)
    if source_uri:
        for lf in data.get("leaves") or []:
            ev = lf.get("evidence") or {}
            if not ev.get("source_uri"):
                ev["source_uri"] = source_uri
                lf["evidence"] = ev
    return WikiCanonicalDraft.from_dict(data)


def _merge_chunk_drafts(base: WikiCanonicalDraft, extra: WikiCanonicalDraft) -> WikiCanonicalDraft:
    ch_offset = len(base.chapters)
    ref_map: dict[str, str] = {}
    chapters = list(base.chapters)
    for i, ch in enumerate(extra.chapters):
        new_ref = str(ch_offset + i + 1)
        ref_map[ch.section_ref.rstrip(".")] = new_ref
        ref_map[ch.section_ref] = new_ref
        chapters.append(
            type(ch)(section_ref=new_ref, title=ch.title)
        )
    leaves = list(base.leaves)
    for lf in extra.leaves:
        parent = ref_map.get(lf.parent_ref.rstrip("."), lf.parent_ref)
        parent_leaf_idx = sum(1 for x in leaves if x.parent_ref == parent) + 1
        new_sec = f"{parent}.{parent_leaf_idx}"
        leaves.append(
            type(lf)(
                section_ref=new_sec,
                parent_ref=parent,
                title=lf.title,
                summary=lf.summary,
                body=lf.body,
                evidence=lf.evidence,
            )
        )
    notes = base.ingest_notes + extra.ingest_notes
    return WikiCanonicalDraft(
        document_title=base.document_title or extra.document_title,
        chapters=chapters,
        leaves=leaves,
        ingest_notes=notes,
    )


def compile_wiki_draft(
    llm: JsonChatLLM | None,
    text: str,
    *,
    source_uri: str = "",
    rules_only: bool | None = None,
    on_progress: IngestProgressFn | None = None,
) -> WikiCanonicalDraft:
    """
    Compile markdown/text to WikiCanonicalDraft.
    rules_only=True: FAQ markdown rules (tests/CLI). rules_only=False: LLM required, no silent rules fallback.
    """
    if rules_only is None:
        rules_only = llm is None or os.environ.get("MYCS_COMPILE_LLM", "").strip() not in (
            "1",
            "true",
            "yes",
        )

    if not rules_only and llm is None:
        raise ValueError("compile_wiki_draft: LLM required when rules_only=False")

    progress = on_progress or noop_ingest_progress
    log_step(logger, "compile_wiki_draft_start", chars=len(text), rules_only=rules_only)
    rules_draft = compile_faq_markdown_rules(text, source_uri=source_uri)

    use_llm = not rules_only and llm is not None
    if rules_only or (rules_draft.leaves and not use_llm):
        log_step(
            logger,
            "compile_wiki_draft_rules",
            leaves=len(rules_draft.leaves),
            chapters=len(rules_draft.chapters),
        )
        return rules_draft

    assert llm is not None
    chunks = _split_compile_chunks(text)
    log_step(logger, "compile_wiki_llm_chunks", count=len(chunks))
    report_ingest_progress(
        progress,
        stage="compile",
        percent=18,
        message=f"大模型编译：共 {len(chunks)} 个分块",
    )
    merged: WikiCanonicalDraft | None = None
    for idx, chunk in enumerate(chunks):
        pct = 18 + int(52 * (idx + 1) / max(1, len(chunks)))
        report_ingest_progress(
            progress,
            stage="compile",
            percent=pct,
            message=f"大模型编译分块 {idx + 1}/{len(chunks)}（调用中…）",
        )
        logger.info("joyjoy: compile chunk %s/%s chars=%s", idx + 1, len(chunks), len(chunk))
        piece = _llm_compile_piece(llm, chunk, source_uri=source_uri)
        log_step(
            logger,
            "compile_wiki_llm_chunk_done",
            index=idx + 1,
            total=len(chunks),
            leaves=len(piece.leaves),
        )
        if merged is None:
            merged = piece
        else:
            merged = _merge_chunk_drafts(merged, piece)

    if merged is None or not merged.leaves:
        logger.error("joyjoy: compile llm empty, no rules fallback")
        raise ValueError("LLM 编译结果为空（未生成任何章节条目），请检查原文或模型输出")
    if not merged.chapters and rules_draft.chapters:
        merged.chapters = rules_draft.chapters
    if rules_draft.ingest_notes:
        merged.ingest_notes = merged.ingest_notes + rules_draft.ingest_notes
    log_step(
        logger,
        "compile_wiki_draft_done",
        chapters=len(merged.chapters),
        leaves=len(merged.leaves),
    )
    return merged