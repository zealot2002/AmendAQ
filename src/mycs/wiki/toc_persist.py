from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from mycs.graph.extract import SectionGraphBuilder
from mycs.graph.model import KnowledgeGraph
from mycs.graph.persist import export_graph_json, persist_graph
from mycs.log import get_logger
from mycs.wiki.outline import OutlineNode, parse_outline_from_text

logger = get_logger(__name__)

WIKI_ROOT_ID = "wiki_root"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_wiki_root(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT node_id FROM wiki_toc_node WHERE node_id = ?", (WIKI_ROOT_ID,)
    ).fetchone()
    if row:
        return WIKI_ROOT_ID
    ts = _now()
    conn.execute(
        """
        INSERT INTO wiki_toc_node (
            node_id, parent_id, mount_id, document_id, kind, section_ref,
            title, summary, body, sort_key, depth, status, created_at, updated_at
        ) VALUES (?, NULL, ?, NULL, 'root', '', 'Enterprise Wiki', '', '', 0, 0, 'published', ?, ?)
        """,
        (WIKI_ROOT_ID, "__root__", ts, ts),
    )
    return WIKI_ROOT_ID


def ensure_mount(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    display_title: str | None = None,
) -> str:
    ensure_wiki_root(conn)
    mount_id = f"mount_{document_id}"
    row = conn.execute(
        "SELECT mount_id FROM wiki_document_mount WHERE mount_id = ?", (mount_id,)
    ).fetchone()
    if row:
        return mount_id
    ts = _now()
    title = display_title or document_id
    mount_node_id = f"node_{mount_id}"
    conn.execute(
        """
        INSERT INTO wiki_toc_node (
            node_id, parent_id, mount_id, document_id, kind, section_ref,
            title, summary, body, sort_key, depth, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'volume', '', ?, '', '', 0, 1, 'published', ?, ?)
        """,
        (mount_node_id, WIKI_ROOT_ID, mount_id, document_id, title, ts, ts),
    )
    conn.execute(
        """
        INSERT INTO wiki_document_mount (
            mount_id, document_id, parent_node_id, display_title, sort_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 0, ?, ?)
        """,
        (mount_id, document_id, mount_node_id, title, ts, ts),
    )
    return mount_id


def ingest_document_toc_draft(
    conn: sqlite3.Connection,
    text: str,
    *,
    document_id: str,
    title: str,
    source_uri: str,
) -> dict[str, Any]:
    """Parse outline, write draft TOC nodes, sync kg graph."""
    mount_id = ensure_mount(conn, document_id=document_id, display_title=title)
    conn.execute(
        "DELETE FROM wiki_toc_node WHERE mount_id = ? AND status = 'draft'",
        (mount_id,),
    )
    roots = parse_outline_from_text(text, source_uri=source_uri)
    mount_row = conn.execute(
        "SELECT parent_node_id FROM wiki_document_mount WHERE mount_id = ?",
        (mount_id,),
    ).fetchone()
    mount_node_id = mount_row["parent_node_id"]
    ts = _now()
    count = 0
    sort_ch = 0
    for ch in roots:
        sort_ch += 1
        ch_id = f"{mount_id}_draft_{ch.node_key}"
        conn.execute(
            """
            INSERT INTO wiki_toc_node (
                node_id, parent_id, mount_id, document_id, kind, section_ref,
                title, summary, body, sort_key, depth, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'chapter', ?, ?, '', '', ?, 2, 'draft', ?, ?)
            """,
            (
                ch_id,
                mount_node_id,
                mount_id,
                document_id,
                ch.section_ref,
                ch.title,
                sort_ch,
                ts,
                ts,
            ),
        )
        count += 1
        sort_leaf = 0
        for leaf in ch.children:
            sort_leaf += 1
            entity_id = f"{document_id}_{leaf.section_ref.replace('.', '_')}"
            leaf_id = f"{mount_id}_draft_{leaf.node_key}"
            conn.execute(
                """
                INSERT INTO wiki_toc_node (
                    node_id, parent_id, mount_id, document_id, kind, section_ref,
                    title, summary, body, sort_key, depth, entity_id, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'leaf', ?, ?, ?, ?, ?, 3, ?, 'draft', ?, ?)
                """,
                (
                    leaf_id,
                    ch_id,
                    mount_id,
                    document_id,
                    leaf.section_ref,
                    leaf.title,
                    leaf.summary,
                    leaf.body,
                    sort_leaf,
                    entity_id,
                    ts,
                    ts,
                ),
            )
            count += 1

    builder = SectionGraphBuilder()
    graph: KnowledgeGraph = builder.extract(
        text,
        document_id=document_id,
        title=title,
        source_uri=source_uri,
    )
    persist_graph(graph, conn=conn)
    logger.info(
        "joyjoy: draft toc mount=%s nodes=%s entities=%s",
        mount_id,
        count,
        len(graph.entities),
    )
    return {
        "mount_id": mount_id,
        "document_id": document_id,
        "draft_nodes": count,
        "entities": len(graph.entities),
        "status": "draft",
    }


def publish_mount(
    conn: sqlite3.Connection,
    mount_id: str,
    *,
    actor: str = "system",
) -> dict[str, Any]:
    ts = _now()
    archived = conn.execute(
        """
        UPDATE wiki_toc_node SET status = 'archived', updated_at = ?
        WHERE mount_id = ? AND status = 'published' AND kind IN ('chapter', 'leaf')
        """,
        (ts, mount_id),
    ).rowcount
    promoted = conn.execute(
        """
        UPDATE wiki_toc_node SET status = 'published', updated_at = ?
        WHERE mount_id = ? AND status = 'draft'
        """,
        (ts, mount_id),
    ).rowcount
    conn.execute(
        """
        INSERT INTO wiki_publish_audit (mount_id, action, node_count, actor, detail, created_at)
        VALUES (?, 'publish', ?, ?, ?, ?)
        """,
        (mount_id, promoted, actor, f"archived={archived}", ts),
    )
    logger.info("joyjoy: published mount=%s nodes=%s", mount_id, promoted)
    return {"mount_id": mount_id, "published_nodes": promoted, "archived_nodes": archived}


def list_mounts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.*,
          (SELECT COUNT(*) FROM wiki_toc_node n WHERE n.mount_id = m.mount_id AND n.status = 'draft') AS draft_count,
          (SELECT COUNT(*) FROM wiki_toc_node n WHERE n.mount_id = m.mount_id AND n.status = 'published' AND n.kind = 'leaf') AS published_leaves
        FROM wiki_document_mount m
        ORDER BY m.sort_key, m.display_title
        """
    ).fetchall()
    return [dict(r) for r in rows]
