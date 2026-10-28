from mycs.db.connection import connect, get_db_path
from mycs.knowledge.service import KnowledgeService, ensure_database
from mycs.planning.toc_drill import run_toc_drill
from mycs.wiki.toc_persist import ingest_document_toc_draft, publish_mount


class _StubSelector:
    def __init__(self, picks: list[str]) -> None:
        self._picks = list(picks)
        self._i = 0

    def select_toc_branch(self, *, question, level, path, choices):
        if self._i >= len(self._picks):
            return {"action": "stop", "node_id": None, "reason": "test_stop"}
        want = self._picks[self._i]
        self._i += 1
        for c in choices:
            if c["section_ref"] == want or c["node_id"] == want:
                return {"action": "select", "node_id": c["node_id"], "reason": "test"}
        return {"action": "select", "node_id": choices[0]["node_id"], "reason": "fallback"}


def test_toc_drill_two_levels(tmp_path):
    ensure_database()
    text = (
        "1. 总则\n"
        "1.1 目的\n"
        "说明目的。\n"
        "1.2 范围\n"
        "说明范围。\n"
        "2. 考勤\n"
        "2.1 打卡\n"
        "每日打卡。\n"
    )
    conn = connect(get_db_path())
    try:
        meta = ingest_document_toc_draft(
            conn,
            text,
            document_id="doc_drill_test",
            title="t",
            source_uri="file://t",
        )
        publish_mount(conn, meta["mount_id"], actor="test")
        conn.commit()
    finally:
        conn.close()

    svc = KnowledgeService()
    try:
        drill = run_toc_drill(
            llm=_StubSelector(["2.", "2.1"]),
            svc=svc,
            document_id="doc_drill_test",
            question="怎么打卡",
        )
    finally:
        svc.close()

    assert drill.scope_section_prefix == "2.1"
    assert len(drill.path) >= 2
    assert drill.path[0]["section_ref"].startswith("2")
