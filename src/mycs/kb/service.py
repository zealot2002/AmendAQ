from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from mycs.document_id import generate_document_id
from mycs.kb.dedup import normalize_faq_question
from mycs.kb.import_parse import ParsedFaqRow, parse_faq_import_text
from mycs.kb.sync_kg import sync_kb_to_kg
from mycs.log import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_title(title: str) -> str:
    t = (title or "").strip()[:40]
    if not t:
        return "kb"
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", t).strip("_").lower()
    return slug[:32] or "kb"


def _new_document_id(conn: sqlite3.Connection, title: str) -> str:
    base = _slug_title(title)
    if not re.match(r"^[a-z]", base):
        base = f"kb_{base}"
    candidate = base
    n = 1
    while conn.execute(
        "SELECT 1 FROM kb_library WHERE document_id = ?", (candidate,)
    ).fetchone():
        candidate = f"{base}_{n}"
        n += 1
    return candidate


def _item_counts(conn: sqlite3.Connection, document_id: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS n FROM kb_faq_item
        WHERE document_id = ? AND disabled = 0
        GROUP BY status
        """,
        (document_id,),
    ).fetchall()
    draft = published = 0
    for r in rows:
        if r["status"] == "draft":
            draft = int(r["n"])
        elif r["status"] == "published":
            published = int(r["n"])
    return {"draft_count": draft, "published_leaves": published, "item_count": draft + published}


class KbService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_libraries(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM kb_library ORDER BY updated_at DESC, title"
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            doc = row["document_id"]
            counts = _item_counts(self._conn, doc)
            out.append(
                {
                    "document_id": doc,
                    "mount_id": f"mount_{doc}",
                    "display_title": row["title"],
                    "description": row["description"],
                    "draft_count": counts["draft_count"],
                    "published_leaves": counts["published_leaves"],
                    "item_count": counts["item_count"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return out

    def get_library(self, document_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM kb_library WHERE document_id = ?", (document_id,)
        ).fetchone()
        if not row:
            raise KeyError(document_id)
        counts = _item_counts(self._conn, document_id)
        return {
            "document_id": row["document_id"],
            "title": row["title"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            **counts,
            "mount_id": f"mount_{document_id}",
        }

    def create_library(self, *, title: str, description: str = "") -> dict[str, Any]:
        title = (title or "").strip()
        if not title:
            raise ValueError("知识库名称不能为空")
        doc_id = _new_document_id(self._conn, title)
        ts = _now()
        self._conn.execute(
            """
            INSERT INTO kb_library (document_id, title, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (doc_id, title, (description or "").strip(), ts, ts),
        )
        sync_kb_to_kg(self._conn, document_id=doc_id, display_title=title)
        self._conn.commit()
        logger.info("joyjoy: kb library created document_id=%s", doc_id)
        return self.get_library(doc_id)

    def update_library(
        self,
        document_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM kb_library WHERE document_id = ?", (document_id,)
        ).fetchone()
        if not row:
            raise KeyError(document_id)
        new_title = (title if title is not None else row["title"]).strip()
        new_desc = description if description is not None else row["description"]
        ts = _now()
        self._conn.execute(
            "UPDATE kb_library SET title = ?, description = ?, updated_at = ? WHERE document_id = ?",
            (new_title, (new_desc or "").strip(), ts, document_id),
        )
        sync_kb_to_kg(self._conn, document_id=document_id, display_title=new_title)
        self._conn.commit()
        return self.get_library(document_id)

    def delete_library(self, document_id: str) -> None:
        self._conn.execute("DELETE FROM kb_faq_item WHERE document_id = ?", (document_id,))
        self._conn.execute("DELETE FROM kb_library WHERE document_id = ?", (document_id,))
        self._conn.execute(
            "DELETE FROM kg_evidence WHERE document_id = ?", (document_id,)
        )
        self._conn.execute("DELETE FROM kg_relation WHERE document_id = ?", (document_id,))
        self._conn.execute(
            "DELETE FROM kg_entity_tag WHERE entity_id IN "
            "(SELECT entity_id FROM kg_entity WHERE document_id = ?)",
            (document_id,),
        )
        self._conn.execute("DELETE FROM kg_entity WHERE document_id = ?", (document_id,))
        self._conn.execute("DELETE FROM kg_document WHERE document_id = ?", (document_id,))
        self._conn.commit()
        logger.info("joyjoy: kb library deleted document_id=%s", document_id)

    def list_items(self, document_id: str) -> list[dict[str, Any]]:
        if not self._conn.execute(
            "SELECT 1 FROM kb_library WHERE document_id = ?", (document_id,)
        ).fetchone():
            raise KeyError(document_id)
        rows = self._conn.execute(
            """
            SELECT * FROM kb_faq_item
            WHERE document_id = ? AND disabled = 0
            ORDER BY sort_key, created_at
            """,
            (document_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _existing_question_keys(self, document_id: str) -> set[str]:
        rows = self._conn.execute(
            """
            SELECT question, answer FROM kb_faq_item
            WHERE document_id = ? AND disabled = 0
            """,
            (document_id,),
        ).fetchall()
        return {normalize_faq_question(str(r["question"] or "")) for r in rows}

    def _find_item_by_question_key(
        self, document_id: str, question_key: str, *, exclude_item_id: str | None = None
    ) -> str | None:
        rows = self._conn.execute(
            """
            SELECT item_id, question FROM kb_faq_item
            WHERE document_id = ? AND disabled = 0
            """,
            (document_id,),
        ).fetchall()
        for r in rows:
            iid = str(r["item_id"])
            if exclude_item_id and iid == exclude_item_id:
                continue
            if normalize_faq_question(str(r["question"] or "")) == question_key:
                return iid
        return None

    def _next_sort_key(self, document_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sort_key), 0) AS m FROM kb_faq_item WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        return int(row["m"]) + 1

    def create_item(
        self,
        document_id: str,
        *,
        question: str,
        answer: str,
        status: str = "draft",
    ) -> dict[str, Any]:
        lib = self.get_library(document_id)
        q = (question or "").strip()
        a = (answer or "").strip()
        if not q or not a:
            raise ValueError("问题和答案均不能为空")
        qkey = normalize_faq_question(q)
        if self._find_item_by_question_key(document_id, qkey):
            raise ValueError(f"已存在相同问题，请勿重复添加：{q[:80]}")
        item_id = f"{document_id}_item_{uuid.uuid4().hex[:12]}"
        sort_key = self._next_sort_key(document_id)
        ts = _now()
        st = "published" if status == "published" else "draft"
        self._conn.execute(
            """
            INSERT INTO kb_faq_item (
                item_id, document_id, sort_key, question, answer, status, disabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (item_id, document_id, sort_key, q, a, st, ts, ts),
        )
        sync_kb_to_kg(
            self._conn, document_id=document_id, display_title=lib["title"]
        )
        self._conn.commit()
        return self._get_item(item_id)

    def _get_item(self, item_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM kb_faq_item WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            raise KeyError(item_id)
        return dict(row)

    def update_item(
        self,
        item_id: str,
        *,
        question: str | None = None,
        answer: str | None = None,
        status: str | None = None,
        sort_key: int | None = None,
    ) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM kb_faq_item WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            raise KeyError(item_id)
        doc_id = row["document_id"]
        lib = self.get_library(doc_id)
        q = (question if question is not None else row["question"]).strip()
        a = (answer if answer is not None else row["answer"]).strip()
        if not q or not a:
            raise ValueError("问题和答案均不能为空")
        qkey = normalize_faq_question(q)
        dup = self._find_item_by_question_key(
            doc_id, qkey, exclude_item_id=item_id
        )
        if dup:
            raise ValueError(f"已存在相同问题：{q[:80]}")
        st = row["status"]
        if status is not None:
            st = "published" if status == "published" else "draft"
        sk = int(sort_key if sort_key is not None else row["sort_key"])
        ts = _now()
        self._conn.execute(
            """
            UPDATE kb_faq_item
            SET question = ?, answer = ?, status = ?, sort_key = ?, updated_at = ?
            WHERE item_id = ?
            """,
            (q, a, st, sk, ts, item_id),
        )
        sync_kb_to_kg(
            self._conn, document_id=doc_id, display_title=lib["title"]
        )
        self._conn.commit()
        return self._get_item(item_id)

    def delete_item(self, item_id: str) -> None:
        row = self._conn.execute(
            "SELECT document_id FROM kb_faq_item WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            raise KeyError(item_id)
        doc_id = row["document_id"]
        lib = self.get_library(doc_id)
        self._conn.execute("DELETE FROM kb_faq_item WHERE item_id = ?", (item_id,))
        sync_kb_to_kg(
            self._conn, document_id=doc_id, display_title=lib["title"]
        )
        self._conn.commit()

    def import_items(
        self,
        document_id: str,
        text: str,
        *,
        as_draft: bool = True,
    ) -> dict[str, Any]:
        lib = self.get_library(document_id)
        parsed = parse_faq_import_text(text, default_title=lib["title"])
        if not parsed:
            raise ValueError(
                "未能解析任何问答。请使用规范 Markdown（### Q1. … + **答：**）或「问：」「答：」成对文本。"
            )
        return self._insert_parsed_rows(
            document_id, parsed, status="draft" if as_draft else "published"
        )

    def _insert_parsed_rows(
        self,
        document_id: str,
        rows: list[ParsedFaqRow],
        *,
        status: str,
    ) -> dict[str, Any]:
        lib = self.get_library(document_id)
        sort_base = self._next_sort_key(document_id)
        ts = _now()
        created = 0
        skipped = 0
        seen: set[str] = self._existing_question_keys(document_id)
        for row in rows:
            qkey = normalize_faq_question(row.question)
            if not qkey or qkey in seen:
                skipped += 1
                continue
            seen.add(qkey)
            item_id = f"{document_id}_item_{uuid.uuid4().hex[:12]}"
            sort_key = sort_base + created
            self._conn.execute(
                """
                INSERT INTO kb_faq_item (
                    item_id, document_id, sort_key, question, answer, status, disabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    item_id,
                    document_id,
                    sort_key,
                    row.question,
                    row.answer,
                    status,
                    ts,
                    ts,
                ),
            )
            created += 1
        if created == 0 and skipped > 0:
            raise ValueError(f"全部为重复问题，未导入（跳过 {skipped} 条）")
        sync_kb_to_kg(
            self._conn, document_id=document_id, display_title=lib["title"]
        )
        self._conn.commit()
        logger.info(
            "joyjoy: kb import document_id=%s imported=%s skipped=%s",
            document_id,
            created,
            skipped,
        )
        return {
            "imported": created,
            "skipped": skipped,
            "document_id": document_id,
        }

    def publish_library(self, document_id: str, *, actor: str = "vue-admin") -> dict[str, Any]:
        lib = self.get_library(document_id)
        ts = _now()
        self._conn.execute(
            """
            UPDATE kb_faq_item SET status = 'published', updated_at = ?
            WHERE document_id = ? AND status = 'draft' AND disabled = 0
            """,
            (ts, document_id),
        )
        items = sync_kb_to_kg(
            self._conn, document_id=document_id, display_title=lib["title"]
        )
        self._conn.commit()
        logger.info("joyjoy: kb published document_id=%s items=%s actor=%s", document_id, items, actor)
        return {**self.get_library(document_id), "ok": True, "published_items": items}