from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from mycs.knowledge.service import ensure_database
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.wiki.compile import compile_faq_markdown_rules
from mycs.wiki.ingest_progress import report_ingest_progress, wrap_progress

logger = get_logger(__name__)

_FORMAT_HINT = (
    "纯文本 / 不规范排版时，请开启「大模型整理为 FAQ」后重试；"
    "或整理为规范 .md（## 模块 + ### Qn + **答：**）。"
)

_DOC_SPEC_MD = (
    "Markdown：一级标题为文档名；模块用 ##；每题 ### Qn. 标题；答案以 **答：** 开头。"
)


def _looks_faq_markdown(text: str) -> bool:
    return "##" in text and ("###" in text or "答" in text or "答：" in text)


def _env_bool(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


def ingest_document_file(
    src: Path,
    *,
    document_id: str,
    on_progress: Callable[[str, int, str], None] | None = None,
    use_llm: bool | None = None,
) -> None:
    """FAQ 入库：优先规范 md 规则解析；否则大模型 compile → Wiki 草稿（可二次编辑）。"""
    progress = wrap_progress(on_progress) if on_progress else None
    text = src.read_text(encoding="utf-8")
    source_uri = f"file://{src.resolve()}"

    if use_llm is None:
        use_llm = _env_bool("MYCS_INGEST_FAQ_LLM", "1")

    from mycs.wiki.ingest_compile import ingest_compile_file

    rules_first = _env_bool("MYCS_INGEST_RULES_FIRST", "1")
    if rules_first and _looks_faq_markdown(text):
        preview = compile_faq_markdown_rules(text, source_uri=source_uri)
        if preview.leaves:
            if progress:
                report_ingest_progress(
                    progress, stage="parse", percent=15, message="按 FAQ 规范解析 Markdown"
                )
            log_step(
                logger,
                "workflow_ingest_faq_rules",
                document_id=document_id,
                source=str(src),
                leaves=len(preview.leaves),
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

    if use_llm:
        from mycs.llm.factory import create_llm

        if progress:
            report_ingest_progress(
                progress,
                stage="compile",
                percent=12,
                message="大模型整理为 FAQ（首次可能较慢）…",
            )
        log_step(
            logger,
            "workflow_ingest_faq_llm",
            document_id=document_id,
            source=str(src),
            chars=len(text),
        )
        try:
            ingest_compile_file(
                src,
                document_id=document_id,
                llm=create_llm(),
                rules_only=False,
                on_progress=progress,
            )
        except ValueError as exc:
            raise ValueError(f"{exc}。{_FORMAT_HINT}") from exc
        return

    raise ValueError(
        f"无法按规则解析该文档，且未启用大模型整理。{_FORMAT_HINT} {_DOC_SPEC_MD}"
    )


def run_ingest_uploaded(
    document_id: str,
    on_progress: Callable[[str, int, str], None] | None = None,
    *,
    use_llm: bool | None = None,
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
    log_step(
        logger,
        "workflow_ingest_start",
        document_id=doc,
        source=str(src),
        use_llm=use_llm,
    )
    ingest_document_file(src, document_id=doc, on_progress=on_progress, use_llm=use_llm)
    set_active_document_id(doc)
    st = workflow_state(doc)
    if (st.get("draft_nodes") or 0) == 0:
        raise ValueError(f"未生成目录条目。{_FORMAT_HINT}")
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