from __future__ import annotations

import sqlite3

CATALOG_HIERARCHICAL = "hierarchical"
CATALOG_FLAT_FAQ = "flat_faq"

_KNOWN = frozenset({CATALOG_HIERARCHICAL, CATALOG_FLAT_FAQ})


def infer_catalog_mode(document_id: str) -> str:
    doc = (document_id or "").strip().lower()
    if doc == "faq" or doc.endswith("_faq") or doc.endswith("-faq"):
        return CATALOG_FLAT_FAQ
    return CATALOG_HIERARCHICAL


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def migrate_kg_document_catalog_mode(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "kg_document", "catalog_mode"):
        conn.execute(
            f"""
            ALTER TABLE kg_document
            ADD COLUMN catalog_mode TEXT NOT NULL DEFAULT '{CATALOG_HIERARCHICAL}'
            """
        )
    conn.execute(
        """
        UPDATE kg_document SET catalog_mode = ?
        WHERE (catalog_mode IS NULL OR catalog_mode = '' OR catalog_mode = ?)
          AND lower(document_id) IN ('faq')
        """,
        (CATALOG_FLAT_FAQ, CATALOG_HIERARCHICAL),
    )
    conn.execute(
        """
        UPDATE kg_document SET catalog_mode = ?
        WHERE catalog_mode IS NULL OR catalog_mode = ''
        """,
        (CATALOG_HIERARCHICAL,),
    )


def get_catalog_mode(conn: sqlite3.Connection, document_id: str) -> str:
    doc = (document_id or "").strip()
    if not doc:
        return CATALOG_HIERARCHICAL
    kb = conn.execute(
        "SELECT 1 FROM kb_library WHERE document_id = ? LIMIT 1",
        (doc,),
    ).fetchone()
    if kb:
        return CATALOG_FLAT_FAQ
    if not _column_exists(conn, "kg_document", "catalog_mode"):
        return infer_catalog_mode(doc)
    row = conn.execute(
        "SELECT catalog_mode FROM kg_document WHERE document_id = ? LIMIT 1",
        (doc,),
    ).fetchone()
    if row and row[0]:
        mode = str(row[0]).strip()
        if mode in _KNOWN:
            return mode
    return infer_catalog_mode(doc)