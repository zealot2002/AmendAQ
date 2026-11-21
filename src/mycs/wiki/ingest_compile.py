from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mycs.document_display import infer_handbook_display_title
from mycs.db.connection import connect, get_db_path
from mycs.db.catalog_mode import infer_catalog_mode
from mycs.graph.persist import export_graph_json, persist_graph
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.wiki.canonical import (
    WikiCanonicalDraft,
    canonical_to_outline_roots,
    leaf_evidence_quotes,
    validate_canonical,
)
from mycs.wiki.compile import compile_wiki_draft
from mycs.wiki.ingest_contract import enforce_faq_contract
from mycs.wiki.ingest_progress import IngestProgressFn, noop_ingest_progress, report_ingest_progress
from mycs.wiki.toc_persist import ingest_document_toc_from_roots, publish_mount

logger = get_logger(__name__)


def ingest_compile_file(
    path: Path,
    *,
    document_id: str | None = None,
    llm: Any = None,
    rules_only: bool | None = None,
    canonical_out: Path | None = None,
    validate: bool = True,
    publish: bool = False,
    on_progress: IngestProgressFn | None = None,
) -> dict[str, Any]:
    progress = on_progress or noop_ingest_progress
    report_ingest_progress(progress, stage="read", percent=5, message="读取源文件")
    text = path.read_text(encoding="utf-8")
    doc_id = document_id or path.stem
    source_uri = f"file://{path.resolve()}"
    title = infer_handbook_display_title(
        document_id=doc_id,
        path=path,
        text=text,
        stored_title=path.name,
    )
    log_step(
        logger,
        "ingest_compile_start",
        path=str(path),
        document_id=doc_id,
        chars=len(text),
    )
    report_ingest_progress(
        progress, stage="compile", percent=12, message=f"结构化解析（{len(text)} 字）"
    )
    draft = compile_wiki_draft(
        llm,
        text,
        source_uri=source_uri,
        rules_only=rules_only,
        on_progress=progress,
    )
    report_ingest_progress(progress, stage="validate", percent=65, message="校验 FAQ 排版规范")
    if rules_only:
        enforce_faq_contract(text, draft)
    report_ingest_progress(
        progress,
        stage="validate",
        percent=72,
        message=f"校验结构：{len(draft.chapters)} 章 / {len(draft.leaves)} 条",
    )
    errors = validate_canonical(draft) if validate else []
    if errors:
        log_step(logger, "ingest_compile_validate_failed", errors=errors)
        raise ValueError("canonical validation failed: " + "; ".join(errors))

    out_path = canonical_out or (
        Path(__file__).resolve().parents[3] / "data" / "ingest" / f"{doc_id}.canonical.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(draft.to_json(), encoding="utf-8")
    log_step(logger, "ingest_compile_canonical_saved", path=str(out_path))

    report_ingest_progress(progress, stage="persist", percent=82, message="写入 Wiki 草稿与知识点")
    roots = canonical_to_outline_roots(draft)
    quotes = leaf_evidence_quotes(draft)
    conn = connect(get_db_path())
    try:
        meta = ingest_document_toc_from_roots(
            conn,
            roots,
            document_id=doc_id,
            title=title,
            source_uri=source_uri,
            graph_from="outline",
            leaf_quotes=quotes,
        )
        if publish:
            pub = publish_mount(conn, meta["mount_id"])
            log_step(logger, "ingest_compile_publish", mount_id=meta["mount_id"], result=pub)
        conn.commit()
    finally:
        conn.close()

    from mycs.graph.extract import knowledge_graph_from_outline_roots

    graph = knowledge_graph_from_outline_roots(
        roots,
        document_id=doc_id,
        title=title,
        source_uri=source_uri,
        leaf_quotes=quotes,
    )
    kg_path = Path(__file__).resolve().parents[3] / "data" / "kg" / f"{doc_id}.json"
    export_graph_json(graph, kg_path)
    report_ingest_progress(progress, stage="done", percent=100, message="整理目录完成")

    log_step(
        logger,
        "ingest_compile_done",
        document_id=doc_id,
        chapters=len(draft.chapters),
        leaves=len(draft.leaves),
        ingest_notes=draft.ingest_notes,
        canonical_json=str(out_path),
    )
    logger.info(
        "joyjoy: ingest_compile document_id=%s chapters=%s leaves=%s notes=%s",
        doc_id,
        len(draft.chapters),
        len(draft.leaves),
        len(draft.ingest_notes),
    )
    return {
        **meta,
        "canonical_json": str(out_path),
        "ingest_notes": draft.ingest_notes,
        "chapters": len(draft.chapters),
        "leaves": len(draft.leaves),
    }


def ingest_canonical_json(
    path: Path,
    *,
    document_id: str | None = None,
    publish: bool = False,
) -> dict[str, Any]:
    """Load data/ingest/<doc>.canonical.json (or export) into Wiki + kg."""
    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    draft = WikiCanonicalDraft.from_dict(data)
    errors = validate_canonical(draft)
    if errors:
        raise ValueError("canonical validation failed: " + "; ".join(errors))

    stem = path.stem
    if stem.endswith(".canonical"):
        stem = stem[: -len(".canonical")]
    doc_id = document_id or stem or "document"
    source_uri = f"file://{path.resolve()}"
    title = draft.document_title or doc_id

    log_step(
        logger,
        "ingest_canonical_start",
        path=str(path),
        document_id=doc_id,
        chapters=len(draft.chapters),
        leaves=len(draft.leaves),
    )

    roots = canonical_to_outline_roots(draft)
    quotes = leaf_evidence_quotes(draft)
    conn = connect(get_db_path())
    try:
        meta = ingest_document_toc_from_roots(
            conn,
            roots,
            document_id=doc_id,
            title=title,
            source_uri=source_uri,
            graph_from="outline",
            leaf_quotes=quotes,
        )
        if publish:
            pub = publish_mount(conn, meta["mount_id"])
            log_step(logger, "ingest_canonical_publish", mount_id=meta["mount_id"], result=pub)
        conn.commit()
    finally:
        conn.close()

    from mycs.graph.extract import knowledge_graph_from_outline_roots

    graph = knowledge_graph_from_outline_roots(
        roots,
        document_id=doc_id,
        title=title,
        source_uri=source_uri,
        leaf_quotes=quotes,
    )
    persist_graph(
        graph,
        catalog_mode=infer_catalog_mode(doc_id),
    )
    kg_path = Path(__file__).resolve().parents[3] / "data" / "kg" / f"{doc_id}.json"
    export_graph_json(graph, kg_path)

    log_step(
        logger,
        "ingest_canonical_done",
        document_id=doc_id,
        mount_id=meta.get("mount_id"),
        published=publish,
    )
    return {
        **meta,
        "canonical_json": str(path),
        "chapters": len(draft.chapters),
        "leaves": len(draft.leaves),
    }