from __future__ import annotations

import os
import sqlite3
from typing import Any


def allowed_statuses() -> tuple[str, ...]:
    if os.environ.get("AMENDAQ_WIKI_ALLOW_DRAFT", "").strip() in ("1", "true", "yes"):
        return ("published", "draft")
    return ("published",)


def row_to_node(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "node_id": row["node_id"],
        "parent_id": row["parent_id"],
        "mount_id": row["mount_id"],
        "document_id": row["document_id"],
        "kind": row["kind"],
        "section_ref": row["section_ref"],
        "title": row["title"],
        "summary": row["summary"],
        "body": row["body"] if row["kind"] == "leaf" else "",
        "sort_key": row["sort_key"],
        "depth": row["depth"],
        "entity_id": row["entity_id"],
        "status": row["status"],
        "disabled": bool(row["disabled"]),
    }


def fetch_nodes(
    conn: sqlite3.Connection,
    *,
    mount_id: str | None = None,
    document_id: str | None = None,
    kinds: tuple[str, ...] | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    if statuses is None:
        statuses = allowed_statuses()
    ph_s = ",".join("?" for _ in statuses)
    clauses = [f"status IN ({ph_s})", "disabled = 0"]
    params: list[Any] = list(statuses)
    if mount_id:
        clauses.append("mount_id = ?")
        params.append(mount_id)
    if document_id:
        clauses.append("document_id = ?")
        params.append(document_id)
    if kinds:
        ph_k = ",".join("?" for _ in kinds)
        clauses.append(f"kind IN ({ph_k})")
        params.extend(kinds)
    sql = f"""
        SELECT * FROM wiki_toc_node
        WHERE {' AND '.join(clauses)}
        ORDER BY depth, sort_key, section_ref
    """
    return [row_to_node(r) for r in conn.execute(sql, params).fetchall()]


def collect_descendant_ids(
    conn: sqlite3.Connection,
    root_node_id: str,
    *,
    leaf_only: bool = False,
) -> list[str]:
    statuses = allowed_statuses()
    ph_s = ",".join("?" for _ in statuses)
    all_nodes = conn.execute(
        f"""
        SELECT node_id, parent_id, kind FROM wiki_toc_node
        WHERE status IN ({ph_s}) AND disabled = 0
        """,
        list(statuses),
    ).fetchall()
    by_parent: dict[str | None, list[str]] = {}
    kind_map: dict[str, str] = {}
    for r in all_nodes:
        by_parent.setdefault(r["parent_id"], []).append(r["node_id"])
        kind_map[r["node_id"]] = r["kind"]
    out: list[str] = []

    def walk(nid: str) -> None:
        if leaf_only and kind_map.get(nid) == "leaf":
            out.append(nid)
        elif not leaf_only:
            out.append(nid)
        for child in by_parent.get(nid, []):
            walk(child)

    walk(root_node_id)
    return out


def fetch_direct_children(
    conn: sqlite3.Connection,
    *,
    parent_node_id: str,
    document_id: str | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    if statuses is None:
        statuses = allowed_statuses()
    ph_s = ",".join("?" for _ in statuses)
    clauses = [
        f"status IN ({ph_s})",
        "disabled = 0",
        "parent_id = ?",
    ]
    params: list[Any] = [*statuses, parent_node_id]
    if document_id:
        clauses.append("document_id = ?")
        params.append(document_id)
    sql = f"""
        SELECT * FROM wiki_toc_node
        WHERE {' AND '.join(clauses)}
        ORDER BY sort_key, section_ref
    """
    return [row_to_node(r) for r in conn.execute(sql, params).fetchall()]


def slim_toc_choice(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in nodes:
        out.append(
            {
                "node_id": n["node_id"],
                "kind": n["kind"],
                "section_ref": n["section_ref"],
                "title": n["title"],
                "summary": (n.get("summary") or "")[:120],
            }
        )
    return out


def outline_for_plan(
    nodes: list[dict[str, Any]],
    *,
    max_nodes: int = 200,
) -> list[dict[str, Any]]:
    slim = []
    for n in nodes:
        if n["kind"] in ("root", "volume"):
            continue
        slim.append(
            {
                "node_id": n["node_id"],
                "kind": n["kind"],
                "section_ref": n["section_ref"],
                "title": n["title"],
                "summary": (n["summary"] or "")[:160],
                "depth": n["depth"],
            }
        )
        if len(slim) >= max_nodes:
            break
    return slim
