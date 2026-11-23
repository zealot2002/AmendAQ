import uuid

from amendaq.db.connection import connect, get_db_path
from amendaq.knowledge.service import KnowledgeService, ensure_database
from amendaq.planning.sibling_expand import select_related_siblings, titles_share_topic
from amendaq.planning.toc_drill import run_toc_drill
from amendaq.wiki.toc_persist import ingest_document_toc_draft, publish_mount


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


def test_toc_drill_two_levels(tmp_path, monkeypatch):
    monkeypatch.setenv("AMENDAQ_DB", str(tmp_path / "drill.db"))
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


def test_titles_share_topic_does_not_match_unrelated_leave():
    assert titles_share_topic("年假", "年假结转")
    assert not titles_share_topic("年假", "病假")
    assert not titles_share_topic("年假", "公共假期")


def test_select_related_siblings_keeps_carryover_only():
    picked = {"node_id": "a", "kind": "leaf", "section_ref": "5.1", "title": "年假"}
    siblings = [
        picked,
        {"node_id": "b", "kind": "leaf", "section_ref": "5.2", "title": "病假"},
        {"node_id": "c", "kind": "leaf", "section_ref": "5.5", "title": "年假结转"},
    ]
    got = select_related_siblings(
        picked,
        siblings,
        "如果已经结转了 8 天年假，最多可以拥有多少天余额",
    )
    assert [n["section_ref"] for n in got] == ["5.5"]


def test_toc_drill_expands_same_topic_sibling(tmp_path, monkeypatch):
    monkeypatch.setenv("AMENDAQ_DB", str(tmp_path / "sibling.db"))
    ensure_database()
    text = (
        "5. 假期\n"
        "5.1 年假\n"
        "全职员工每完成一个完整工作年度可获得15个带薪年假日。\n"
        "5.2 病假\n"
        "病假需提供证明。\n"
        "5.5 年假结转\n"
        "未使用的年假最多可以结转至20天的余额上限。\n"
    )
    conn = connect(get_db_path())
    try:
        meta = ingest_document_toc_draft(
            conn,
            text,
            document_id="doc_drill_sibling",
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
            llm=_StubSelector(["5.", "5.1"]),
            svc=svc,
            document_id="doc_drill_sibling",
            question="已经结转了 8 天年假，最多可以拥有多少天余额",
        )
    finally:
        svc.close()

    assert drill.scope_section_prefix == "5.1"
    assert "5.5" in drill.scope_section_refs
    assert "5.2" not in drill.scope_section_refs
    assert any(e.get("mode") == "sibling_expand" for e in drill.trace_events)
