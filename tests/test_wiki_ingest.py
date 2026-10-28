from mycs.db.bootstrap import bootstrap_database
from mycs.db.connection import connect
from mycs.knowledge.service import KnowledgeService
def test_find_wiki_by_topics(tmp_path):
    db = tmp_path / "test.db"
    bootstrap_database(db)
    svc = KnowledgeService(connect(db))
    try:
        result = svc.find_wiki_policies(topics=["overtime"], match="any", limit=5)
        assert result["count"] >= 1
        hit_ids = {h["policy_id"] for h in result["hits"]}
        assert "handbook_2_2" in hit_ids
    finally:
        svc.close()

