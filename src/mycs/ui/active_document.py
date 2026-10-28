from __future__ import annotations

import os
from pathlib import Path

from mycs.db.connection import connect, get_db_path
from mycs.knowledge.service import ensure_database
from mycs.paths import uploads_dir
from mycs.log import get_logger

logger = get_logger(__name__)

_ACTIVE_FILE = Path(__file__).resolve().parents[3] / "data" / ".active_document_id"


def set_active_document_id(document_id: str) -> None:
    doc = document_id.strip()
    if not doc:
        return
    _ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ACTIVE_FILE.write_text(doc + "\n", encoding="utf-8")
    os.environ["MYCS_GRAPH_DOCUMENT"] = doc
    logger.info("active document_id=%s (MYCS_GRAPH_DOCUMENT set)", doc)


def read_active_document_id() -> str:
    env = os.environ.get("MYCS_GRAPH_DOCUMENT", "").strip()
    if env:
        return env
    if _ACTIVE_FILE.is_file():
        return _ACTIVE_FILE.read_text(encoding="utf-8").strip()
    return ""


def resolve_active_document_id() -> str:
    """Best-effort current document for UI/API (no manual input)."""
    active = read_active_document_id()
    if active:
        return active

    ensure_database()
    up = uploads_dir()
    if up.is_dir():
        files = sorted(up.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            doc = files[0].stem
            logger.info("resolved document_id from latest upload file=%s doc=%s", files[0], doc)
            set_active_document_id(doc)
            return doc

    conn = connect(get_db_path())
    try:
        row = conn.execute(
            """
            SELECT document_id FROM wiki_document_mount
            ORDER BY updated_at DESC LIMIT 1
            """
        ).fetchone()
        if row:
            doc = row["document_id"]
            logger.info("resolved document_id from latest mount doc=%s", doc)
            set_active_document_id(doc)
            return doc
    except Exception as exc:
        logger.warning("resolve mount failed: %s", exc)
    finally:
        conn.close()
    return ""
