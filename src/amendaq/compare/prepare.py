"""Build an isolated FAQ database for the comparison. Does not touch data/amendaq.db."""

from __future__ import annotations

from pathlib import Path

from amendaq.compare.corpus import TITLE, render_faq
from amendaq.db.bootstrap import ensure_schema
from amendaq.db.connection import connect
from amendaq.kb.service import KbService


def build_faq_db(db_path: Path) -> str:
    if db_path.exists():
        db_path.unlink()
    ensure_schema(db_path)
    conn = connect(db_path)
    try:
        kb = KbService(conn)
        library = kb.create_library(
            title=TITLE,
            description="对比测试库。与界面里的演示知识库分开。",
        )
        document_id = library["document_id"]
        kb.import_items(document_id, render_faq(), as_draft=False)
        return document_id
    finally:
        conn.close()
