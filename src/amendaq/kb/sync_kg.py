from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from amendaq.db.catalog_mode import CATALOG_FLAT_FAQ
from amendaq.graph.extract import knowledge_graph_from_outline_roots
from amendaq.graph.persist import persist_graph
from amendaq.log import get_logger
from amendaq.wiki.outline import OutlineNode

logger = get_logger(__name__)

CHAPTER_REF = "1"
DEFAULT_CHAPTER_TITLE = "问答"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_id_for_section(document_id: str, section_ref: str) -> str:
    return f"{document_id}_{section_ref.replace('.', '_')}"


def ensure_kg_document(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    title: str,
    source_uri: str = "",
) -> None:
    ts = _now()
    row = conn.execute(
        "SELECT document_id FROM kg_document WHERE document_id = ?",
        (document_id,),
    ).fetchone()
    uri = source_uri or f"kb://{document_id}"
    if row:
        conn.execute(
            """
            UPDATE kg_document SET title = ?, catalog_mode = ?, source_uri = COALESCE(NULLIF(?, ''), source_uri)
            WHERE document_id = ?
            """,
            (title, CATALOG_FLAT_FAQ, uri, document_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO kg_document (document_id, title, source_uri, ingested_at, catalog_mode)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, title, uri, ts, CATALOG_FLAT_FAQ),
        )


def sync_kb_to_kg(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    display_title: str,
) -> int:
    """Flatten kb_faq_item → kg_entity (+ section_ref on items). No wiki_toc_node."""
    ensure_kg_document(conn, document_id=document_id, title=display_title)
    rows = conn.execute(
        """
        SELECT item_id, question, answer, status, sort_key, disabled
        FROM kb_faq_item
        WHERE document_id = ? AND disabled = 0
        ORDER BY sort_key, created_at
        """,
        (document_id,),
    ).fetchall()

    chapter = OutlineNode(
        node_key="default",
        kind="chapter",
        section_ref=CHAPTER_REF,
        title=DEFAULT_CHAPTER_TITLE,
    )
    leaf_quotes: dict[str, str] = {}
    ts = _now()
    count = 0
    for idx, row in enumerate(rows, start=1):
        body = (row["answer"] or "").strip()
        question = (row["question"] or "").strip()
        if not question or not body:
            continue
        leaf_ref = f"{CHAPTER_REF}.{idx}"
        summary = body[:280] + ("…" if len(body) > 280 else "")
        quote = body if len(body) <= 600 else body[:600]
        leaf_quotes[leaf_ref] = quote
        chapter.children.append(
            OutlineNode(
                node_key=str(row["item_id"]),
                kind="leaf",
                section_ref=leaf_ref,
                title=question,
                body=body,
                summary=summary,
            )
        )
        conn.execute(
            "UPDATE kb_faq_item SET section_ref = ?, updated_at = ? WHERE item_id = ?",
            (leaf_ref, ts, row["item_id"]),
        )
        count += 1

    graph = knowledge_graph_from_outline_roots(
        [chapter],
        document_id=document_id,
        title=display_title,
        source_uri=f"kb://{document_id}",
        leaf_quotes=leaf_quotes,
    )
    persist_graph(graph, conn=conn, catalog_mode=CATALOG_FLAT_FAQ)
    logger.info(
        "joyjoy: kb sync kg document_id=%s items=%s entities=%s",
        document_id,
        count,
        len(graph.entities),
    )
    return count