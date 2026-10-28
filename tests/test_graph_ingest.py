from mycs.db.bootstrap import bootstrap_database, ensure_schema
from mycs.db.connection import connect
from mycs.graph.extract import SectionGraphBuilder, ingest_txt_file
from mycs.knowledge.service import KnowledgeService
from mycs.wiki.ingest import policies_from_text


def test_policies_from_chinese_sections():
    text = "#### 2.3 Overtime Pay\nBody here.\n"
    policies = policies_from_text(text)
    assert "handbook_2_3" in policies


def test_section_graph_and_search(tmp_path):
    db = tmp_path / "kg.db"
    ensure_schema(db)
    src = tmp_path / "sample.txt"
    src.write_text("2.1 年假\n全职 15 天。\n", encoding="utf-8")
    builder = SectionGraphBuilder()
    graph = builder.extract(
        src.read_text(encoding="utf-8"),
        document_id="sample",
        title="sample.txt",
        source_uri="file://sample",
    )
    assert any(e.entity_type == "Policy" for e in graph.entities)

    import os

    os.environ["MYCS_DB"] = str(db)
    ingest_txt_file(src, document_id="sample", use_section_builder=True)
    svc = KnowledgeService(connect(db))
    try:
        found = svc.kg_search_entities(
            query="年假", document_id="sample", limit=5
        )
        assert found["count"] >= 1
    finally:
        svc.close()


def test_bootstrap_loads_handbook_graph(tmp_path):
    db = tmp_path / "mycs.db"
    bootstrap_database(db)
    conn = connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) AS c FROM kg_entity").fetchone()["c"]
        assert n > 10
    finally:
        conn.close()
