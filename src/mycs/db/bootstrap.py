from __future__ import annotations

import json
from pathlib import Path

from mycs.db.connection import connect, get_db_path
from mycs.log import get_logger
from mycs.db.catalog_mode import migrate_kg_document_catalog_mode
from mycs.db.schema_kg import KG_DDL
from mycs.db.schema_kb import KB_DDL
from mycs.db.schema_wiki_toc import WIKI_TOC_DDL
from mycs.graph.extract import SectionGraphBuilder
from mycs.graph.persist import export_graph_json, persist_graph
from mycs.wiki.ingest import policies_from_text

logger = get_logger(__name__)

REF_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"
HANDBOOK_TXT = Path(__file__).resolve().parents[3] / "data" / "sources" / "employee_handbook.txt"


def ensure_schema(db_path: Path | None = None) -> Path:
    """Apply DDL without reloading seed data."""
    path = db_path or get_db_path()
    conn = connect(path)
    try:
        _create_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def bootstrap_database(db_path: Path | None = None) -> Path:
    path = db_path or get_db_path()
    conn = connect(path)
    try:
        _create_schema(conn)
        _load_handbook(conn)
        _load_handbook_graph(conn)
        _load_gov_reference(conn)
        conn.commit()
    finally:
        conn.close()
    logger.info("database ready at %s", path)
    return path


def _migrate_kb_section_ref(conn) -> None:
    rows = conn.execute("PRAGMA table_info(kb_faq_item)").fetchall()
    if not rows:
        return
    if not any(str(r[1]) == "section_ref" for r in rows):
        conn.execute(
            "ALTER TABLE kb_faq_item ADD COLUMN section_ref TEXT NOT NULL DEFAULT ''"
        )


def _create_schema(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS wiki_policy (
            policy_id TEXT PRIMARY KEY,
            section TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            body TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            source_uri TEXT NOT NULL,
            evidence_quote TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wiki_policy_tag (
            policy_id TEXT NOT NULL REFERENCES wiki_policy(policy_id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            PRIMARY KEY (policy_id, tag)
        );

        CREATE INDEX IF NOT EXISTS idx_wiki_tag ON wiki_policy_tag(tag);

        CREATE TABLE IF NOT EXISTS gov_case (
            case_id TEXT PRIMARY KEY,
            procedure_id TEXT NOT NULL,
            subject_label TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            status TEXT NOT NULL,
            status_label TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gov_procedure (
            procedure_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            online_available INTEGER NOT NULL,
            summary TEXT NOT NULL
        );

        """
    )
    conn.executescript(KG_DDL)
    migrate_kg_document_catalog_mode(conn)
    conn.executescript(WIKI_TOC_DDL)
    conn.executescript(KB_DDL)
    _migrate_kb_section_ref(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS gov_policy (
            policy_id TEXT PRIMARY KEY,
            procedure_id TEXT NOT NULL,
            review_stage TEXT NOT NULL,
            title TEXT NOT NULL,
            max_working_days INTEGER,
            summary TEXT NOT NULL,
            evidence_quote TEXT NOT NULL,
            source_uri TEXT NOT NULL,
            effective_from TEXT NOT NULL
        );
        """
    )


def _load_handbook(conn) -> None:
    if not HANDBOOK_TXT.is_file():
        raise FileNotFoundError(f"missing handbook source: {HANDBOOK_TXT}")
    policies = policies_from_text(HANDBOOK_TXT.read_text(encoding="utf-8"))
    conn.execute("DELETE FROM wiki_policy_tag")
    conn.execute("DELETE FROM wiki_policy")
    for p in policies.values():
        ev = p["evidence"]
        conn.execute(
            """
            INSERT INTO wiki_policy (
                policy_id, section, title, summary, body,
                effective_from, source_uri, evidence_quote
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["policy_id"],
                p["section"],
                p["title"],
                p["summary"],
                p["body"],
                ev["effective_from"],
                ev["source_uri"],
                ev["quote"],
            ),
        )
        for tag in p.get("tags") or []:
            conn.execute(
                "INSERT INTO wiki_policy_tag (policy_id, tag) VALUES (?, ?)",
                (p["policy_id"], tag),
            )


def _load_handbook_graph(conn) -> None:
    if not HANDBOOK_TXT.is_file():
        return
    text = HANDBOOK_TXT.read_text(encoding="utf-8")
    extractor = SectionGraphBuilder()
    graph = extractor.extract(
        text,
        document_id="employee_handbook",
        title="employee_handbook.txt",
        source_uri=f"file://{HANDBOOK_TXT.resolve()}",
    )
    persist_graph(graph, conn=conn)
    kg_dir = Path(__file__).resolve().parents[3] / "data" / "kg"
    export_graph_json(graph, kg_dir / "employee_handbook.json")
    logger.info("handbook knowledge graph loaded entities=%s", len(graph.entities))


def _load_gov_reference(conn) -> None:
    conn.execute("DELETE FROM gov_case")
    conn.execute("DELETE FROM gov_procedure")
    conn.execute("DELETE FROM gov_policy")
    for row in json.loads((REF_DIR / "cases.json").read_text(encoding="utf-8")).values():
        conn.execute(
            """
            INSERT INTO gov_case (case_id, procedure_id, subject_label, submitted_at, status, status_label)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["case_id"],
                row["procedure_id"],
                row["subject_label"],
                row["submitted_at"],
                row["status"],
                row["status_label"],
            ),
        )
    for row in json.loads((REF_DIR / "procedures.json").read_text(encoding="utf-8")).values():
        conn.execute(
            """
            INSERT INTO gov_procedure (procedure_id, title, online_available, summary)
            VALUES (?, ?, ?, ?)
            """,
            (
                row["procedure_id"],
                row["title"],
                1 if row.get("online_available") else 0,
                row.get("summary", ""),
            ),
        )
    for row in json.loads((REF_DIR / "policies.json").read_text(encoding="utf-8")).values():
        ev = row.get("evidence") or {}
        conn.execute(
            """
            INSERT INTO gov_policy (
                policy_id, procedure_id, review_stage, title, max_working_days,
                summary, evidence_quote, source_uri, effective_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["policy_id"],
                row["procedure_id"],
                row["review_stage"],
                row["title"],
                row.get("max_working_days"),
                row.get("summary", ""),
                ev.get("quote", ""),
                ev.get("source_uri", ""),
                ev.get("effective_from", ""),
            ),
        )
