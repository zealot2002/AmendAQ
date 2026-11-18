from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from mycs.graph.extract import ingest_txt_file
from mycs.wiki.ingest_contract import enforce_handbook_contract
from mycs.wiki.outline import parse_outline_from_text
from mycs.knowledge.service import ensure_database
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.wiki.ingest_progress import report_ingest_progress, wrap_progress

logger = get_logger(__name__)

_FORMAT_HINT = (
    "文档不符合规范：.md 须为「## 模块 + ### 问 + 答：」FAQ；"
    ".txt 须为「1. 章 + 1.1 节」编号手册。"
)

_DOC_SPEC_MD = (
    "Markdown：一级标题为文档名；模块用 ##；每题 ### Qn. 标题；答案以 **答：** 开头。"
)
_DOC_SPEC_TXT = (
    "文本：章用「1. 标题」；节用「1.1 标题」；节下为正文。"
)


def _looks_faq_markdown(text: str) -> bool:
    return "##" in text and ("###" in text or "答" in text or "答：" in text)


def ingest_document_file(
    src: Path,
    *,
    document_id: str,
    on_progress: Callable[[str, int, str], None] | None = None,
) -> None:
    """Deterministic ingest only — no LLM. FAQ-shaped md or numbered txt."""
    progress = wrap_progress(on_progress) if on_progress else None
    text = src.read_text(encoding="utf-8")
    ext = src.suffix.lower()

    force_legacy = os.environ.get("MYCS_INGEST_LEGACY_TXT", "").strip() in ("1", "true", "yes")
    use_faq = ext in {".md", ".markdown"} or _looks_faq_markdown(text)

    if use_faq and not force_legacy:
        from mycs.wiki.ingest_compile import ingest_compile_file

        if progress:
            report_ingest_progress(
                progress, stage="parse", percent=15, message="按 FAQ 规范解析 Markdown"
            )
        log_step(
            logger,
            "workflow_ingest_faq_rules",
            document_id=document_id,
            source=str(src),
            spec=_DOC_SPEC_MD,
        )
        try:
            ingest_compile_file(
                src,
                document_id=document_id,
                llm=None,
                rules_only=True,
                on_progress=progress,
            )
        except ValueError as exc:
            raise ValueError(f"{exc}。{_FORMAT_HINT} {_DOC_SPEC_MD}") from exc
        return

    if progress:
        report_ingest_progress(
            progress, stage="parse", percent=20, message="按编号章节解析 txt"
        )
    source_uri = f"file://{src.resolve()}"
    roots = parse_outline_from_text(text, source_uri=source_uri)
    try:
        enforce_handbook_contract(text, roots)
    except ValueError as exc:
        raise ValueError(f"{exc}。{_FORMAT_HINT} {_DOC_SPEC_TXT}") from exc
    log_step(
        logger,
        "workflow_ingest_numbered_txt",
        document_id=document_id,
        source=str(src),
        spec=_DOC_SPEC_TXT,
    )
    ingest_txt_file(src, document_id=document_id)
    if progress:
        report_ingest_progress(progress, stage="done", percent=100, message="整理完成")


def run_ingest_uploaded(
    document_id: str,
    on_progress: Callable[[str, int, str], None] | None = None,
) -> dict:
    from mycs.ui.active_document import resolve_active_document_id, set_active_document_id
    from mycs.ui.workflow import _ensure_upload_dir, workflow_state

    ensure_database()
    doc = (document_id or "").strip() or resolve_active_document_id()
    if not doc:
        raise ValueError("请先上传文档")
    candidates = list(_ensure_upload_dir().glob(f"{doc}*"))
    if not candidates:
        raise ValueError("请先上传文档")
    src = max(candidates, key=lambda p: p.stat().st_mtime)
    log_step(logger, "workflow_ingest_start", document_id=doc, source=str(src))
    ingest_document_file(src, document_id=doc, on_progress=on_progress)
    set_active_document_id(doc)
    st = workflow_state(doc)
    if (st.get("draft_nodes") or 0) == 0:
        raise ValueError(
            f"未生成目录条目，请检查文档格式。{_FORMAT_HINT} {_DOC_SPEC_TXT} {_DOC_SPEC_MD}"
        )
    log_step(
        logger,
        "workflow_ingest_done",
        document_id=doc,
        draft_nodes=st.get("draft_nodes"),
        mount_id=st.get("mount_id"),
        workflow_step=st.get("current_step"),
    )
    from mycs.ui import wiki_admin

    return {
        "document_id": doc,
        "workflow": st,
        "toc": wiki_admin.get_toc(doc),
    }