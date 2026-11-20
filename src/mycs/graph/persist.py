from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mycs.db.catalog_mode import infer_catalog_mode
from mycs.db.connection import connect, get_db_path
from mycs.graph.model import KnowledgeGraph
from mycs.log import get_logger

logger = get_logger(__name__)


def persist_graph(
    graph: KnowledgeGraph,
    db_path: Path | None = None,
    *,
    conn: sqlite3.Connection | None = None,
    catalog_mode: str | None = None,
) -> None:
    own_conn = conn is None
    if own_conn:
        conn = connect(db_path or get_db_path())
    assert conn is not None
    try:
        conn.execute("DELETE FROM kg_evidence WHERE document_id = ?", (graph.document_id,))
        conn.execute("DELETE FROM kg_relation WHERE document_id = ?", (graph.document_id,))
        conn.execute(
            "DELETE FROM kg_entity_tag WHERE entity_id IN "
            "(SELECT entity_id FROM kg_entity WHERE document_id = ?)",
            (graph.document_id,),
        )
        conn.execute("DELETE FROM kg_entity WHERE document_id = ?", (graph.document_id,))
        conn.execute("DELETE FROM kg_document WHERE document_id = ?", (graph.document_id,))

        mode = catalog_mode or infer_catalog_mode(graph.document_id)
        conn.execute(
            """
            INSERT INTO kg_document (document_id, title, source_uri, ingested_at, catalog_mode)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                graph.document_id,
                graph.title,
                graph.source_uri,
                datetime.now(timezone.utc).isoformat(),
                mode,
            ),
        )
        seen: set[str] = set()
        for ent in graph.entities:
            if ent.entity_id in seen:
                continue
            seen.add(ent.entity_id)
            conn.execute(
                """
                INSERT INTO kg_entity (
                    entity_id, document_id, entity_type, name, summary, properties_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ent.entity_id,
                    graph.document_id,
                    ent.entity_type,
                    ent.name,
                    ent.summary,
                    json.dumps(ent.properties, ensure_ascii=False),
                ),
            )
            for tag in ent.tags:
                conn.execute(
                    "INSERT INTO kg_entity_tag (entity_id, tag) VALUES (?, ?)",
                    (ent.entity_id, tag.lower()),
                )
        for rel in graph.relations:
            conn.execute(
                """
                INSERT INTO kg_relation (
                    relation_id, document_id, from_entity_id, to_entity_id,
                    predicate, properties_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rel.relation_id,
                    graph.document_id,
                    rel.from_entity_id,
                    rel.to_entity_id,
                    rel.predicate,
                    json.dumps(rel.properties, ensure_ascii=False),
                ),
            )
        for ev in graph.evidence:
            conn.execute(
                """
                INSERT INTO kg_evidence (
                    evidence_id, document_id, entity_id, relation_id,
                    quote, section_ref, source_uri
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev.evidence_id,
                    graph.document_id,
                    ev.entity_id,
                    ev.relation_id,
                    ev.quote,
                    ev.section_ref,
                    graph.source_uri,
                ),
            )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def export_graph_json(graph: KnowledgeGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
