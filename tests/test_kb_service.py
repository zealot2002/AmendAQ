import sqlite3

from mycs.db.schema_kb import KB_DDL
from mycs.db.schema_kg import KG_DDL
from mycs.kb.service import KbService


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(KG_DDL)
    conn.executescript(KB_DDL)
    return conn


def test_kb_crud_and_sync():
    conn = _mem_conn()
    kb = KbService(conn)
    lib = kb.create_library(title="测试库", description="说明")
    doc = lib["document_id"]
    kb.create_item(doc, question="Q1?", answer="A1.")
    kb.create_item(doc, question="Q2?", answer="A2.")
    items = kb.list_items(doc)
    assert len(items) == 2
    assert all((i.get("section_ref") or "").startswith("1.") for i in items)
    ents = conn.execute(
        "SELECT COUNT(*) AS n FROM kg_entity WHERE document_id = ?", (doc,)
    ).fetchone()["n"]
    assert ents == 2
    kb.publish_library(doc)
    row = conn.execute(
        "SELECT catalog_mode FROM kg_document WHERE document_id = ?", (doc,)
    ).fetchone()
    assert row["catalog_mode"] == "flat_faq"
    pub = conn.execute(
        "SELECT COUNT(*) AS n FROM kb_faq_item WHERE document_id = ? AND status = 'published'",
        (doc,),
    ).fetchone()["n"]
    assert pub == 2


def test_kb_dedup_on_create_and_import():
    conn = _mem_conn()
    kb = KbService(conn)
    lib = kb.create_library(title="去重库")
    doc = lib["document_id"]
    kb.create_item(doc, question="年假有多少天？", answer="15 天")
    try:
        kb.create_item(doc, question="年假有多少天？", answer="重复")
        raise AssertionError("expected duplicate error")
    except ValueError as exc:
        assert "重复" in str(exc)
    text = """1. Q：年假有多少天？
A：已有
2. Q：病假怎么请？
A：通知主管"""
    res = kb.import_items(doc, text)
    assert res["imported"] == 1
    assert res["skipped"] == 1