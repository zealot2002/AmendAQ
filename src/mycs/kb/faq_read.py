from __future__ import annotations

import sqlite3
from typing import Any


def faq_leaf_rows(
    conn: sqlite3.Connection,
    *,
    document_id: str,
    statuses: tuple[str, ...] = ("published",),
) -> list[dict[str, Any]]:
    ph = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"""
        SELECT item_id, question, answer, section_ref, sort_key, status
        FROM kb_faq_item
        WHERE document_id = ? AND disabled = 0 AND status IN ({ph})
        ORDER BY sort_key, created_at
        """,
        (document_id, *statuses),
    ).fetchall()
    leaves: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        body = (row["answer"] or "").strip()
        title = (row["question"] or "").strip()
        if not title or not body:
            continue
        sec = (row["section_ref"] or "").strip() or f"1.{idx}"
        leaves.append(
            {
                "node_id": row["item_id"],
                "item_id": row["item_id"],
                "section_ref": sec,
                "title": title,
                "summary": body[:280] + ("…" if len(body) > 280 else ""),
                "body": body,
                "kind": "leaf",
                "status": row["status"],
            }
        )
    return leaves


def faq_entity_from_section(
    conn: sqlite3.Connection,
    section: str,
    *,
    document_id: str | None,
) -> dict[str, Any] | None:
    clauses = ["section_ref = ?", "disabled = 0", "status = 'published'"]
    params: list[Any] = [section]
    if document_id:
        clauses.append("document_id = ?")
        params.append(document_id)
    row = conn.execute(
        f"SELECT * FROM kb_faq_item WHERE {' AND '.join(clauses)} LIMIT 1",
        params,
    ).fetchone()
    if not row:
        return None
    body = (row["answer"] or "").strip()
    title = (row["question"] or "").strip()
    doc = str(row["document_id"] or document_id or "")
    sec = str(row["section_ref"] or section)
    eid = f"{doc}_{sec.replace('.', '_')}"
    quote = body[:600] if body else ""
    return {
        "entity_id": eid,
        "document_id": doc,
        "entity_type": "Policy",
        "name": title,
        "summary": body[:280] + ("…" if len(body) > 280 else ""),
        "properties": {"section": sec, "body": body, "policy_id": eid, "item_id": row["item_id"]},
        "tags": [],
        "evidence": {
            "quote": quote,
            "source_uri": f"kb://{doc}",
            "section_ref": sec,
        },
    }