from amendaq.planning.toc_batch_select import section_under_chapters, run_toc_batch_chapter_select


def test_section_under_chapters():
    assert section_under_chapters("6.1.2", ["6."])
    assert section_under_chapters("6.", ["6."])
    assert not section_under_chapters("7.1", ["6."])
    assert section_under_chapters("4.3.1", ["4."])


class _BatchLLM:
    def __init__(self, actions: list[dict]):
        self._actions = actions
        self._i = 0

    def review_toc_catalog_batch(self, **kwargs):
        out = self._actions[self._i]
        self._i += 1
        return out


class _FakeSvc:
    def wiki_list_chapters(self, *, document_id: str):
        chapters = [
            {"section_ref": f"{i}.", "title": f"章{i}", "node_id": f"n{i}"}
            for i in range(1, 11)
        ]
        return {"chapters": chapters, "count": len(chapters)}


def test_batch_select_continue_then_pick(monkeypatch):
    monkeypatch.setenv("AMENDAQ_TOC_BATCH_SIZE", "4")
    llm = _BatchLLM(
        [
            {"action": "continue", "section_refs": [], "reason": "none"},
            {"action": "pick", "section_refs": ["5.", "6."], "reason": "hit"},
            {"action": "done", "section_refs": [], "reason": "enough"},
        ]
    )
    res = run_toc_batch_chapter_select(
        llm=llm,
        svc=_FakeSvc(),  # type: ignore[arg-type]
        document_id="doc_x",
        question="test",
    )
    assert res.selected_section_refs == ["5.", "6."]
    assert res.batches_shown == 3
    assert len(res.batch_log) == 3
    assert res.reason == "exhausted_batches"
