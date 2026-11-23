from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from amendaq.db.connection import connect, get_db_path
from amendaq.graph.text2sql import create_sql_generator, validate_readonly_sql
from amendaq.knowledge.search import score_entity
from amendaq.wiki.toc_query import (
    collect_descendant_ids,
    fetch_direct_children,
    fetch_nodes,
    outline_for_plan,
    row_to_node,
    slim_toc_choice,
)
from amendaq.wiki.toc_persist import publish_mount, list_mounts, ensure_mount


def _row_policy(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "policy_id": row["policy_id"],
        "section": row["section"],
        "title": row["title"],
        "summary": row["summary"],
        "body": row["body"],
        "tags": [],
        "evidence": {
            "quote": row["evidence_quote"],
            "source_uri": row["source_uri"],
            "effective_from": row["effective_from"],
            "section_ref": row["section"],
        },
    }


class KnowledgeService:
    """Single knowledge + domain state API (SQLite)."""

    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        self._conn = conn or connect()
        self._own_conn = conn is None

    def close(self) -> None:
        if self._own_conn:
            self._conn.close()

    # --- Wiki: resolve by catalog tags, not raw question tokens ---
    def find_wiki_policies(
        self,
        *,
        topics: list[str],
        match: str = "any",
        limit: int = 5,
    ) -> dict[str, Any]:
        topics = [t.strip().lower() for t in topics if t.strip()]
        if not topics:
            return {"topics": [], "hits": [], "count": 0}

        placeholders = ",".join("?" for _ in topics)
        if match == "all":
            sql = f"""
                SELECT p.*, COUNT(DISTINCT t.tag) AS tag_hits
                FROM wiki_policy p
                JOIN wiki_policy_tag t ON p.policy_id = t.policy_id
                WHERE t.tag IN ({placeholders})
                GROUP BY p.policy_id
                HAVING tag_hits >= ?
                ORDER BY tag_hits DESC, p.section
                LIMIT ?
            """
            params = [*topics, len(topics), limit]
        else:
            sql = f"""
                SELECT p.*, COUNT(DISTINCT t.tag) AS tag_hits
                FROM wiki_policy p
                JOIN wiki_policy_tag t ON p.policy_id = t.policy_id
                WHERE t.tag IN ({placeholders})
                GROUP BY p.policy_id
                ORDER BY tag_hits DESC, p.section
                LIMIT ?
            """
            params = [*topics, limit]

        rows = self._conn.execute(sql, params).fetchall()
        hits = [_row_policy(r) for r in rows]
        for h, r in zip(hits, rows):
            h["tag_hits"] = r["tag_hits"]
        return {"topics": topics, "match": match, "hits": hits, "count": len(hits)}

    def get_wiki_policy(self, policy_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM wiki_policy WHERE policy_id = ?", (policy_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown wiki policy_id: {policy_id}")
        policy = _row_policy(row)
        tags = self._conn.execute(
            "SELECT tag FROM wiki_policy_tag WHERE policy_id = ?", (policy_id,)
        ).fetchall()
        policy["tags"] = [r["tag"] for r in tags]
        return policy

    def get_wiki_evidence(self, policy_id: str) -> dict[str, Any]:
        policy = self.get_wiki_policy(policy_id)
        ev = dict(policy["evidence"])
        ev["policy_id"] = policy_id
        ev["title"] = policy["title"]
        return ev

    # --- Gov domain (demo) ---
    def get_case(self, case_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM gov_case WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown case_id: {case_id}")
        return dict(row)

    def get_case_status(self, case_id: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        return {
            "case_id": case["case_id"],
            "status": case["status"],
            "status_label": case["status_label"],
            "submitted_at": case["submitted_at"],
        }

    def get_procedure(self, procedure_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM gov_procedure WHERE procedure_id = ?", (procedure_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown procedure_id: {procedure_id}")
        d = dict(row)
        d["online_available"] = bool(d["online_available"])
        return d

    # --- Knowledge graph (MCP-style + optional q2sql) ---
    def kg_find_entities(
        self,
        *,
        topics: list[str] | None = None,
        entity_type: str | None = None,
        name_contains: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        topics = [t.strip().lower() for t in (topics or []) if t.strip()]
        clauses: list[str] = []
        params: list[Any] = []
        if entity_type:
            clauses.append("e.entity_type = ?")
            params.append(entity_type)
        if document_id:
            clauses.append("e.document_id = ?")
            params.append(document_id)
        if name_contains:
            clauses.append("LOWER(e.name) LIKE ?")
            params.append(f"%{name_contains.lower()}%")
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        if topics:
            ph = ",".join("?" for _ in topics)
            sql = f"""
                SELECT e.*, COUNT(DISTINCT t.tag) AS tag_hits
                FROM kg_entity e
                JOIN kg_entity_tag t ON e.entity_id = t.entity_id
                WHERE t.tag IN ({ph}) {where}
                GROUP BY e.entity_id
                ORDER BY tag_hits DESC, e.name
                LIMIT ?
            """
            rows = self._conn.execute(sql, [*topics, *params, limit]).fetchall()
        else:
            sql = f"""
                SELECT e.*, 0 AS tag_hits FROM kg_entity e
                WHERE 1=1 {where}
                ORDER BY e.name LIMIT ?
            """
            rows = self._conn.execute(sql, [*params, limit]).fetchall()
        hits = [self._row_entity(r) for r in rows]
        for h, r in zip(hits, rows):
            h["tag_hits"] = r["tag_hits"]
        return {"topics": topics, "hits": hits, "count": len(hits)}

    def kg_search_entities(
        self,
        *,
        query: str,
        document_id: str | None = None,
        entity_type: str = "Policy",
        limit: int = 5,
        entity_id_in: list[str] | None = None,
        section_prefix: str | None = None,
        section_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        clauses = ["e.entity_type = ?"]
        params: list[Any] = [entity_type]
        if document_id:
            clauses.append("e.document_id = ?")
            params.append(document_id)
        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"SELECT * FROM kg_entity e WHERE {where}",
            params,
        ).fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            ent = self._row_entity(row)
            body = ent.get("body") or ent.get("summary") or ""
            s = score_entity(query, ent["name"], ent.get("summary") or "", body)
            if s <= 0:
                blob = (ent["name"] + " " + (ent.get("summary") or "") + " " + body[:400]).lower()
                from amendaq.knowledge.search import tokenize as tokfn

                for tok in tokfn(query):
                    if tok in blob:
                        s = 2.0
                        break
            if s <= 0:
                continue
            if entity_id_in and ent["entity_id"] not in entity_id_in:
                continue
            sec = str(ent.get("section") or "")
            if section_refs and sec:
                from amendaq.planning.sibling_expand import section_in_scopes

                if not section_in_scopes(sec, section_refs):
                    continue
            elif section_prefix and sec:
                pref = section_prefix.rstrip(".")
                if not (sec == pref or sec.startswith(f"{pref}.")):
                    continue
            ent["search_score"] = s
            scored.append((s, ent))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = [e for _, e in scored[:limit]]
        return {"query": query, "document_id": document_id, "hits": hits, "count": len(hits)}

    # --- Wiki TOC ---
    def wiki_mount_volume_node_id(self, document_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT parent_node_id FROM wiki_document_mount
            WHERE document_id = ? ORDER BY updated_at DESC LIMIT 1
            """,
            (document_id,),
        ).fetchone()
        return str(row["parent_node_id"]) if row else None

    def wiki_list_toc_children(
        self,
        *,
        parent_node_id: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        nodes = fetch_direct_children(
            self._conn,
            parent_node_id=parent_node_id,
            document_id=document_id,
        )
        return {
            "parent_node_id": parent_node_id,
            "document_id": document_id,
            "nodes": slim_toc_choice(nodes),
            "count": len(nodes),
        }

    def wiki_list_chapters(self, *, document_id: str) -> dict[str, Any]:
        nodes = fetch_nodes(
            self._conn,
            document_id=document_id,
            kinds=("chapter",),
        )
        chapters = slim_toc_choice(nodes)
        return {"document_id": document_id, "chapters": chapters, "count": len(chapters)}

    def faq_list_published_leaves(self, *, document_id: str) -> dict[str, Any]:
        from amendaq.kb.faq_read import faq_leaf_rows

        leaves = faq_leaf_rows(self._conn, document_id=document_id, statuses=("published",))
        slim = [
            {
                "section_ref": lf["section_ref"],
                "title": lf["title"],
                "summary": lf["summary"],
                "node_id": lf["node_id"],
            }
            for lf in leaves
        ]
        return {"document_id": document_id, "leaves": slim, "count": len(slim)}

    def wiki_list_leaves(self, *, document_id: str) -> dict[str, Any]:
        """Deprecated alias: flat FAQ reads kb_faq_item."""
        return self.faq_list_published_leaves(document_id=document_id)

    def document_catalog_mode(self, *, document_id: str) -> str:
        from amendaq.db.catalog_mode import CATALOG_FLAT_FAQ

        return CATALOG_FLAT_FAQ

    def wiki_outline_for_chapters(
        self,
        *,
        document_id: str,
        chapter_section_refs: list[str],
        max_nodes: int = 80,
    ) -> dict[str, Any]:
        from amendaq.planning.toc_batch_select import section_under_chapters

        nodes = fetch_nodes(
            self._conn,
            document_id=document_id,
            kinds=("chapter", "leaf"),
        )
        refs = [r for r in chapter_section_refs if r]
        if not refs:
            slim = outline_for_plan(nodes, max_nodes=max_nodes)
        else:
            filtered = [
                n
                for n in nodes
                if (
                    n.get("kind") == "chapter"
                    and str(n.get("section_ref") or "") in refs
                )
                or (
                    n.get("kind") == "leaf"
                    and section_under_chapters(str(n.get("section_ref") or ""), refs)
                )
            ]
            slim = outline_for_plan(filtered, max_nodes=max_nodes)
        return {
            "document_id": document_id,
            "chapter_refs": refs,
            "nodes": slim,
            "count": len(slim),
        }

    def wiki_get_toc_outline(
        self,
        *,
        document_id: str | None = None,
        mount_id: str | None = None,
        max_nodes: int = 200,
    ) -> dict[str, Any]:
        nodes = fetch_nodes(
            self._conn,
            mount_id=mount_id,
            document_id=document_id,
            kinds=("chapter", "leaf"),
        )
        return {
            "document_id": document_id,
            "mount_id": mount_id,
            "nodes": outline_for_plan(nodes, max_nodes=max_nodes),
            "count": len(nodes),
        }

    def wiki_get_subtree(self, node_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM wiki_toc_node WHERE node_id = ?", (node_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown toc node_id: {node_id}")
        root = row_to_node(row)
        ids = collect_descendant_ids(self._conn, node_id, leaf_only=True)
        leaves = []
        if ids:
            ph = ",".join("?" for _ in ids)
            rows = self._conn.execute(
                f"SELECT * FROM wiki_toc_node WHERE node_id IN ({ph}) ORDER BY sort_key",
                ids,
            ).fetchall()
            leaves = [row_to_node(r) for r in rows]
        return {"root": root, "leaf_ids": ids, "leaves": leaves, "count": len(leaves)}

    def wiki_get_leaves(
        self,
        node_ids: list[str],
    ) -> dict[str, Any]:
        if not node_ids:
            return {"leaves": [], "count": 0}
        ph = ",".join("?" for _ in node_ids)
        rows = self._conn.execute(
            f"""
            SELECT * FROM wiki_toc_node
            WHERE node_id IN ({ph}) AND kind = 'leaf' AND disabled = 0
            ORDER BY section_ref
            """,
            node_ids,
        ).fetchall()
        leaves = [row_to_node(r) for r in rows]
        return {"leaves": leaves, "count": len(leaves)}

    def wiki_resolve_branch(
        self,
        *,
        node_id: str | None = None,
        section_prefix: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        if node_id:
            return self.wiki_get_subtree(node_id)
        if section_prefix and document_id:
            from amendaq.wiki.toc_query import allowed_statuses

            statuses = allowed_statuses()
            ph = ",".join("?" for _ in statuses)
            row = self._conn.execute(
                f"""
                SELECT * FROM wiki_toc_node
                WHERE document_id = ? AND status IN ({ph})
                  AND kind = 'chapter' AND section_ref LIKE ?
                ORDER BY length(section_ref) DESC LIMIT 1
                """,
                (document_id, *statuses, f"{section_prefix.rstrip('.')}%"),
            ).fetchone()
            if row:
                return self.wiki_get_subtree(row["node_id"])
        raise KeyError("wiki branch not found")

    def document_display_title(self, *, document_id: str) -> str:
        """Human-readable handbook name for UI (mount/kg title, upload file, or 员工手册)."""
        from amendaq.document_display import infer_handbook_display_title, is_technical_document_label
        from amendaq.paths import uploads_dir

        doc = (document_id or "").strip()
        if not doc:
            return ""
        stored = ""
        kb = self._conn.execute(
            "SELECT title FROM kb_library WHERE document_id = ? LIMIT 1",
            (doc,),
        ).fetchone()
        if kb and kb["title"]:
            stored = str(kb["title"]).strip()
        if not stored:
            for m in list_mounts(self._conn):
                if str(m.get("document_id") or "") == doc:
                    stored = str(m.get("display_title") or "").strip()
                    break
        if not stored:
            row = self._conn.execute(
                "SELECT title FROM kg_document WHERE document_id = ? LIMIT 1",
                (doc,),
            ).fetchone()
            if row and row["title"]:
                stored = str(row["title"]).strip()
        uploads = sorted(uploads_dir().glob(f"{doc}*"))
        path = uploads[-1] if uploads else None
        title = infer_handbook_display_title(
            document_id=doc,
            path=path,
            stored_title=stored or None,
        )
        if title and not is_technical_document_label(doc, title):
            return title
        return title or doc

    def wiki_list_mounts(self) -> dict[str, Any]:
        return {"mounts": list_mounts(self._conn), "count": len(list_mounts(self._conn))}

    def wiki_publish_mount(self, mount_id: str, *, actor: str = "ui") -> dict[str, Any]:
        result = publish_mount(self._conn, mount_id, actor=actor)
        self._conn.commit()
        return result

    def wiki_update_node(
        self,
        node_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
        body: str | None = None,
        parent_id: str | None = None,
        disabled: bool | None = None,
    ) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM wiki_toc_node WHERE node_id = ?", (node_id,)
        ).fetchone()
        if not row:
            raise KeyError(node_id)
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        new_title = title if title is not None else row["title"]
        new_body = body if body is not None else row["body"]
        if row["kind"] == "leaf" and body is not None:
            text = (new_body or "").strip()
            new_summary = text[:280] + ("…" if len(text) > 280 else "")
        else:
            new_summary = summary if summary is not None else row["summary"]
        new_parent = parent_id if parent_id is not None else row["parent_id"]
        new_dis = int(disabled) if disabled is not None else row["disabled"]
        self._conn.execute(
            """
            UPDATE wiki_toc_node SET title = ?, summary = ?, body = ?, parent_id = ?,
              disabled = ?, updated_at = ?
            WHERE node_id = ?
            """,
            (new_title, new_summary, new_body, new_parent, new_dis, ts, node_id),
        )
        self._conn.commit()
        return {"node_id": node_id, "updated": True}

    def kg_get_entity_by_section(
        self, section: str, *, document_id: str | None = None
    ) -> dict[str, Any]:
        clauses = ["json_extract(e.properties_json, '$.section') = ?"]
        params: list[Any] = [section]
        if document_id:
            clauses.append("e.document_id = ?")
            params.append(document_id)
        row = self._conn.execute(
            f"SELECT * FROM kg_entity e WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        if row:
            return self.kg_get_entity(row["entity_id"])
        from amendaq.kb.faq_read import faq_entity_from_section

        fallback = faq_entity_from_section(
            self._conn, section, document_id=document_id
        )
        if fallback:
            return fallback
        raise KeyError(f"no entity section={section} document_id={document_id}")

    def kg_get_entity(self, entity_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM kg_entity WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"unknown entity_id: {entity_id}")
        ent = self._row_entity(row)
        tags = self._conn.execute(
            "SELECT tag FROM kg_entity_tag WHERE entity_id = ?", (entity_id,)
        ).fetchall()
        ent["tags"] = [r["tag"] for r in tags]
        return ent

    def kg_neighbors(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        direction: str = "out",
    ) -> dict[str, Any]:
        if direction == "in":
            sql = """
                SELECT r.*, e.name AS peer_name, e.entity_type AS peer_type
                FROM kg_relation r
                JOIN kg_entity e ON r.from_entity_id = e.entity_id
                WHERE r.to_entity_id = ?
            """
        else:
            sql = """
                SELECT r.*, e.name AS peer_name, e.entity_type AS peer_type
                FROM kg_relation r
                JOIN kg_entity e ON r.to_entity_id = e.entity_id
                WHERE r.from_entity_id = ?
            """
        params: list[Any] = [entity_id]
        if predicate:
            sql += " AND r.predicate = ?"
            params.append(predicate)
        rows = self._conn.execute(sql, params).fetchall()
        edges = [dict(r) for r in rows]
        return {"entity_id": entity_id, "direction": direction, "edges": edges, "count": len(edges)}

    def kg_get_evidence(self, entity_id: str) -> dict[str, Any]:
        rows = self._conn.execute(
            "SELECT * FROM kg_evidence WHERE entity_id = ? ORDER BY evidence_id",
            (entity_id,),
        ).fetchall()
        if not rows:
            ent = self.kg_get_entity(entity_id)
            props = ent.get("properties") or {}
            quote = props.get("body") or ent.get("summary") or ""
            return {
                "entity_id": entity_id,
                "title": ent.get("name"),
                "quote": quote[:400],
                "section_ref": props.get("section", ""),
            }
        row = rows[0]
        ent = self.kg_get_entity(entity_id)
        return {
            "entity_id": entity_id,
            "title": ent.get("name"),
            "quote": row["quote"],
            "section_ref": row["section_ref"],
            "source_uri": row["source_uri"],
        }

    def kg_run_readonly_sql(self, sql: str) -> dict[str, Any]:
        validate_readonly_sql(sql)
        if "LIMIT" not in sql.upper():
            sql = f"{sql.rstrip()} LIMIT 20"
        cur = self._conn.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return {"sql": sql, "columns": cols, "rows": rows, "count": len(rows)}

    def kg_nl_query(
        self, question: str, *, document_id: str | None = None
    ) -> dict[str, Any]:
        gen = create_sql_generator()
        sql = gen.nl_to_sql(question, document_id=document_id)
        result = self.kg_run_readonly_sql(sql)
        result["nl_query"] = question
        return result

    def _row_entity(self, row: sqlite3.Row) -> dict[str, Any]:
        props = json.loads(row["properties_json"] or "{}")
        return {
            "entity_id": row["entity_id"],
            "document_id": row["document_id"],
            "entity_type": row["entity_type"],
            "name": row["name"],
            "summary": row["summary"],
            "properties": props,
            "section": props.get("section"),
            "body": props.get("body"),
            "policy_id": props.get("policy_id") or row["entity_id"],
        }

    def get_gov_policy_for_stage(self, procedure_id: str, review_stage: str) -> dict[str, Any]:
        row = self._conn.execute(
            """
            SELECT * FROM gov_policy
            WHERE procedure_id = ? AND review_stage = ?
            """,
            (procedure_id, review_stage),
        ).fetchone()
        if not row:
            raise KeyError(
                f"no gov policy procedure_id={procedure_id} stage={review_stage}"
            )
        return {
            "policy_id": row["policy_id"],
            "procedure_id": row["procedure_id"],
            "review_stage": row["review_stage"],
            "title": row["title"],
            "max_working_days": row["max_working_days"],
            "summary": row["summary"],
            "evidence": {
                "quote": row["evidence_quote"],
                "source_uri": row["source_uri"],
                "effective_from": row["effective_from"],
            },
        }


def ensure_database() -> Path:
    from amendaq.db.bootstrap import bootstrap_database, ensure_schema
    from amendaq.db.reset import should_skip_demo_seed

    path = get_db_path()
    ensure_schema(path)
    if not path.is_file() or path.stat().st_size == 0:
        if should_skip_demo_seed():
            ensure_schema(path)
            return path
        bootstrap_database(path)
        return path
    if should_skip_demo_seed():
        return path
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM kg_entity WHERE document_id = 'employee_handbook'"
        ).fetchone()
        if row and row["n"] == 0:
            from amendaq.db.bootstrap import _load_handbook_graph

            _load_handbook_graph(conn)
            conn.commit()
    finally:
        conn.close()
    return path
